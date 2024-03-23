import calendar
from pandas import (DataFrame,
					Series,
					read_csv,
					)
from pandas import options as pandas_options
from datetime import datetime
from requests import request
from typing import List, Union

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.generic import ListView
from dotenv import load_dotenv, find_dotenv

from meetingpicker.apps.picker.models import PickerModel


#Filter pandas warning about using a mysql connection directly
from warnings import filterwarnings
filterwarnings('ignore', category=UserWarning)
pandas_options.mode.copy_on_write = True

#Load environment variables from file (db connection parameters)
load_dotenv(find_dotenv('../.env'), override=True)

ALL_MEETINGS = read_csv('data/all_meetings.csv')
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
REGION_ORDERED = {"Auckland" : 1,
				"Christchurch and Canterbury" : 2,
				"Dunedin, Otago and Southland" : 3,
				"Hamilton and Waikato" : 4,
				"Wellington" : 5,
				"Hutt Valley and Masterton" : 6,
				"Northland" : 7,
				"Hawke's Bay and Gisborne" : 8,
				"Tauranga and Rotorua" : 9,
				"Upper South Island" : 10,
				"Taranaki" : 11,
				"Palmerston North and Whanganui" : 12,
				"Porirua and Kapiti Coast" : 13,
				"West Coast - South Island" : 14,
				}


class ProcessingError(Exception):
	 pass  


def format_table(mtgs:DataFrame) -> str:
	"""Take table of meetings and format for display.

	Args:
		mtgs (DataFrame): DataFrame of meetings

	Returns:
		DataFrame: table for display
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
	# Re-sort by day, then seconds into each day (for time)
	mtgs['Ordering'] = mtgs.apply(lambda x: str(DAYS_ORDERED.get(x['Day'], 9999)) + \
								 	str( int( (datetime.strptime(x['Start Time'], '%I:%M %p')\
									- datetime(1900,1,1)).total_seconds() ) ), axis=1)
	mtgs.sort_values(by='Ordering', inplace=True)
	mtgs.drop('Ordering', axis=1, inplace=True)
	#Format Table as HTML table for display
	mtgs = mtgs.to_html(classes='table table-striped table-bordered table-hover', table_id='mtgs',
		     			index=False, escape=False, render_links=True)	
	return mtgs

	
def sort_on_day(series:Series) -> Series:
	"""Sort a series of days in order of the week, starting with the current day.

	Args:
		series (Series): Pandas series

	Returns:
		Series: Pandas series, sorted
	"""
	return series.apply(lambda x: DAYS_ORDERED.get(x, 9999))


def sort_on_region(series:Series) -> Series:
	"""Sort a series of regions.

	Args:
		series (Series): Pandas series

	Returns:
		Series: Pandas series, sorted
	"""
	return series.apply(lambda x: REGION_ORDERED.get(x, 9999))


def get_data(parameter:str = None,
		     previous_parameters:Union[dict, str, int] = {}) -> Union[list, DataFrame]:
	"""
	Method to retrieve a table of meeting information, given a set of parameters to 
	filter the data with.
	
	Args:
	
	parameter (str): this specific parameter/level of user query 
	previous_parameters List[list, dict, str, int]: List of all parameters provided
	
	Returns:
	
	DataFrame: table of meeting information 
	
	"""
	# Create database conn and pull meeting data 
	if parameter == 'venue':
		if previous_parameters['venue'] == 'in-person':
			#Filter to just in-person meetings
			meetings = ALL_MEETINGS.loc[ALL_MEETINGS['venue'].isin(['in-person', 'hybrid'])]
			if len(meetings) == 0:
				return ['NONE']
			meetings.sort_values(by='Day', key=sort_on_day, inplace=True)
			regions = meetings.groupby('region').count().reset_index()\
			                  .sort_values(by='region', key=sort_on_region)
			return ['SHOW ALL'] + regions.region.values.tolist()
		elif previous_parameters['venue'] == 'online':
			#Filter to just online meetings
			meetings = ALL_MEETINGS.loc[ALL_MEETINGS['venue'].isin(['online', 'hybrid'])]
			meetings.sort_values(by='Day', key=sort_on_day, inplace=True)
			regions = meetings.groupby('region').count().reset_index()\
			                  .sort_values(by='region', key=sort_on_region)
			return ['SHOW ALL'] + regions.region.values.tolist()
		else:
			raise ValueError('Invalid venue parameter')
	elif parameter == 'region':
		this_region = previous_parameters['region'].replace('__', "'")\
												   .replace('_', ' ')
		if previous_parameters['venue'] == 'in-person':
			#Filter to just meetings in the region
			if previous_parameters['region'] == 'SHOW ALL':
				meetings = ALL_MEETINGS
			else:
				meetings = ALL_MEETINGS.loc[ALL_MEETINGS['region'] == this_region]
			meetings.sort_values(by='Day', key=sort_on_day, inplace=True)
			days = meetings.Day.unique().tolist()
			return ['SHOW ALL'] + days
		elif previous_parameters['venue'] == 'online':
			meetings = ALL_MEETINGS.loc[ALL_MEETINGS['venue'].isin(['online', 'hybrid'])]
			meetings.sort_values(by='Day', key=sort_on_day, inplace=True)
			days = meetings.Day.unique().tolist()
			return ['SHOW ALL'] + days
		else:
			raise ValueError('Invalid venue parameter')
	elif parameter == 'day':
		this_region = previous_parameters['region'].replace('__', "'")\
												   .replace('_', ' ')
		if previous_parameters['region'] == 'SHOW ALL':
			if previous_parameters['venue'] == 'online':
				meetings = ALL_MEETINGS.loc[ALL_MEETINGS['venue'].isin(['online', 'hybrid'])]
			elif previous_parameters['venue'] == 'in-person':
				meetings = ALL_MEETINGS.loc[ALL_MEETINGS['venue'].isin(['in-person', 'hybrid'])]
			else:
				raise ValueError('Invalid venue parameter')
			#Filter to just meetings on a given day
			if not previous_parameters['day'] == 'SHOW ALL':
				meetings = meetings.loc[meetings['Day'] == previous_parameters['day']]
			#meetings.sort_values(by='Day', key=sort_on_day, inplace=True)
			return meetings
		else:
			if previous_parameters['day'] == 'SHOW ALL':
				if previous_parameters['venue'] == 'online':
					meetings = ALL_MEETINGS.loc[ALL_MEETINGS['venue'].isin(['online', 'hybrid'])]
				elif previous_parameters['venue'] == 'in-person':
					meetings = ALL_MEETINGS.loc[ALL_MEETINGS['venue'].isin(['in-person', 'hybrid'])]
				else:
					raise ValueError('Invalid venue parameter')
				meetings.sort_values(by='Day', key=sort_on_day, inplace=True)
				return meetings
			else:
				if previous_parameters['venue'] == 'online':
					meetings = ALL_MEETINGS.loc[ALL_MEETINGS['venue'].isin(['online', 'hybrid'])]
				elif previous_parameters['venue'] == 'in-person':
					meetings = ALL_MEETINGS.loc[ALL_MEETINGS['venue'].isin(['in-person', 'hybrid'])]
				else:
					raise ValueError('Invalid venue parameter')
				#Filter to just meetings in the region
				meetings = meetings.loc[meetings['Day'] == previous_parameters['day']]
				#Filter to just meetings in the region
				meetings = meetings.loc[meetings.region == this_region]
				meetings.sort_values(by='Day', key=sort_on_day, inplace=True)
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

