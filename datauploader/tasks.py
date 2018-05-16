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
    update_nokia(oh_member, userid, queryoauth, nokia_data, oauth_token)


def update_nokia(oh_member, userid, queryoauth, nokia_data, oauth_token):
    oh_access_token = oh_member.get_access_token(
                            client_id=settings.OPENHUMANS_CLIENT_ID,
                            client_secret=settings.OPENHUMANS_CLIENT_SECRET)
    try:
        # Set start date and end date for data fetch
        start_time = get_start_time(oh_access_token, nokia_data, queryoauth,
                                    oauth_token)
        start_ymd = start_time.strftime('%Y-%m-%d')

        start_epoch = start_time.strftime('%s')
        stop_time = datetime.utcnow() + timedelta(days=7)
        stop_ymd = stop_time.strftime('%Y-%m-%d')
        stop_epoch = stop_time.strftime('%s')

        print('processing {} - {} for member {}'.format(start_ymd,
                                                        stop_ymd,
                                                        oh_member.oh_id))
        nokia_urls = [
            {'name': 'activity',
             'url': 'https://api.health.nokia.com/v2/' +
                    'measure?action=getactivity&userid=' + str(userid) +
                    '&startdateymd=' + str(start_ymd) +
                    '&enddateymd=' + str(stop_ymd)},
            {'name': 'measure',
             'url': 'https://api.health.nokia.com' +
                    '/measure?action=getmeas&userid=' + str(userid) +
                    '&startdate=' + str(start_epoch) +
                    '&enddate=' + str(stop_epoch)},
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
        for i in range(0, len(nokia_urls)):
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
                # print(nokia_data[keyname])
                print(type(nokia_data[keyname]))
                nokia_data[keyname].append(thisfetch.text)
            else:
                print("Creating new endpoint array for {}".format(keyname))
                # If this data type does not exist, create the key.
                nokia_data[keyname] = [thisfetch.text]
        print("start_ymd: {} stop_ymd: {}".format(start_ymd, stop_ymd))
        start_time = stop_time + timedelta(days=1)
        start_ymd = start_time.strftime('%Y-%m-%d')
        start_epoch = start_time.strftime('%s')
        stop_time = stop_time + timedelta(days=8)
        stop_ymd = stop_time.strftime('%Y-%m-%d')
        stop_epoch = stop_time.strftime('%s')
        print("start_ymd: {} stop_ymd: {}".format(start_ymd, stop_ymd))

    except RequestsRespectfulRateLimitedError:
        print('Hit limit requeue request')
        logger.debug(
            'Requeued processing for {} with 60s delay'.format(
                oh_member.oh_id)
        )
        process_nokia.apply_async(args=[oh_member.oh_id], countdown=61)
    finally:
        replace_nokia(oh_member, nokia_data)


def replace_nokia(oh_member, nokia_data):
    """
    Delete any old file and upload new
    """
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
    print("Entering get_existing_nokia function...")
    member = api.exchange_oauth2_member(oh_access_token)
    for dfile in member['data']:
        if 'nokia' in dfile['metadata']['tags']:
            print("Found file with tag...")
            # get file here and read the json into memory
            tf_in = tempfile.NamedTemporaryFile(suffix='.json')
            tf_in.write(requests.get(dfile['download_url']).content)
            tf_in.flush()
            nokia_data = json.load(open(tf_in.name))
            print("getting existing data:")
            print(type(nokia_data))
            for key in nokia_data:
                print(key)
            return nokia_data
    print('no existing data with nokia tag')
    return {}


def get_start_time(oh_access_token, nokia_data, queryoauth, oauth_token):
    """
    Look at existing nokia data and find out the last date it was fetched
    for. Start by looking at activity and then measure endpoints.
    """

    if nokia_data != {}:
        # If there is existing data, start from the most recent date.
        try:
            # If there is activity data, check whether it has a date
            activity_data = nokia_data["activity"][-1]
            activity_data = activity_data.replace("true", "True")
            activity_data = activity_data.replace("false", "False")
            activity_data = ast.literal_eval(activity_data)

            date_ymd = activity_data["body"]["activities"][-1]["date"]
            date_parsed = dp.parse(date_ymd)

            print("setting start date {} from existing activity data".format(date_parsed))
            return date_parsed
        except:
            print("Couldn't get date from activity... trying with measure")
            try:
                # If there is measure data, check whether it has a date
                measure_data = nokia_data["measure"][-1]
                measure_data = measure_data.replace("true", "True")
                measure_data = measure_data.replace("false", "False")
                measure_data = ast.literal_eval(measure_data)

                date_epoch = measure_data["body"]["updatetime"]
                date_struct = time.localtime(date_epoch)
                date_parsed = datetime.datetime(*date_struct[:3])

                print("setting start date {} from existing measure data".format(date_parsed))
                return date_parsed
            except:
                print("Couldn't get date from measure... using member since")


    infourl = 'https://api.health.nokia.com/user?action=getinfo&access_token=' + str(oauth_token)
    userinfo = rr.get(url=infourl, auth=queryoauth, realms=["Nokia"])
    userinfo = userinfo.text
    userinfo = ast.literal_eval(userinfo)
    print("userinfo: {}".format(userinfo))
    userinfobody = userinfo["body"]
    print("userinfobody: {}".format(userinfobody))
    userinfobodyuser = userinfobody["user"]
    print("userinfobodyuser: {}".format(userinfobodyuser))
    member_since = userinfobodyuser["created"]
    print("member_since: {}".format(member_since))
    member_since_struct = time.localtime(member_since)
    print("member_since_struct: {}".format(member_since_struct))
    member_since_parsed = datetime(*member_since_struct[:3])
    print("member_since_parsed: {}".format(member_since_parsed))

    return member_since_parsed
