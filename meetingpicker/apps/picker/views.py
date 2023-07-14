import calendar
import pandas as pd
from datetime import datetime, timedelta
from os import getenv
from requests import request
from typing import List, Union

import geopandas as gp
import MySQLdb as mysql
from django.http import HttpResponse, JsonResponse
from django.views.generic import View
from dotenv import load_dotenv, find_dotenv
from shapely.geometry import Point

from utils.queries import (meeting_data_query,
							meeting_main_query,
							meeting_format_query,)


#Filter pandas warning about using a mysql connection directly
import warnings
warnings.filterwarnings('ignore', category=UserWarning)

#Load environment variables from file (db connection parameters)
load_dotenv(find_dotenv('../.env'), override=True)

REGION_FILE = '../static/regions.shp'
DAYS = {
		i:j for i, j in zip([*range(7)], 
		['MONDAY', 'TUESDAY', 'WEDNESDAY',
		 'THURSDAY', 'FRIDAY', 'SATURDAY',
		 'SUNDAY'
		 ])
	    }
USERNAME = getenv('DBUSER', None)
PASSWORD = getenv('PASSWORD', None)
HOSTNAME = getenv('HOSTNAME', None)
DB = getenv('DBNAME', None)

MEETING_DETAIL_COLS = [ 'id_biginxt',
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


def format_table(mtgs:pd.DataFrame) -> str:
	"""Take table of meetings and format for display.

	Args:
		mtgs (pd.DataFrame): DataFrame of meetings

	Returns:
		pd.DataFrame: table for display
	"""
	mtgs.fillna('', inplace=True)
	for col in mtgs:
		mtgs[col] = mtgs[col].astype(str)
	mtgs['Virtual'] = mtgs.apply(lambda x: '\n'.join(filter(None, [
			'<a href="' + 
			x['Virtual Meeting Link'] +
			'">' + 
			'Click to Join Meeting' +
			'</a>',
			x['Phone Meeting Dial-in Number'] if not \
				x['Phone Meeting Dial-in Number'] == '' else None,
			x['Virtual Meeting Additional Info'] if not \
				x['Virtual Meeting Additional Info'] == '' else None])), axis=1)
	mtgs['Virtual'] = mtgs['Virtual'].apply(lambda x: x.replace('<a href=""></a>', ''))
	# Create cleaned location column for display purposes
	mtgs['Location'] = mtgs.apply(lambda x: '\n'.join(filter(None, [
			x['Location Name'].strip() if not x['Location Name'].strip() == '' else None,
			x['Street Address'].strip() if not x['Street Address'].strip() == '' else None,
			', '.join(filter(None, [  # Filter out empty strings
				x['Neighborhood'].strip() if not x['Neighborhood'].strip() == '' else None,
				x['Town'].strip() if not x['Town'].strip() == '' else None,
				x['Borough'].strip() if not x['Borough'].strip() == '' else None,
				x['County'].strip() if not x['County'].strip() == '' else None,
				x['Zip Code'].strip() if not x['Zip Code'].strip() == '' else None,
				x['Nation'].strip() if not x['Nation'].strip() == '' else None])),
			x['Additional Location Information'].strip() if not \
				x['Additional Location Information'].strip() == '' else None,
			x['Comments'].strip() if not x['Comments'].strip() == '' else None,
			x['Bus Lines'].strip() if not x['Bus Lines'].strip() == '' else None,
			x['Train Lines'].strip() if not x['Train Lines'].strip() == '' else None])
			), axis=1)
	# Limit columns to "for display" only
	mtgs = mtgs[['Day', 'Meeting Name', 'Virtual', 'Location', 
	      		 'Start Time', 'Duration', 'Formats']]
	#Format Table as HTML table for display
	mtgs = mtgs.to_html(classes='table table-striped table-bordered table-hover',
		     			index=False, escape=False, render_links=True)	
	return mtgs
	

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
							       datetime.strptime(x.split(' ')[-1], '%H:%M:%S').strftime('%I:%M %p'))
	meeting_data.sort_values(by=['id_bigint', 'Day'], inplace=True, ascending=True)
	meeting_data.drop(['id_bigint'], axis=1, inplace=True)
	return meeting_data


# GET ALL MEETING DATA. Perform once on page load and store in session
ALL_MEETINGS = get_meeting_data(online=False)
ALL_MEETINGS_ONLINE = ALL_MEETINGS[(~pd.isnull(ALL_MEETINGS['Virtual Meeting Link']) & \
				    			   (ALL_MEETINGS['Virtual Meeting Link'] != ''))]
	


