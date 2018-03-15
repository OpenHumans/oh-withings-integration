from django.db import models
from social.backends.oauth import BaseOAuth1


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


def make_oauth_nonce():
    """
    Making a random string, specific to this request.
    """


def make_oauth_signature():
    """
    Compute OAuth signature using hmac-sha1 on the oAuth base string, then
    base64 & url-encode the result.
    """


class NokiaHealthMember(models.Model):
    """
    Store OAuth data for Nokia Health member.
    """
