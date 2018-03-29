import logging
import requests

from django.contrib.auth import login
from django.shortcuts import render, redirect
from django.conf import settings
from datauploader.tasks import xfer_to_open_humans
from requests_oauthlib import OAuth1
from urllib.parse import parse_qs
from open_humans.models import OpenHumansMember
from .models import NokiaHealthMember

# Set up logging.
logger = logging.getLogger(__name__)

# OAuth1 for Nokia Health
# Credentials obtained during the registration.
client_key = settings.NOKIA_CONSUMER_KEY
client_secret = settings.NOKIA_CONSUMER_SECRET
callback_uri = settings.NOKIA_CALLBACK_URL
oh_proj_page = settings.OH_ACTIVITY_PAGE

# Endpoints found in the OAuth provider API documentation
request_token_url = 'https://developer.health.nokia.com/account/request_token'
authorization_url = 'https://developer.health.nokia.com/account/authorize'
access_token_url = 'https://developer.health.nokia.com/account/access_token'


def index(request):
    """
    Starting page for app.
    """

    context = {'client_id': settings.OPENHUMANS_CLIENT_ID,
               'oh_proj_page': settings.OH_ACTIVITY_PAGE}

    return render(request, 'main/index.html', context=context)


def complete_nokia(request):
    """
    Receive user data from Nokia Health, store it, and start upload.
    """
    logger.debug("Received user returning from Nokia Health")

    # Get the "verifier" out of the redirected URL
    verifier = request.GET['oauth_verifier']

    # Create a new OAuth1 object using the resource owner key/secret
    # from session data and using the verifier parsed from the URL (above)
    oauth = OAuth1(client_key,
                   client_secret=client_secret,
                   resource_owner_key=request.session['resource_owner_key'],
                   resource_owner_secret=request.
                   session['resource_owner_secret'],
                   verifier=verifier)

    # Make a request to Nokia (final request) for an access token
    r = requests.post(url=access_token_url, auth=oauth)
    print(r.text)
    credentials = parse_qs(r.text)
    print(request.user)

    # next steps: parse and store Nokia OAuth tokens

    # 4. (not done) Trigger fetch data task & upload

    oauth_token = credentials.get('oauth_token')[0]
    oauth_token_secret = credentials.get('oauth_token_secret')[0]
    userid = credentials.get('userid')[0]
    deviceid = credentials.get('deviceid')[0]

    oh_id=request.user.oh_member.oh_id
    oh_user = OpenHumansMember.objects.get(oh_id=oh_id)

    nokia_member = NokiaHealthMember.objects.get_or_create(
        user=oh_user,
        userid=userid,
        deviceid=deviceid,
        oauth_token=oauth_token,
        oauth_token_secret=oauth_token_secret)

    activity_url = "https://api.health.nokia.com/v2/measure?action=getactivity"
    meas_url = 'https://api.health.nokia.com/measure?action=getmeas&userid=' + str(userid)
    intraday_url = 'https://api.health.nokia.com/v2/measure?action=getintradayactivity'
    sleep_url = 'https://api.health.nokia.com/v2/sleep?action=get&startdate=1387234800&enddate=1387258800' + str(userid)
    sleep_summary_url = 'https://api.health.nokia.com/v2/sleep?action=getsummary'
    workouts_url = 'https://api.health.nokia.com/v2/measure?action=getworkouts'

    queryoauth = OAuth1(client_key,
                        client_secret=client_secret,
                        resource_owner_key=oauth_token,
                        resource_owner_secret=oauth_token_secret,
                        signature_type='query')

    r_activity = requests.get(url=activity_url, auth=queryoauth)
    r_meas = requests.get(url=meas_url, auth=queryoauth)
    r_intraday = requests.get(url=intraday_url, auth=queryoauth)
    r_sleep = requests.get(url=sleep_url, auth=queryoauth)
    r_sleep_summary = requests.get(url=sleep_summary_url, auth=queryoauth)
    r_workouts = requests.get(url=workouts_url, auth=queryoauth)

    print("Activity:")
    print(r_activity.text)
    print("Measure:")
    print(r_meas.text)
    print("Intraday:")
    print(r_intraday.text)
    print("Sleep:")
    print(r_sleep.text)
    print("Sleep Summary:")
    print(r_sleep_summary.text)
    print("Workouts:")
    print(r_workouts.text)

    xfer_to_open_humans.delay(r_meas.text, oh_id=oh_id)

    context = {'tokeninfo': 'thanks for linking Nokia! Fetching data...',
               'oh_proj_page': oh_proj_page}
    return render(request, 'main/complete_nokia.html', context=context)


