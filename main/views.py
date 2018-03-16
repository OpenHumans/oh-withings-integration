import logging
import requests

from django.contrib.auth import login
from django.shortcuts import render, redirect
from django.conf import settings
from datauploader.tasks import xfer_to_open_humans
from requests_oauthlib import OAuth1Session
from open_humans.models import OpenHumansMember

# Set up logging.
logger = logging.getLogger(__name__)

# OAuth1 for Nokia Health
# Credentials obtained during the registration.
client_key = settings.NOKIA_CONSUMER_KEY
client_secret = settings.NOKIA_CONSUMER_SECRET
callback_uri = 'http://127.0.0.1:5000/complete_nokia'

# Endpoints found in the OAuth provider API documentation
request_token_url = 'https://developer.health.nokia.com/account/request_token'
authorization_url = 'https://developer.health.nokia.com/account/authorize'
access_token_url = 'https://developer.health.nokia.com/account/access_token'

oauth_session = OAuth1Session(client_key,client_secret=client_secret, callback_uri=callback_uri)

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

    # Nokia OAuth last handshake steps
    # Uses requests_oauthlib
    # 1. Get the full redirect path w/ code & verifier 
    # (ex. /complete_nokia?userid=xxxx&oauth_token=xxxx&oauth_verifier=xxxx)
    redirect_response = str(request.get_full_path())

    # 2. Parse the "fragment" from above (to separate the info in a dict)
    # Output ex: {'userid': 'xxx', 'oauth_token': 'xxxx', 'oauth_verifier': 'xxxx'}
    oauth_session.parse_authorization_response(redirect_response)

    # 3. Last leg, use the dict from previous line to get the actual access token
    # Output ex: {'oauth_token': 'xxxx', 'oauth_token_secret': 'xxxx', 'userid': 'xxxx', 'deviceid': 'xxxx'}
    tokeninfo = oauth_session.fetch_access_token(access_token_url)

    # 4. (not done) Trigger fetch data task & upload

    context = { "tokeninfo" : tokeninfo }
    return render(request, 'main/complete_nokia.html', context=context)


def complete(request):
    """
    Receive user from Open Humans and store it.
    """
    logger.debug("Received user returning from Open Humans.")

    # Exchange code for token.
    # This creates an OpenHumansMember and associated user account.
    # code = request.GET.get('code', '')
    # oh_member = oh_code_to_member(code=code)

    # if oh_member:
    #     # Log in the user.
    #     user = oh_member.user
    #     login(request, user,
    #           backend='django.contrib.auth.backends.ModelBackend')

    #     nokia_oauth_timestamp = create_nokia_timestamp()
    #     nokia_oauth_nonce = create_nokia_nonce()
    #     nokia_oauth_signature = create_nokia_oauth_signature()

    #     # Render `complete.html`.
    #     context = {'oh_id': oh_member.oh_id,
    #                'oh_proj_page': settings.OH_ACTIVITY_PAGE,
    #                'nokia_consumer_key': settings.NOKIA_CONSUMER_KEY,
    #                'nokia_callback_url': settings.NOKIA_CALLBACK_URL,
    #                'nokia_oauth_nonce': nokia_oauth_nonce,
    #                'nokia_oauth_signature': nokia_oauth_signature,
    #                'nokia_oauth_timestamp': nokia_oauth_timestamp
    #                }
    #     return render(request, 'main/complete.html',
    #                   context=context)

    # logger.debug('Invalid code exchange. User returned to starting page.')
    # return redirect('/')

    # Start OAuth1 handshake to generate authorization URL for user
    # 1. Fetch the request token.
    # Output ex: oauth_token=xxxx&oauth_token_secret=xxxx
    oauth_session.fetch_request_token(request_token_url)

    # 2. Generate link for user based on tokens from last line
    redirect_url = oauth_session.authorization_url(authorization_url)
    # Add Nokia Health Authorization URL to the context for the template
    context = { "redirect_url" : redirect_url }
    return render(request, 'main/complete.html', context=context)


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
