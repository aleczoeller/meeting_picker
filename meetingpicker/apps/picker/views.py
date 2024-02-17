import calendar
import pandas as pd
from datetime import datetime, timedelta
from os import getenv
from requests import request
from typing import List, Union

import asyncio
import geopandas as gp
import MySQLdb as mysql
from asgiref.sync import sync_to_async
from django.http import HttpResponse, JsonResponse, HttpResponseRedirect
from django.shortcuts import render
from django.views.generic import ListView
from dotenv import load_dotenv, find_dotenv
from shapely.geometry import Point

from meetingpicker.utils.queries import (meeting_data_query,
		 								meeting_main_query,
		 								meeting_format_query,)
from meetingpicker.apps.picker.models import PickerModel


#Filter pandas warning about using a mysql connection directly
import warnings
warnings.filterwarnings('ignore', category=UserWarning)

#Load environment variables from file (db connection parameters)
load_dotenv(find_dotenv('../.env'), override=True)

REGION_FILE = 'static/regions.shp'
DAYS = {0: 'MONDAY',
		1: 'TUESDAY',
		2: 'WEDNESDAY',
		3: 'THURSDAY',
		4: 'FRIDAY',
		5: 'SATURDAY',
		6: 'SUNDAY'}


# Rules for sorting tables 
today = datetime.today()
weekday = calendar.weekday(today.year, today.month, today.day) 
start_list = list(range(weekday, 7, 1))
end_list = list(range(0, weekday))
day_list = start_list + end_list 
day_names = [DAYS[i] for i in day_list]
day_list = [*range(7)]
DAYS_ORDERED = {i:j for i, j in zip(day_names, day_list)}

# Read meeting data
ALL_MEETINGS = gp.read_file('data/all_meetings_inperson.geojson')
ALL_REGIONS = gp.read_file('data/all_regions.geojson')
ALL_MEETINGS_ONLINE = gp.read_file('data/all_meetings_online.geojson')
ALL_MEETINGS_INPERSON = gp.read_file('data/all_meetings_inperson.geojson')
# Issue with geopandas formatting - ensure datetimes are in correct format
for df in (ALL_MEETINGS, ALL_MEETINGS_ONLINE, ALL_MEETINGS_INPERSON):
	df['Start Time'] = pd.to_datetime(df['Start Time'], format='%H:%M:00')
	# Roundabout method for sorting first on day of the week, THEN on time
	df['DayTime'] = df.apply(lambda x: ((DAYS_ORDERED.get(x['Day'], 9999)+1)*10000) * \
						  	(86400 - (x['Start Time'] - datetime(1900,1,1)).seconds), 
							axis=1)
	df.sort_values(by='DayTime', inplace=True)
	df.drop('DayTime', axis=1, inplace=True)
	df['Start Time'] = df['Start Time'].dt.strftime('%I:%M %p')
	df['Start Time'] = df['Start Time'].apply(lambda x: str(x)[1:] if str(x)[0] == '0' \
										   	  else str(x))
	df['Duration'] = pd.to_datetime(df['Duration'], format='%H:%M:00')
	df['Duration'] = df['Duration'].dt.strftime('%H:%M')
	df['Duration'] = df['Duration'].apply(lambda x: str(x)[1:] if str(x)[0] == '0' \
									   	  else str(x))
# UPDATED: 17-02-2024 -> filter out international meetings 
ALL_MEETINGS = ALL_MEETINGS.loc[ALL_MEETINGS['intl']==0]
ALL_MEETINGS_ONLINE = ALL_MEETINGS_ONLINE.loc[ALL_MEETINGS_ONLINE['intl']==0]
ALL_MEETINGS_INPERSON = ALL_MEETINGS_INPERSON.loc[ALL_MEETINGS_INPERSON['intl']==0]
# Read region data
REGIONS = gp.read_file(REGION_FILE)