def complete(request):
    """
    Receive user from Open Humans and store.
    """
    logger.debug("Received user returning from Open Humans.")

    # Exchange code for token.
    # This creates an OpenHumansMember and associated user account.
    code = request.GET.get('code', '')
    oh_member = oh_code_to_member(code=code)

    if oh_member:
        # Log in the user.
        user = oh_member.user
        login(request, user,
              backend='django.contrib.auth.backends.ModelBackend')

        # Create an OAuth1 object, and obtain a request token
        oauth = OAuth1(client_key, client_secret=client_secret,
                       callback_uri=callback_uri)
        r = requests.post(url=request_token_url, auth=oauth)

        # Parse and save the resource owner key & secret (for use
        # in nokia_complete callback)
        credentials = parse_qs(r.text)
        request.session['resource_owner_key'] =\
            credentials.get('oauth_token')[0]
        request.session['resource_owner_secret'] =\
            credentials.get('oauth_token_secret')[0]

        # Generate the authorization URL
        authorize_url = authorization_url + '?oauth_token='
        authorize_url = authorize_url + request.session['resource_owner_key']

        # Render `complete.html`.
        context = {'oh_id': oh_member.oh_id,
                   'oh_proj_page': settings.OH_ACTIVITY_PAGE,
                   "redirect_url": authorize_url,
                   'nokia_consumer_key': settings.NOKIA_CONSUMER_KEY,
                   'nokia_callback_url': settings.NOKIA_CALLBACK_URL,
                   }
        return render(request, 'main/complete.html', context=context)

    logger.debug('Invalid code exchange. User returned to starting page.')
    return redirect('/')


def oh_code_to_member(code):
    """
    Exchange code for token, use this to create and return OpenHumansMember.
    If a matching OpenHumansMember exists, update and return it.
    """
    if settings.OPENHUMANS_CLIENT_SECRET and \
       settings.OPENHUMANS_CLIENT_ID and code:
        data = {
            'grant_type': 'authorization_code',
            'redirect_uri':
            '{}/complete'.format(settings.OPENHUMANS_APP_BASE_URL),
            'code': code,
        }
        req = requests.post(
            '{}/oauth2/token/'.format(settings.OPENHUMANS_OH_BASE_URL),
            data=data,
            auth=requests.auth.HTTPBasicAuth(
                settings.OPENHUMANS_CLIENT_ID,
                settings.OPENHUMANS_CLIENT_SECRET
            )
        )
        data = req.json()

        if 'access_token' in data:
            oh_id = oh_get_member_data(
                data['access_token'])['project_member_id']
            try:
                oh_member = OpenHumansMember.objects.get(oh_id=oh_id)
                logger.debug('Member {} re-authorized.'.format(oh_id))
                oh_member.access_token = data['access_token']
                oh_member.refresh_token = data['refresh_token']
                oh_member.token_expires = OpenHumansMember.get_expiration(
                    data['expires_in'])
            except OpenHumansMember.DoesNotExist:
                oh_member = OpenHumansMember.create(
                    oh_id=oh_id,
                    access_token=data['access_token'],
                    refresh_token=data['refresh_token'],
                    expires_in=data['expires_in'])
                logger.debug('Member {} created.'.format(oh_id))
            oh_member.save()

            return oh_member

        elif 'error' in req.json():
            logger.debug('Error in token exchange: {}'.format(req.json()))
        else:
            logger.warning('Neither token nor error info in OH response!')
    else:
        logger.error('OH_CLIENT_SECRET or code are unavailable')
    return None


def oh_get_member_data(token):
    """
    Exchange OAuth2 token for member data.
    """
    req = requests.get(
        '{}/api/direct-sharing/project/exchange-member/'
        .format(settings.OPENHUMANS_OH_BASE_URL),
        params={'access_token': token}
        )
    if req.status_code == 200:
        return req.json()
    raise Exception('Status code {}'.format(req.status_code))
    return None
