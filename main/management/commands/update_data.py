from django.core.management.base import BaseCommand
from main.models import NokiaHealthMember
from main.views import process_nokia
import arrow
from datetime import timedelta


class Command(BaseCommand):
    help = 'Update data for all users'

    def handle(self, *args, **options):
        nokia_users = NokiaHealthMember.objects.all()
        for user in nokia_users:
            if user.last_updated < (arrow.now() - timedelta(days=4)):
                print("running update for user {}".format(user.userid))
                process_nokia.delay(user.user.oh_id)
            else:
                print("didn't update {}".format(user.userid))
