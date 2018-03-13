import logging
import requests
import secrets

from django.contrib.auth import login
from django.shortcuts import render, redirect
from django.conf import settings
from datauploader.tasks import xfer_to_open_humans
from open_humans.models import OpenHumansMember

# Set up logging.
logger = logging.getLogger(__name__)


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

    # Use the token key and secret to perform end-user authorization.
    token_key = request.GET.get('oauth_token', '')
    token_secret = request.GET.get('oauth_token_secret', '')

    access_token = nokia_get_access_token(key=token_key, secret=token_secret)

    # Initiate a data transfer task, then render `complete.html`.
    xfer_to_open_humans.delay(oh_id=oh_member.oh_id,
                              nokia_id=nokia_member.nokia_id)

    return render(request, 'main/complete_nokia.html')


def complete(request):
    """
    Receive user from Open Humans and store it.
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

        nokia_oauth_timestamp = int(time.time())
        nokia_oauth_nonce = create_nokia_nonce()
        nokia_oauth_signature = create_nokia_oauth_signature()

        # Render `complete.html`.
        context = {'oh_id': oh_member.oh_id,
                   'oh_proj_page': settings.OH_ACTIVITY_PAGE,
                   'nokia_consumer_key': settings.NOKIA_CONSUMER_KEY,
                   'nokia_callback_url': settings.NOKIA_CALLBACK_URL,
                   'nokia_oauth_nonce': nokia_oauth_nonce,
                   'nokia_oauth_signature': nokia_oauth_signature,
                   'nokia_oauth_timestamp': nokia_oauth_timestamp
                   }
        return render(request, 'main/complete.html',
                      context=context)

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


def create_nokia_nonce(length=8):
    secrets.token_hex(length)


def nokia_get_access_token(key, secret):
    """
    Exchange key and secret for access token.
    """
    https://developer.health.nokia.com/account/access_token
    ?oauth_consumer_key={{ NOKIA_CONSUMER_KEY }}
    &oauth_nonce={{ NOKIA_OAUTH_NONCE }}
    &oauth_signature={{ NOKIA_OAUTH_SIGNATURE }}
    &oauth_signature_method=HMAC-SHA1
    &oauth_timestamp={{ NOKIA_OAUTH_TIMESTAMP }}
    &oauth_token=808976772931d191e2cb5229472f41cfe87c1df04d67478e7866f50e173
    &oauth_version=1.0
