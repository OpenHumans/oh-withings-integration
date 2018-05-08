"""
Asynchronous tasks that update data in Open Humans.
These tasks:
  1. delete any current files in OH if they match the planned upload filename
  2. adds a data file
"""
import logging
import os
import json
import shutil
import tempfile
import requests
import arrow
import time
import ast
import dateutil.parser as dp

from celery import shared_task
from django.conf import settings
from requests_oauthlib import OAuth1
from open_humans.models import OpenHumansMember
from datetime import datetime, timedelta
from nokia.settings import rr
from requests_respectful import RequestsRespectfulRateLimitedError
from ohapi import api


# Set up logging.
logger = logging.getLogger(__name__)


@shared_task
def process_nokia(oh_id):
    '''
    Fetch all nokia health data for a given user
    '''
    print('Entering process_nokia function')
    oh_member = OpenHumansMember.objects.get(oh_id=oh_id)
    oh_access_token = oh_member.get_access_token(
                            client_id=settings.OPENHUMANS_CLIENT_ID,
                            client_secret=settings.OPENHUMANS_CLIENT_SECRET)

    nokia_data = get_existing_nokia(oh_access_token)
    nokia_member = oh_member.nokia_member
    userid = nokia_member.userid
    oauth_token = nokia_member.oauth_token
    oauth_token_secret = nokia_member.oauth_token_secret
    print(userid)
    queryoauth = OAuth1(client_key=settings.NOKIA_CONSUMER_KEY,
                        client_secret=settings.NOKIA_CONSUMER_SECRET,
                        resource_owner_key=oauth_token,
                        resource_owner_secret=oauth_token_secret,
                        signature_type='query')

    print('Calling update_nokia function')
    update_nokia(oh_member, userid, queryoauth, nokia_data)


def update_nokia(oh_member, userid, queryoauth, nokia_data):
    oh_access_token = oh_member.get_access_token(
                            client_id=settings.OPENHUMANS_CLIENT_ID,
                            client_secret=settings.OPENHUMANS_CLIENT_SECRET)
    try:
        # Set start date and end date for data fetch
        start_time = get_start_time(oh_access_token, nokia_data)
        start_ymd = start_time.strftime('%Y-%m-%d')
        start_epoch = start_time.strftime('%s')

        stop_time = datetime.utcnow() + timedelta(days=7)
        stop_ymd = stop_time.strftime('%Y-%m-%d')
        stop_epoch = stop_time.strftime('%s')

        while start_ymd != stop_ymd:
            nokia_urls = [
                {'name': 'activity',
                 'url': 'https://api.health.nokia.com/v2/' +
                        'measure?action=getactivity&userid=' + str(userid) +
                        '&startdateymd=' + str(start_ymd) + '&enddateymd=' +
                        str(stop_ymd)},
                {'name': 'measure',
                 'url': 'https://api.health.nokia.com' +
                        '/measure?action=getmeas&userid=' + str(userid) +
                        '&startdate=' + str(start_epoch) + '&enddate=' +
                        str(stop_epoch)},
                {'name': 'intraday',
                 'url': 'https://api.health.nokia.com' +
                        '/v2/measure?action=getintradayactivity' +
                        str(userid) + '&startdate=' + str(start_epoch) +
                        '&enddate=' + str(stop_epoch)},
                {'name': 'sleep',
                 'url': 'https://api.health.nokia.com/v2/sleep?' +
                        'action=get&startdate=' + str(start_epoch) +
                        '&enddate=' + str(stop_epoch) + '&userid=' +
                        str(userid)},
                {'name': 'sleep_summary',
                 'url': 'https://api.health.nokia.com' +
                        '/v2/sleep?action=getsummary&startdateymd=' +
                        str(start_ymd) + '&enddateymd=' + str(stop_ymd)},
                {'name': 'workouts',
                 'url': 'https://api.health.nokia.com' +
                        '/v2/measure?action=getworkouts&userid=' +
                        str(userid) + '&startdateymd=' + str(start_ymd) +
                        '&enddateymd=' + str(stop_ymd)}
            ]

            for i in range(0, len(nokia_urls)-1):
                endpoint = nokia_urls[i]
                keyname = endpoint['name']
                print('url for {}'.format(keyname))
                print(endpoint['url'])
                thisfetch = rr.get(url=endpoint['url'], auth=queryoauth,
                                   realms=["Nokia"])
                # print(thisfetch.text)
                if keyname in nokia_data.keys():
                    print("Adding to existing")
                    # If this data type already exists, append to it.
                    print(nokia_data[keyname])
                    print(type(nokia_data[keyname]))
                    nokia_data[keyname].append(thisfetch.text)
                else:
                    print("Creating new endpoint array for {}".format(keyname))
                    # If this data type does not exist, create the key.
                    nokia_data[keyname] = [thisfetch.text]

    except RequestsRespectfulRateLimitedError:
        print('Hit limit requeue request')
        logger.debug(
            'Requeued processing for {} with 60s delay'.format(
                oh_member.oh_id)
        )
        # process_nokia.apply_async(args=[oh_member.oh_id], countdown=61)
    finally:
        replace_nokia(oh_member, nokia_data)


