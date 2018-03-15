from django.db import models
from social.backends.oauth import BaseOAuth1
import secrets


class NokiaOAuth1(BaseOAuth1):
    """
    Nokia OAuth1 authentication
    """
    ID_KEY = 'userid'
    AUTH_URL = 'https://developer.health.nokia.com/account/authorize'
    REQUEST_TOKEN = 'https://developer.health.nokia.com/account/request_token'
    ACCESS_TOKEN = 'https://developer.health.nokia.com/account/access_token'

    def get_user_id(self, details, response):
        return response['access_token'][self.ID_KEY]


def create_nokia_nonce(length=8):
    """
    Random string that should be different for every request.
    """
    secrets.token_hex(length)


def create_nokia_oauth_signature():
    """
    OAuth signature. Computed using hmac-sha1 on the oAuth base string,
    then base64 & url-encode the result
    """


def create_nokia_timestamp():
    """
    Current date as unix epoch
    """
    int(time.time())


class NokiaHealthMember(models.Model):
    """
    Store OAuth data for Nokia Health member.
    """
