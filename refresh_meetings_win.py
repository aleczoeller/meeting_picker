# -*- coding: utf-8 -*-

import asyncio
import calendar
from datetime import datetime, timedelta
from os import getenv
from typing import List, Union

import geopandas as gp
import MySQLdb as mysql
import pandas as pd
from dotenv import find_dotenv, load_dotenv
from requests import request
from shapely.geometry import Point

from meetingpicker.utils.queries import (meeting_data_query,
                                         meeting_format_query,
                                         meeting_main_query)

load_dotenv(find_dotenv('.env'), override=True)

#Filter pandas warning about using a mysql connection directly
import warnings
warnings.filterwarnings('ignore', category=UserWarning)

REGION_FILE = 'static/regions.shp'
DAYS = {0: 'SUNDAY',
        1: 'MONDAY',
        2: 'TUESDAY',
        3: 'WEDNESDAY',
        4: 'THURSDAY',
        5: 'FRIDAY',
        6: 'SATURDAY',
        }
USERNAME = getenv('DBUSER', None)
PASSWORD = getenv('PASSWORD', None)
HOSTNAME = getenv('HOSTNAME', None)
DB = getenv('DBNAME', None)
"""Test MySQL Connection
with mysql.connect(user=USERNAME, password=PASSWORD, host=HOSTNAME, db=DB) as conn:
    cur = conn.cursor()
    print(cur.execute('select 1 as num'))
"""


MEETING_DETAIL_COLS = [ 'id_bigint',
                        'Meeting Name',
                        'Virtual Meeting Link',
                        'Virtual Meeting Additional Info',
                        'Phone Meeting Dial-in Number',
                        'Location Name',
                        'Street Address',
                        'Neighborhood',
                        'Town',
                        'Borough',
                        'County',
                        'Zip Code',
                        'Nation',
                        'Additional Location Information',
                        'Comments',
                        'Bus Lines',
                        'Train Lines',
                        'Contact 1 Email' ]

MEETING_MAIN_COLS = ['id_bigint',
                      'Day',
                     'Start Time',
                     'Duration',
                     'Formats',
                     'Longitude',
                     'Latitude']

# Rules for sorting tables 
today = datetime.today()
weekday = calendar.weekday(today.year, today.month, today.day) 
start_list = list(range(weekday, 7, 1))
end_list = list(range(0, weekday))
day_list = start_list + end_list 
day_names = [DAYS[i] for i in day_list]
day_list = [*range(7)]
DAYS_ORDERED = {i:j for i, j in zip(day_names, day_list)}

# Variables for dataframes
ALL_MEETINGS = None
ALL_REGIONS = None
ALL_MEETINGS_ONLINE = None
ALL_MEETINGS_INPERSON = None
GEO_MEETINGS = None
# Variables for async futures
am_future = None
ar_future = None
gm_future = None
amo_future = None
ami_future = None


class ProcessingError(Exception):
     pass  


def process_meeting_data(meeting_data:pd.DataFrame,
                          online:bool) -> pd.DataFrame:
    """Take BMLT-formatted MySQL table and process into 
    properly encoded human-readable format.

    Args:
        meeting_data (pd.DataFrame): data from BMLT
        online (bool): whether to filter for online meetings. Defaults to False.

    Returns:
        pd.DataFrame: cleaned data
    """
    # Convert to wide format
    meeting_data = meeting_data.pivot(index='id_bigint', 
                                      columns='field_prompt', 
                                      values='data_string')
    meeting_data.reset_index(drop=False, inplace=True)
    # Re-organize columns and drop unnecessary ones
    meeting_data = meeting_data[MEETING_DETAIL_COLS]
    # Filter online meetings
    if online:
        meeting_data = meeting_data[~pd.isnull(meeting_data['Virtual Meeting Link'])]
        meeting_data = meeting_data[meeting_data['Virtual Meeting Link'] != '']
    return meeting_data 

def sort_on_day(series:pd.Series) -> pd.Series:
    """Sort a series of days in order of the week, starting with the current day.

    Args:
        series (pd.Series): Pandas series

    Returns:
        pd.Series: Pandas series, sorted
    """
    return series.apply(lambda x: DAYS_ORDERED.get(x, 9999))