def replace_nokia(oh_member, nokia_data):
    """
    Delete any old file and upload new
    """
    print(nokia_data)
    tmp_directory = tempfile.mkdtemp()
    metadata = {
        'tags': ['nokia', 'health', 'measure'],
        'description': 'File with Nokia Health data',
        'updated_at': str(datetime.utcnow()),
    }
    filename = 'nokia_data_' + datetime.today().strftime('%Y%m%d')
    out_file = os.path.join(tmp_directory, filename)
    logger.debug('deleted old file for {}'.format(oh_member.oh_id))
    api.delete_file(oh_member.access_token,
                    oh_member.oh_id,
                    file_basename=filename)
    with open(out_file, 'w') as json_file:
        json.dump(nokia_data, json_file)
        json_file.flush()
    api.upload_aws(out_file, metadata,
                   oh_member.access_token,
                   project_member_id=oh_member.oh_id)
    logger.debug('uploaded new file for {}'.format(oh_member.oh_id))


def get_existing_nokia(oh_access_token):
    member = api.exchange_oauth2_member(oh_access_token)
    print(member)
    for dfile in member['data']:
        if 'nokia' in dfile['metadata']['tags']:
            # get file here and read the json into memory
            tf_in = tempfile.NamedTemporaryFile(suffix='.json')
            tf_in.write(requests.get(dfile['download_url']).content)
            tf_in.flush()
            nokia_data = json.load(open(tf_in.name))
            print("getting existing data:")
            print(type(nokia_data))
            return nokia_data
    return {}


def get_start_time(oh_access_token, nokia_data):
    """
    Look at existing nokia data and find out the last date it was fetched
    for. Start by looking at activity and then measure endpoints.
    """
    try:
        # If there is activity data, proceed to check whether it has a date.
        activity_data = nokia_data["activity"][0]
        activity_data = activity_data.replace("true", "True")
        activity_data = activity_data.replace("false", "False")
        activity_data = ast.literal_eval(activity_data)
        date_ymd = activity_data["body"]["activities"][0]["date"]
        date_parsed = dp.parse(date_ymd)
        return date_parsed
    except:
        try:
            # If there is measure data, proceed to check whether it has a date.
            measure_data = nokia_data["measure"][0]
            measure_data = measure_data.replace("true", "True")
            measure_data = measure_data.replace("false", "False")
            measure_data = ast.literal_eval(measure_data)
            date_epoch = measure_data["body"]["updatetime"]
            date_struct = time.localtime(date_epoch)
            date_parsed = datetime.datetime(*date_struct[:3])
            return date_parsed
        except:
            # If we can't get a date from activity or measure endpoints, just
            # use the 2009 which is when Withings began.
            print("No existing nokia data, using 2009, when Withings began")
            start_time = '2009-01-01'
            date_parsed = dp.parse(start_time)
            return date_parsed
