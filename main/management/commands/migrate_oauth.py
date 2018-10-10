from django.core.management.base import BaseCommand
from main.models import NokiaHealthMember

class Command(BaseCommand):
    help = 'Migrate users from OAuth1 to OAuth2'

    def handle(self, *args, **options):
        nokia_users = NokiaHealthMember.objects.all()
        for user in nokia_users:
            if user.oauth_token:
                print("user {} has a token".format(user.userid))
                # Concatenate oauth token + secret and pass it as refresh token
                # Implement here
            else:
                print("User {} does not have an OAuth1 token, skipping".format(user.userid))
