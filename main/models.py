from django.db import models
from django.conf import settings
from open_humans.models import OpenHumansMember
from datetime import timedelta
import requests
import arrow

class NokiaHealthMember(models.Model):
    """
    Store OAuth2 data for Open Humans member.
    A User account is created for this Open Humans member.
    """
    user = models.OneToOneField(OpenHumansMember, related_name="nokia_member", on_delete=models.CASCADE)
    userid = models.CharField(max_length=16, primary_key=True, unique=True)
    deviceid = models.CharField(max_length=16)
    last_updated = models.DateTimeField(
                            default=(arrow.now() - timedelta(days=7)).format())
    last_submitted = models.DateTimeField(
                            default=(arrow.now() - timedelta(days=7)).format())
    # OAuth1
    oauth_token = models.CharField(max_length=256)
    oauth_token_secret = models.CharField(max_length=256)
    # OAuth2
    access_token = models.CharField(max_length=512, null=True)
    refresh_token = models.CharField(max_length=512, null=True)
    expires_in = models.CharField(max_length=512, null=True)
    scope = models.CharField(max_length=512, null=True)
    token_type = models.CharField(max_length=512, null=True)

    @staticmethod
    def get_expiration(expires_in):
        return (arrow.now() + timedelta(seconds=expires_in)).format()

    def get_access_token(self,
                         client_id=settings.NOKIA_CLIENT_ID,
                         client_secret=settings.NOKIA_CONSUMER_SECRET):
        """
        Return access token. Refresh first if necessary.
        """
        # Also refresh if nearly expired (less than 60s remaining).
        delta = timedelta(seconds=60)
        if arrow.get(self.expires_in) - delta < arrow.now():
            self._refresh_tokens()
        return self.access_token

    def _refresh_tokens(self):
        """
        Refresh access token.
        """
        print("calling refresh token method in class")
        response = requests.get(
            'https://account.withings.com/oauth2/token',
            data = {
                'grant_type': 'refresh_token',
                'client_id': settings.NOKIA_CLIENT_ID,
                'client_secret': settings.NOKIA_CONSUMER_SECRET,
                'refresh_token': self.refresh_token
            })
        print(response.text)
        if response.status_code == 200:
            data = response.json()
            self.access_token = data['access_token']
            self.refresh_token = data['refresh_token']
            self.token_expires = self.get_expiration(data['expires_in'])
            self.scope = data['scope']
            self.userid = data['userid']
            self.save()
            return True
        return False