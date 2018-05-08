from django.core.management.base import BaseCommand
from main.models import NokiaHealthMember
from open_humans.models import OpenHumansMember
from fitbit.settings import OPENHUMANS_CLIENT_ID, OPENHUMANS_CLIENT_SECRET


class Command(BaseCommand):
    help = 'Update data for all users'

    def handle(self, *args, **options):
        # OH token refresh (for all users)
        oh_users = OpenHumansMember.objects.all()
        for user in users:
            user._refresh_tokens(OPENHUMANS_CLIENT_ID, OPENHUMANS_CLIENT_SECRET)

        # Nokia token refresh (for all users)
        nokia_users = NokiaHealthMember.objects.all()
        for user in users:
            user._refresh_tokens()
