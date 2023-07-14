
meeting_format_query = """
-- Meeting formats:
select shared_id_bigint, name_string from `na_comdef_formats`
where lang_enum = 'en';
"""

meeting_main_query = """
-- Meetings main:
select id_bigint,
 	weekday_tinyint,
    start_time,
    duration_time,
    formats,
    longitude,
	latitude
from `na_comdef_meetings_main` 
where published = 1 order by id_bigint asc;
"""

"""
/*
distinct field_prompt values:

Meeting Name
Town
Nation
Comments
Phone Meeting Dial-in Number
Virtual Meeting Link
Location Name
Street Address
Additional Location Information
Borough
Neighborhood
Zip Code
Virtual Meeting Additional Info
County
Bus Lines
Train Lines
Contact 1 Email
*/
"""

meeting_data_query = """
-- Meetings details:
select meetingid_bigint as id_bigint,
    field_prompt,
    data_string,
    data_bigint,
    data_double
from `na_comdef_meetings_data`
where meetingid_bigint <> 0 
order by meetingid_bigint asc,
    id asc;
"""