def get_data(parameter:str = None,
		     previous_parameters:Union[dict, str, int] = {}) -> list | pd.DataFrame:
	"""
	Method to retrieve a table of meeting information, given a set of parameters to 
	filter the data with.
	
	Args:
	
	parameter (str): this specific parameter/level of user query 
	previous_parameters List[list, dict, str, int]: List of all parameters provided
	
	Returns:
	
	pd.DataFrame: table of meeting information 
	
	"""
	#Create database conn and pull meeting data 
	if parameter == 'venue':
		if previous_parameters['venue'] == 'in-person':
			regions = gp.read_file(REGION_FILE)
			regions.sort_values(by='id', inplace=True)
			meetings = ALL_MEETINGS.copy()
			if not previous_parameters['day'] == 'SHOW ALL':
				these_days = {i:j for j, i in DAYS.items()}
				day = these_days[previous_parameters['day']]
				meetings = meetings.loc[meetings['Day'] == day]
			#Filter to just in-person meetings
			meetings = meetings.loc[~pd.isnull(meetings['Street Address'])]
			#Filter to just meetings in the region
			meetings['geometry'] = [Point(i,j) for i, j in zip(meetings['Longitude'].values,
						      							   	  meetings['Latitude'].values)]
			meetings = gp.GeoDataFrame(meetings, crs='EPSG:4326', geometry='geometry')
			regions = regions.loc[regions['geometry'].intersects(meetings.unary_union)]
			del meetings
			return ['SHOW ALL'] + regions.region.values.tolist()
		elif previous_parameters['venue'] == 'online':
			meetings = ALL_MEETINGS_ONLINE.copy()
			meetings.drop(['geometry', 'Longitude', 'Latitude'], 
		 				  axis=1, inplace=True, errors='ignore')
			if not previous_parameters['day'] == 'SHOW ALL':
				these_days = {i:j for j, i in DAYS.items()}
				day = these_days[previous_parameters['day']]
				meetings = meetings.loc[meetings['Day'] == day]
			return meetings
			

	elif parameter == 'region':
		if previous_parameters['region'] == 'SHOW ALL':
			meetings = ALL_MEETINGS.copy()
			if not previous_parameters['day'] == 'SHOW ALL':
				these_days = {i:j for j, i in DAYS.items()}
				day = these_days[previous_parameters['day']]
				meetings = meetings.loc[meetings['Day'] == day]
				meetings.drop(['geometry', 'Longitude', 'Latitude'], 
		 				  axis=1, inplace=True, errors='ignore')
				return meetings 
			else:
				meetings.drop(['geometry', 'Longitude', 'Latitude'], 
		 				  axis=1, inplace=True, errors='ignore')
				return meetings
		else:
			regions = gp.read_file(REGION_FILE)
			region = regions.loc[regions.region==previous_parameters['region']].geometry.values[0]
			# Filter meetings to only show meetings in region
			meetings = ALL_MEETINGS.copy()
			#Filter to just meetings in the region
			meetings['geometry'] = [Point(i,j) for i, j in zip(meetings['Longitude'].values,
						      							   	   meetings['Latitude'].values)]
			meetings = gp.GeoDataFrame(meetings, crs='EPSG:4326', geometry='geometry')
			meetings = meetings.loc[meetings['geometry'].within(region)]
			del regions
			del region
			meetings.drop(['geometry', 'Longitude', 'Latitude'], 
		 				  axis=1, inplace=True, errors='ignore')
			return meetings


	else:
		raise ProcessingError(f"Invalid parameter: {parameter}")
	


class Picker(View):
	"""View for meeting picker. 
	
	"""
	template_name = 'base.html'
	context_object_name = 'entries'
	model = None
	allow_empty = True

	def get_context_data(self, **kwargs):
		"""Set initial view - days to pick meeting from.
		"""
		context = super(Picker, self).get_context_data(**kwargs)
		today = datetime.today()
		weekday = calendar.weekday(today.year, today.month, today.day)
		start_list = list(range(weekday, 7, 1))
		end_list = list(range(0, weekday))
		day_list = start_list + end_list 
		day_list = ['SHOW ALL'] + [DAYS[i] for i in day_list]
		context['days'] = day_list
		return context
	

	def get(self, request:request,
			   *args, **kwargs) -> JsonResponse | HttpResponse:
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
		
		"""
		# Identify type of request
		if request.method != 'GET' or kwargs['day'] == 'nan':
			return HttpResponse(request)
		#Account for two choices, online and in-person 
		elif kwargs['venue'] == 'online':
			meetings = get_data(parameter='venue', 
								previous_parameters={'venue':'online',
													 'day':kwargs['day']}
								)
			return JsonResponse({'meetings':format_table(meetings)})
		elif kwargs['venue'] == 'in-person' and kwargs['region'] == 'nan':
			regions = get_data(parameter='venue', 
							   previous_parameters={'venue':'in-person',
													'day':kwargs['day']}
							  )
			return JsonResponse({'regions':regions})
		elif kwargs['region'] != 'nan':
			meetings = get_data(parameter='region', 
								previous_parameters={'venue':kwargs['venue'],
													'day':kwargs['day'],
													'region':kwargs['region']}
								)
			return JsonResponse({'meetings':format_table(meetings)})
		else:
			raise ProcessingError(f"Invalid request: {request}")
			