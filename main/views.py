import logging
import requests

from django.contrib.auth import login, logout
from django.shortcuts import render, redirect
from django.conf import settings
from datauploader.tasks import process_nokia
from django.contrib import messages
from requests_oauthlib import OAuth1
from urllib.parse import parse_qs
from open_humans.models import OpenHumansMember
from .helpers import get_nokia_file, check_update
from .models import NokiaHealthMember
from ohapi import api
import arrow


# Set up logging.
logger = logging.getLogger(__name__)

# Endpoints found in the OAuth provider API documentation
request_token_url = 'https://developer.health.nokia.com/account/request_token'
authorization_url = 'https://developer.health.nokia.com/account/authorize'


def index(request):
    """
    Starting page for app.
    """
    if request.user.is_authenticated:
        return redirect('/dashboard')
    else:
        context = {'client_id': settings.OPENHUMANS_CLIENT_ID,
                   'oh_proj_page': settings.OH_ACTIVITY_PAGE}

        return render(request, 'main/index.html', context=context)


def complete(request):
    """
    Receive user from Open Humans and store.
    """
    print("Received user returning from Open Humans.")

    # Exchange code for token.
    # This creates an OpenHumansMember and associated user account.
    code = request.GET.get('code', '')
    oh_member = oh_code_to_member(code=code)

    if oh_member:
        # Log in the user.
        user = oh_member.user
        login(request, user,
              backend='django.contrib.auth.backends.ModelBackend')

        context = {'oh_id': oh_member.oh_id,
                   'oh_proj_page': settings.OH_ACTIVITY_PAGE}

        if not hasattr(oh_member, 'nokia_member'):
            auth_url = 'https://account.withings.com/oauth2_user/authorize2?response_type=code&client_id='+settings.NOKIA_CLIENT_ID+'&scope=user.info,user.metrics,user.activity&redirect_uri='+str(settings.WITHINGS_REDIRECT_URI)+'&state=abc'
            context['auth_url'] = auth_url
            return render(request, 'main/complete.html', context=context)

        return redirect("/dashboard")

    logger.debug('Invalid code exchange. User returned to starting page.')
    return redirect('/')


def dashboard(request):
    if request.user.is_authenticated:
        if hasattr(request.user.oh_member, 'nokia_member'):
            nokia_member = request.user.oh_member.nokia_member
            download_file = get_nokia_file(request.user.oh_member)
            if download_file == 'error':
                logout(request)
                return redirect("/")
            connect_url = ''
            allow_update = check_update(nokia_member)
        else:
            allow_update = False
            nokia_member = ''
            download_file = ''

        # Generate the authorization URL
        auth_url = 'https://account.withings.com/oauth2_user/authorize2?response_type=code&client_id='+settings.NOKIA_CLIENT_ID+'&scope=user.info,user.metrics,user.activity&redirect_uri='+str(settings.WITHINGS_REDIRECT_URI)+'&state=abc'

        context = {
            'oh_member': request.user.oh_member,
            'nokia_member': nokia_member,
            'download_file': download_file,
            'connect_url': auth_url,
            'allow_update': allow_update
        }
        return render(request, 'main/dashboard.html',
                      context=context)
    return redirect("/")


def remove_nokia(request):
    if request.method == "POST" and request.user.is_authenticated:
        try:
            oh_member = request.user.oh_member
            api.delete_file(oh_member.access_token,
                            oh_member.oh_id,
                            file_basename="nokia_data")
            messages.info(request, "Your Withings/Nokia account has been removed")
            nokia_account = request.user.oh_member.nokia_member
            nokia_account.delete()
        except:
            nokia_account = request.user.oh_member.nokia_member
            nokia_account.delete()
            messages.info(request, ("Something went wrong, please"
                          "re-authorize us on Open Humans"))
            logout(request)
            return redirect('/')
    return redirect('/dashboard')


def update_data(request):
    if request.method == "POST" and request.user.is_authenticated:
        oh_member = request.user.oh_member
        process_nokia.delay(oh_member.oh_id)
        nokia_member = oh_member.nokia_member
        nokia_member.last_submitted = arrow.now().format()
        nokia_member.save()
        messages.info(request,
                      ("An update of your Withings / Nokia Health data has been started! "
                       "It can take a few minutes before the first data is "
                       "available. Reload this page in a while to find your "
                       "data"))
        return redirect('/dashboard')


def complete_nokia(request):
    """
    Receive user data from Withings/Nokia Health, store it, and start upload.
    """
    logger.debug("Received user returning from Withings/Nokia Health")

    code = request.GET['code']
    print(code)

    oh_id = request.user.oh_member.oh_id
    print(oh_id)
    oh_user = OpenHumansMember.objects.get(oh_id=oh_id)

    payload = {
        'code': code,
        'grant_type': 'authorization_code',
        'client_id': settings.NOKIA_CLIENT_ID,
        'client_secret': settings.NOKIA_CONSUMER_SECRET,
        'redirect_uri': settings.WITHINGS_REDIRECT_URI,
        'state': 'abc'
    }
    r = requests.post('https://account.withings.com/oauth2/token', payload)
    rjson = r.json()
    print(rjson)

    # Save the user 
    try:
        nokia_member = NokiaHealthMember.objects.get(userid=rjson['userid'])
        nokia_member.userid = rjson['userid']
        nokia_member.access_token = rjson['access_token']
        nokia_member.refresh_token = rjson['refresh_token']
        nokia_member.expires_in = rjson['expires_in']
        nokia_member.scope = rjson['scope']
        nokia_member.token_type = rjson['token_type']
        nokia_member.save()
    except NokiaHealthMember.DoesNotExist:
        nokia_member, created = NokiaHealthMember.objects.get_or_create(
            user=oh_user,
            userid=rjson['userid'],
            access_token=rjson['access_token'],
            refresh_token=rjson['refresh_token'],
            expires_in=rjson['expires_in'],
            scope=rjson['scope'],
            token_type=rjson['token_type'])

    if nokia_member:
        # Fetch user's data from Nokia (update the data if it already existed)
        process_nokia.delay(oh_id)
        context = {'tokeninfo': 'Fetching data...',
                   'oh_proj_page': settings.OH_ACTIVITY_PAGE}
        return redirect('/dashboard')

    logger.debug('Could not create Withings/Nokia member.')
    return redirect('/dashboard')


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
