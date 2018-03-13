from django.db import models


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