def get_meeting_data(online:bool = False) -> pd.DataFrame:
    """Return all meeting information. 

    Args:
        online (bool, optional): whether to filter for online meetings. Defaults to False.

    Returns:
        pd.DataFrame: Fully cleaned meetings
    """
    with mysql.connect(user=USERNAME, password=PASSWORD, host=HOSTNAME, db=DB) as conn:
        meeting_data = pd.read_sql(con=conn, sql=meeting_data_query)
        meeting_data = process_meeting_data(meeting_data, online)
        meeting_main = pd.read_sql(con=conn, sql=meeting_main_query)
        meeting_main.columns = MEETING_MAIN_COLS
        meeting_formats = pd.read_sql(con=conn, sql=meeting_format_query)
        meeting_formats = {k:v for k, v in zip(meeting_formats['shared_id_bigint'].astype(str).values, 
                                                meeting_formats['name_string'].values)}
        meeting_main['Formats'] = meeting_main['Formats'].apply(lambda x: ', '.join([meeting_formats[i] \
                                           for i in x.split(',')]) if not x=='' else '')
    meeting_data = pd.merge(left=meeting_data,
                             right=meeting_main,
                            how='right',
                            on='id_bigint')
    meeting_data['Day'] = meeting_data['Day'].apply(lambda x: DAYS[x])
    meeting_data['Start Time'] = meeting_data['Start Time'].astype(str)
    meeting_data['Start Time'] = meeting_data['Start Time'].apply(lambda x: \
                                   datetime.strptime(x.split(' ')[-1], '%H:%M:%S').strftime('%I:%M %p'))
    meeting_data['Duration'] = meeting_data['Duration'].astype(str)
    meeting_data['Duration'] = meeting_data['Duration'].apply(lambda x: \
                                   datetime.strptime(x.split(' ')[-1], '%H:%M:%S').strftime('%H:%M'))
    meeting_data['Duration'] = meeting_data['Duration'].apply(lambda x: \
                                   x[1:] if x[0] == '0' else x)    
    meeting_data['Day Ordered'] = meeting_data.apply(lambda x: DAYS_ORDERED[x['Day']], axis=1)
    meeting_data['Real Time'] = pd.to_datetime(meeting_data['Start Time'], format='%I:%M %p')
    meeting_data.sort_values(by=['Day Ordered', 'Real Time'], inplace=True, ascending=True)
    meeting_data.reset_index(drop=True, inplace=True)
    # Added following line to accomodate geopandas not importing datetime objects correctly
    meeting_data['Start Time'] = meeting_data['Real Time'].apply(lambda x: x.strftime('%H:%M:%S'))
    meeting_data.drop(['id_bigint', 'Day Ordered', 'Real Time'], axis=1, inplace=True)
    return meeting_data


async def all_meetings(am_future:asyncio.Future) -> asyncio.Future:
    """Asyncronous call to generate meeting dataframe. Returns as a future.

    Args:
        am_future (asyncio.Future): new empty future object

    Returns:
        asyncio.Future: future object, value is meeting dataframe
    """
    # GET ALL MEETING DATA. Perform once on page load and store in session
    ALL_MEETINGS = get_meeting_data(online=False)
    ALL_MEETINGS['geometry'] = [Point(i,j) for i, j in zip(ALL_MEETINGS['Longitude'].values,
                                                        ALL_MEETINGS['Latitude'].values)]
    ALL_MEETINGS = gp.GeoDataFrame(ALL_MEETINGS, crs='EPSG:4326', geometry='geometry')
    am_future.set_result(ALL_MEETINGS)

async def all_regions(ar_future:asyncio.Future) -> asyncio.Future:
    """Asynchronous call to generate all regions. Returns as a future.

    Args:
        ar_future (asyncio.Future): new empty future object

    Returns:
        asyncio.Future: future object, value is all regions as shapely geometry
    """
    ALL_REGIONS = gp.read_file(REGION_FILE).geometry.unary_union
    ALL_REGIONS = gp.GeoDataFrame(geometry=[ALL_REGIONS], crs='EPSG:4326')
    ar_future.set_result(ALL_REGIONS)