class ProcessingError(Exception):
	 pass  


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
	mtgs['Virtual'] = ''
	mtgs['Location'] = ''
	if not len(mtgs) == 0:
		mtgs['Virtual'] = mtgs.apply(lambda x: '<br>'.join(filter(None, [
				'<a href="' + 
				x['Virtual Meeting Link'] +
				'">' + 
				'Click to Join Meeting' +
				'</a>',
				x['Phone Meeting Dial-in Number'] if not \
					x['Phone Meeting Dial-in Number'] == '' else None,
				x['Virtual Meeting Additional Info'] if not \
					x['Virtual Meeting Additional Info'] == '' else None])), axis=1)
		mtgs['Virtual'] = mtgs['Virtual'].apply(lambda x: x.replace('<a href="">Click to Join Meeting</a>', ''))
		# Create cleaned location column for display purposes
		mtgs['Location'] = mtgs.apply(lambda x: '<br>'.join(filter(None, [
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
	mtgs = mtgs.to_html(classes='table table-striped table-bordered table-hover', table_id='mtgs',
		     			index=False, escape=False, render_links=True)	
	return mtgs

	
def sort_on_day(series:pd.Series) -> pd.Series:
	"""Sort a series of days in order of the week, starting with the current day.

	Args:
		series (pd.Series): Pandas series

	Returns:
		pd.Series: Pandas series, sorted
	"""
	return series.apply(lambda x: DAYS_ORDERED.get(x, 9999))


def get_data(parameter:str = None,
		     previous_parameters:Union[dict, str, int] = {}) -> Union[list, pd.DataFrame]:
	"""
	Method to retrieve a table of meeting information, given a set of parameters to 
	filter the data with.
	
	Args:
	
	parameter (str): this specific parameter/level of user query 
	previous_parameters List[list, dict, str, int]: List of all parameters provided
	
	Returns:
	
	pd.DataFrame: table of meeting information 
	
	"""
	# Create database conn and pull meeting data 
	if parameter == 'venue':
		if previous_parameters['venue'] == 'in-person':
			REGIONS.sort_values(by='id', inplace=True)
			#Filter to just in-person meetings
			meetings = ALL_MEETINGS.loc[(~pd.isnull(ALL_MEETINGS['Street Address'])) & \
			   						(ALL_MEETINGS['Street Address'] != '')]
			if len(meetings) == 0:
				return ['NONE']
			regions = REGIONS.loc[REGIONS['geometry'].intersects(meetings.unary_union)]
			del meetings
			return ['SHOW ALL'] + regions.region.values.tolist()
		elif previous_parameters['venue'] == 'online':
			REGIONS.sort_values(by='id', inplace=True)
			#Filter to just in-person meetings
			meetings = ALL_MEETINGS.loc[(~pd.isnull(ALL_MEETINGS['Virtual Meeting Link'])) & \
			   						(ALL_MEETINGS['Virtual Meeting Link'] != '')]
			if len(meetings) == 0:
				return ['NONE']
			regions = REGIONS.loc[REGIONS['geometry'].intersects(meetings.unary_union)]
			del meetings
			return ['SHOW ALL'] + regions.region.values.tolist()
		else:
			raise ValueError('Invalid venue parameter')
	elif parameter == 'region':
		if previous_parameters['venue'] == 'in-person':
			if not previous_parameters['region'] == 'SHOW ALL':
				regions = REGIONS.loc[REGIONS['region']==previous_parameters['region']]
				meetings = ALL_MEETINGS_INPERSON[['Day', 'geometry']]
			else:
				regions = REGIONS.loc[REGIONS['intl'].astype(int)==0]
				meetings = ALL_MEETINGS_INPERSON.loc[ALL_MEETINGS_INPERSON['intl']==0][['Day', 'geometry']]
			#Filter to just meetings in the region
			if previous_parameters['region'] == 'SHOW ALL':
				meetings = gp.sjoin(meetings, REGIONS)
			else:
				meetings = gp.sjoin(meetings, regions)
				del regions
			meetings = meetings[['Day']]
			meetings.sort_values(by='Day', key=sort_on_day, inplace=True)
			days = meetings.Day.unique().tolist()
			return ['SHOW ALL'] + days
		elif previous_parameters['venue'] == 'online':
			if not previous_parameters['region'] == 'SHOW ALL':
				regions = REGIONS.loc[REGIONS['region']==previous_parameters['region']]
				meetings = ALL_MEETINGS_ONLINE[['Day', 'geometry']]
			else:
				regions = REGIONS.loc[REGIONS['intl'].astype(int)==0]
				meetings = ALL_MEETINGS_ONLINE.loc[ALL_MEETINGS_ONLINE['intl']==0][['Day', 'geometry']]
			#Filter to just meetings in the region
			if previous_parameters['region'] == 'SHOW ALL':
				meetings = gp.sjoin(meetings, REGIONS)
			elif regions is None or len(regions) == 0:
				meetings = meetings.loc[meetings['region'] == 'not_real_value']
			else:
				meetings = gp.sjoin(meetings, regions)
				del regions
			meetings = meetings[['Day']]
			meetings.sort_values(by='Day', key=sort_on_day, inplace=True)
			days = meetings.Day.unique().tolist()
			return ['SHOW ALL'] + days
		else:
			raise ValueError('Invalid venue parameter')
			

	elif parameter == 'day':
		if previous_parameters['region'] == 'SHOW ALL':
			meetings = ALL_MEETINGS.loc[ALL_MEETINGS['intl']==0]
			meetings.sort_values(by='Day', key=sort_on_day, inplace=True)
			if previous_parameters['venue'] == 'online':
				meetings = meetings.loc[(~pd.isnull(meetings['Virtual Meeting Link'])) & \
			    					    (meetings['Virtual Meeting Link'] != '')]
			elif previous_parameters['venue'] == 'in-person':
				meetings = meetings.loc[(~pd.isnull(meetings['Street Address'])) & \
			    						(meetings['Street Address'] != '')]
			else:
				raise ValueError('Invalid venue parameter')
			#Filter to just meetings on a given day
			if not previous_parameters['day'] == 'SHOW ALL':
				meetings = meetings.loc[meetings['Day'] == previous_parameters['day']]
				meetings.drop(['geometry', 'Longitude', 'Latitude'], 
		 				  axis=1, inplace=True, errors='ignore')
				return meetings 
			else:
				meetings.drop(['geometry', 'Longitude', 'Latitude'], 
		 				  axis=1, inplace=True, errors='ignore')
				return meetings
		else:
			if previous_parameters['day'] == 'SHOW ALL':
				region = REGIONS.loc[REGIONS.region==previous_parameters['region']].geometry.values[0]
				meetings = ALL_MEETINGS
				meetings.sort_values(by='Day', key=sort_on_day, inplace=True)
				if previous_parameters['venue'] == 'online':
					meetings = meetings.loc[(~pd.isnull(meetings['Virtual Meeting Link'])) & \
											(meetings['Virtual Meeting Link'] != '')]
				elif previous_parameters['venue'] == 'in-person':
					meetings = meetings.loc[(~pd.isnull(meetings['Street Address'])) & \
											(meetings['Street Address'] != '')]
				else:
					raise ValueError('Invalid venue parameter')
				meetings = meetings.loc[meetings['geometry'].within(region)]
				del region
				meetings.drop(['geometry', 'Longitude', 'Latitude'], 
							axis=1, inplace=True, errors='ignore')
				return meetings
			else:
				region = REGIONS.loc[REGIONS.region==previous_parameters['region']].geometry.values[0]
				meetings = ALL_MEETINGS
				meetings.sort_values(by='Day', key=sort_on_day, inplace=True)
				if previous_parameters['venue'] == 'online':
					meetings = meetings.loc[(~pd.isnull(meetings['Virtual Meeting Link'])) & \
											(meetings['Virtual Meeting Link'] != '')]
				elif previous_parameters['venue'] == 'in-person':
					meetings = meetings.loc[(~pd.isnull(meetings['Street Address'])) & \
											(meetings['Street Address'] != '')]
				else:
					raise ValueError('Invalid venue parameter')
				#Filter to just meetings in the region
				meetings = meetings.loc[meetings['Day'] == previous_parameters['day']]
				#Filter to just meetings in the region
				meetings = gp.GeoDataFrame(meetings, crs='EPSG:4326', geometry='geometry')
				meetings = meetings.loc[meetings['geometry'].within(region)]
				del region
				meetings.drop(['geometry', 'Longitude', 'Latitude'], 
							axis=1, inplace=True, errors='ignore')
				return meetings
	else:
		raise ProcessingError(f"Invalid parameter: {parameter}")
	


class Picker(ListView):
	"""View for meeting picker. 
	
	"""
	template_name = 'base.html'
	context_object_name = 'entries'
	model = PickerModel
	allow_empty = False

	def get_context_data(self, **kwargs):
		"""Set initial view - days to pick meeting from.
		"""
		self.object_list = super().get_queryset()
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
			   *args, **kwargs) -> Union[JsonResponse, HttpResponse]:
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
		- Online/In person
		- Region
		- Day of the week
		
		"""
		# Identify type of request
		if request.method != 'GET' or self.kwargs['venue'] == 'nan':
			return render(request, self.template_name, context=self.get_context_data())
		# Get data passed through URI
		if self.kwargs['venue'] == 'in-person' and self.kwargs['region'] == 'nan':
			regions = get_data(parameter='venue', 
							   previous_parameters={'venue':'in-person'},
							  )
			return JsonResponse({'regions':regions})
		elif self.kwargs['venue'] == 'online' and self.kwargs['region'] == 'nan':
			regions = get_data(parameter='venue', 
		      				   previous_parameters={'venue':'online'},
							   )
			return JsonResponse({'regions':regions})
		elif kwargs['region'] != 'nan' and kwargs['day'] == 'nan':
			days = get_data(parameter='region', 
								previous_parameters={'venue':self.kwargs['venue'],
													'region':self.kwargs['region']}
								)
			return JsonResponse({'days':days})
		elif kwargs['day'] != 'nan':
			meetings = get_data(parameter='day', 
								previous_parameters={'venue':self.kwargs['venue'],
													'region':self.kwargs['region'],
													'day':self.kwargs['day']}
								)
			if len(meetings) == 0:
				return JsonResponse({'meetings':'NO MEETINGS'})
			else:
				# Pass pretty and cleaned html table
				return JsonResponse({'meetings':format_table(meetings)})
		else:
			raise ProcessingError(f"Invalid request: {request}")



picker = Picker.as_view()

