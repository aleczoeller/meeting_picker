import calendar
import os
import pandas as pd
from datetime import datetime, timedelta
from os import getenv
from requests import request
from typing import List

import geopandas as gp
import MySQLdb as mysql
from django.core import HttpResponse, JsonResponse
from dotenv import load_dotenv, find_dotenv
from shapely.geometry import Point



load_dotenv(find_dotenv('../../.env'))

REGION_FILE = 'nz_regions.shp'
DAYS = {
            i:j for i, j in zip([*range(7)], 
            ['MONDAY', 'TUESDAY', 'WEDNESDAY',
             'THURSDAY', 'FRIDAY', 'SATURDAY',
             'SUNDAY'
             ])
         }
USERNAME = getenv('USERNAME', None)
PASSWORD = getenv('PASSWORD', None)
HOSTNAME = getenv('HOSTNAME', None)
DB = getenv('DBNAME', None)

         
        
def get_data(parameter:str = None,
             previous_parameters:List[dict, str, int] = []) -> pd.DataFrame:
    """
    Method to retrieve a table of meeting information, given a set of parameters to 
    filter the data with.
    
    Args:
    
        parameter (str): this specific parameter/level of user query 
        previous_parameters List[list, dict, str, int]: List of all parameters provided
        
    Returns:
    
        pd.DataFrame: table of meeting information 
        
    """
    #Check parameter. DO NOT QUERY DATABASE if not parameters are set!
    if parameter == 'base':
        return pd.DataFrame({})
    #Create database conn and pull meeting data 
    clause = """SELECT * FROM `na_comdef_meetings` WHERE """
    if parameter == 'venue':
        clause = clause + f"meeting_format = {previous_parameters['venue']}"
    elif parameter == 'region':
        lat_lon_ids = pd.read_sql("""select id, lat, lon from `na_comdef_meetings` where 1""")
        meetings = gp.GeoDataFrame({'id':lat_lon_ids['id'], 
                                    'geometry':[Point(i,j) for i, j in zip(lat_lon_ids['lon'],
                                                                           lat_lon_ids['lat'])]},
                                    crs='EPSG:4326', geometry='geometry')
        del lat_lon_ids 
        regions = gp.read_file(REGION_FILE)
        regions = regions.loc[regions.region==previous_parameters['region']
    


def process_request(request:requst, *args, **kwargs) -> JsonResponse:
	"""
	Main view function. Takes user's GET requests 
	(as button clicks) and returns either meeting 
	list or additional query parameters. As a very 
	important step, view returns "No Meetings" if for any 
	parameter selected, there are none found.  For example, 
	if no meetings are on Tuesday Online, instead of presenting
	a Region the view will go back to the start, with a "None Found"
	type message.
	
	Order of Query Parameters:
	 - Day of the week
	 - Online/In person
	 - Region
	 - City
	
	"""
	# Identify type of request
	if request.type != "GET":
		return HttpResponse(request)
    selections = request.data['selections']
    if list(selections.keys()) == 'base':
        today = datetime.today()
        weekday = calendar.weekday(today.year, today.month, today.day)
        start_list = list(range(weekday, 7, 1))
        end_list = list(range(0, weekday))
        day_list = start_list + end_list 
        day_list = [DAYS[i] for i in day_list]
        return JsonResponse({'days':day_list})
    if list(selection.keys())[0] == 'venue':
        #Account for two choices, online and in-person 
        if selection['venue'] == 'online':
        
	
	
	