async def geo_meetings(am_future: asyncio.Future, gm_future:asyncio.Future) -> asyncio.Future:
    """Asynchronous call to get all meetings as geopandas dataframe. Returns as a future.

    Args:
        gm_future (asyncio.Future): new empty future object

    Returns:
        asyncio.Future: future object, value is all meetings as geopandas dataframe
    """
    ALL_MEETINGS = await am_future
    AR = gp.read_file(REGION_FILE)
    AR = AR[['intl', 'geometry']]
    GEO_MEETINGS = gp.GeoDataFrame(ALL_MEETINGS, crs='EPSG:4326', geometry='geometry')
    # Join to add international column to GEO_MEETINGS
    GEO_MEETINGS = gp.sjoin(GEO_MEETINGS, AR)
    GEO_MEETINGS.drop(['index_right'], axis=1, inplace=True)
    gm_future.set_result(GEO_MEETINGS)

async def all_meetings_online(gm_future:asyncio.Future, amo_future:asyncio.Future) -> asyncio.Future:
    """Asynchronous call to get all online meetings. Returns as a future.
    
    Args:
        amo_future (asyncio.Future): new empty future object

    Returns:
        asyncio.Future: future object, value is all online meetings
    """
    GEO_MEETINGS = await gm_future
    ALL_MEETINGS_ONLINE = GEO_MEETINGS[(~pd.isnull(GEO_MEETINGS['Virtual Meeting Link']) & \
                                    (GEO_MEETINGS['Virtual Meeting Link'] != ''))]
    amo_future.set_result(ALL_MEETINGS_ONLINE)

async def all_meetings_inperson(gm_future:asyncio.Future, ami_future:asyncio.Future) -> asyncio.Future:
    """Asynchronous call to get all in-person meetings. Returns as a future.

    Args:
        ami_future (asyncio.Future): new empty future

    Returns:
        asyncio.Future: future object, value is all in-person meetings
    """
    GEO_MEETINGS = await gm_future
    # Filter to just in-person meetings
    ALL_MEETINGS_INPERSON = GEO_MEETINGS[(~pd.isnull(GEO_MEETINGS['Street Address']) & \
                                        (GEO_MEETINGS['Street Address'] != ''))]
    ami_future.set_result(ALL_MEETINGS_INPERSON)
    

async def run():
    # Call all asynchronous functions.
    # Create future objects (that can be awaited in subsequent methods)
    # and pass them to the async functions
    loop = asyncio.get_running_loop()
    global am_future, ar_future, gm_future, amo_future, ami_future, r_future
    am_future = loop.create_future()
    ar_future = loop.create_future()
    gm_future = loop.create_future()
    amo_future = loop.create_future()
    ami_future = loop.create_future()
    # Call all async functions
    loop.create_task(all_meetings(am_future))
    loop.create_task(all_regions(ar_future))
    loop.create_task(geo_meetings(am_future, gm_future))
    loop.create_task(all_meetings_online(gm_future, amo_future))
    loop.create_task(all_meetings_inperson(gm_future, ami_future))


async def save_all():
    """Wrapper function to save all async functions as global variables.
    """
    ALL_MEETINGS = await am_future
    ALL_MEETINGS_ONLINE = await amo_future
    ALL_MEETINGS_INPERSON = await ami_future
    ALL_REGIONS = await ar_future
    GEO_MEETINGS = await gm_future
    # Update to add international column to all meetings
    ALL_MEETINGS = GEO_MEETINGS
    # Save all dataframes to local file
    ALL_MEETINGS.to_file('data/all_meetings.geojson', driver='GeoJSON')
    ALL_MEETINGS_ONLINE.to_file('data/all_meetings_online.geojson', driver='GeoJSON')
    ALL_MEETINGS_INPERSON.to_file('data/all_meetings_inperson.geojson', driver='GeoJSON')
    ALL_REGIONS.to_file('data/all_regions.geojson', driver='GeoJSON')


if __name__ == '__main__':
    asyncio.run(run())
    asyncio.run(save_all())

