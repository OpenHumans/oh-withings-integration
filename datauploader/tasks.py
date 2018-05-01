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
    userid = nokia_member['userid']
    oauth_token = nokia_member['oauth_token']
    oauth_token_secret = nokia_member['oauth_token_secret']
    # # Fetch user's existing data from OH
    # # We are going to use the pip package open-humans-api for this
    # nokia_data = get_existing_nokia(oh_user.access_token)

    nokia_urls = [
        {'name': 'activity',
         'url': 'https://api.health.nokia.com/v2/measure?action=getactivity',
         'period': ''},
        {'name': 'measure',
         'url': 'https://api.health.nokia.com' +
                '/measure?action=getmeas&userid=' + str(userid),
         'period': ''},
        {'name': 'intraday',
         'url': 'https://api.health.nokia.com' +
                '/v2/measure?action=getintradayactivity',
         'period': ''},
        {'name': 'sleep',
         'url': 'https://api.health.nokia.com/v2/sleep?' +
                'action=get&startdate=1387234800&enddate=1387258800' +
                str(userid),
         'period': ''},
        {'name': 'sleep_summary',
         'url': 'https://api.health.nokia.com' +
                '/v2/sleep?action=getsummary',
         'period': ''},
        {'name': 'workouts',
         'url': 'https://api.health.nokia.com' +
                '/v2/measure?action=getworkouts',
         'period': ''}
    ]

    queryoauth = OAuth1(client_key=settings.NOKIA_CONSUMER_KEY,
                        client_secret=settings.NOKIA_CONSUMER_SECRET,
                        resource_owner_key=oauth_token,
                        resource_owner_secret=oauth_token_secret,
                        signature_type='query')

    dataarray = []
    for url in nokia_urls:
        thisfetch = rr.get(url=url['url'], auth=queryoauth, realms=["Nokia"])
        dataarray.append(thisfetch.text)

    datastring = combine_nh_data(dataarray)
    print(datastring)
    return datastring


def combine_nh_data(dataarray):
    """
    Combine Nokia Health data for all endpoints (activity, measure, intraday,
    sleep, sleep summary, workouts) into a single string.
    """
    endpoints = ['"activity":', ',"measure":', ',"intraday":',
                 ',"sleep":', ',"sleepsummary":', ',"workouts":']

    datastring = '{'
    for i in range(0, len(endpoints)-1):
        datastring += endpoints[i] + dataarray[i]

    datastring += '}'
    return datastring


def get_existing_nokia(oh_access_token):
    member = api.exchange_oauth2_member(oh_access_token)
    for dfile in member['data']:
        if 'nokiahealth' in dfile['metadata']['tags']:
            # get file here and read the json into memory
            tf_in = tempfile.NamedTemporaryFile(suffix='.json')
            tf_in.write(requests.get(dfile['download_url']).content)
            tf_in.flush()
            nokia_data = json.load(open(tf_in.name))
            return nokia_data
    print("NOKIA DATA:")
    return []


@shared_task
def xfer_to_open_humans(user_data, metadata, oh_id, num_submit=0, **kwargs):
    """
    Transfer data to Open Humans.
    num_submit is an optional parameter in case you want to resubmit failed
    tasks (see comments in code).
    """

    logger.debug('Trying to copy data for {} to Open Humans'.format(oh_id))

    oh_member = OpenHumansMember.objects.get(oh_id=oh_id)

    # Make a tempdir for all temporary files.
    # Delete this even if an exception occurs.
    tempdir = tempfile.mkdtemp()
    try:
        add_data_to_open_humans(user_data, metadata, oh_member, tempdir)
    finally:
        shutil.rmtree(tempdir)

    # Note: Want to re-run tasks in case of a failure?
    # You can resubmit a task by calling it again. (Be careful with recursion!)
    # e.g. to give up, resubmit, & try again after 10s if less than 5 attempts:
    # if num_submit < 5:
    #     num_submit += 1
    #     xfer_to_open_humans.apply_async(
    #         args=[oh_id, num_submit], kwargs=kwargs, countdown=10)
    #     return


def add_data_to_open_humans(user_data, metadata, oh_member, tempdir):
    """
    Add demonstration file to Open Humans.
    This might be a good place to start editing, to add your own project data.
    This template is written to provide the function with a tempdir that
    will be cleaned up later. You can use the tempdir to stage the creation of
    files you plan to upload to Open Humans.
    """
    # Create data file.
    data_filepath, data_metadata = make_datafile(user_data, metadata, tempdir)

    # Remove any files with this name previously added to Open Humans.
    delete_oh_file_by_name(oh_member, filename=os.path.basename(data_filepath))

    # Upload this file to Open Humans.
    upload_file_to_oh(oh_member, data_filepath, data_metadata)


def make_datafile(user_data, metadata, tempdir):
    """
    Make a user data file in the tempdir.
    """
    filename = 'user_data_' + datetime.today().strftime('%Y%m%d')
    filepath = os.path.join(tempdir, filename)

    with open(filepath, 'w') as f:
        f.write(user_data)

    return filepath, metadata


def delete_oh_file_by_name(oh_member, filename):
    """
    Delete all project files matching the filename for this Open Humans member.
    This deletes files this project previously added to the Open Humans
    member account, if they match this filename. Read more about file deletion
    API options here:
    https://www.openhumans.org/direct-sharing/oauth2-data-upload/#deleting-files
    """
    req = requests.post(
        settings.OH_DELETE_FILES,
        params={'access_token': oh_member.get_access_token()},
        data={'project_member_id': oh_member.oh_id,
              'file_basename': filename})
    req.raise_for_status()


def upload_file_to_oh(oh_member, filepath, metadata):
    """
    This demonstrates using the Open Humans "large file" upload process.
    The small file upload process is simpler, but it can time out. This
    alternate approach is required for large files, and still appropriate
    for small files.
    This process is "direct to S3" using three steps: 1. get S3 target URL from
    Open Humans, 2. Perform the upload, 3. Notify Open Humans when complete.
    """
    # Get the S3 target from Open Humans.
    upload_url = '{}?access_token={}'.format(
        settings.OH_DIRECT_UPLOAD, oh_member.get_access_token())
    req1 = requests.post(
        upload_url,
        data={'project_member_id': oh_member.oh_id,
              'filename': os.path.basename(filepath),
              'metadata': json.dumps(metadata)})
    req1.raise_for_status()

    # Upload to S3 target.
    with open(filepath, 'rb') as fh:
        req2 = requests.put(url=req1.json()['url'], data=fh)
    req2.raise_for_status()

    # Report completed upload to Open Humans.
    complete_url = ('{}?access_token={}'.format(
        settings.OH_DIRECT_UPLOAD_COMPLETE, oh_member.get_access_token()))
    req3 = requests.post(
        complete_url,
        data={'project_member_id': oh_member.oh_id,
              'file_id': req1.json()['id']})
    req3.raise_for_status()

    logger.debug('Upload done: "{}" for member {}.'.format(
            os.path.basename(filepath), oh_member.oh_id))
