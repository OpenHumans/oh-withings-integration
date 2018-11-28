from django.core.management.base import BaseCommand
from django.conf import settings
from main.models import NokiaHealthMember
import requests

class Command(BaseCommand):
    help = 'Migrate users from OAuth1 to OAuth2'

    def handle(self, *args, **options):
        nokia_users = NokiaHealthMember.objects.all()
        for user in nokia_users:
            if user.oauth_token:
                print("user {} has a token".format(user.userid))
                baseUrl = 'https://account.withings.com/oauth2/token'
                # Construct custom token refresh URL
                # concatenates oauth token + secret and pass it as refresh_token
                migrateUrl = baseUrl + \
                            "?grant_type=refresh_token" + \
                            "&client_id=" + settings.NOKIA_CLIENT_ID + \
                            "&client_secret=" + settings.NOKIA_CLIENT_SECRET + \
                            "&refresh_token=" + user.oauth_token + ":" + user.oauth_token_secret
                print("Token migration url: " + migrateUrl)  
                r = requests.post(migrateUrl)
                q = r.json()
                # Update user data & save
                user.access_token = q.access_token
                user.refresh_token = q.refresh_token
                user.expires_in = q.expires_in
                user.scope = q.scope
                user.token_type = q.token_type
                user.userid = q.userid
                user.save()
            else:
                print("User {} does not have an OAuth1 token, skipping".format(user.userid))
