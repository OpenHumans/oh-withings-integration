from django.core.management.base import BaseCommand
from main.models import NokiaHealthMember
from open_humans.models import OpenHumansMember
from django.conf import settings

class Command(BaseCommand):
    help = 'Import existing users from legacy project. Refresh (and save) OH/Nokia tokens for all members'

    def add_arguments(self, parser):
        parser.add_argument('--infile', type=str,
                            help='CSV with project_member_id & refresh_token')
        parser.add_argument('--delimiter', type=str,
                            help='CSV delimiter')

    def handle(self, *args, **options):
        for line in open(options['infile']):
            line = line.strip().split(options['delimiter'])
            oh_id = line[0]
            oh_access_token = line[1]
            oh_refresh_token = line[2]
            nokia_id = line[3]
            nokia_access_token = line[4]
            nokia_token_secret = line[5]
            if len(OpenHumansMember.objects.filter(
                        oh_id=oh_id)) == 0:
                oh_member = OpenHumansMember.create(
                                    oh_id=oh_id,
                                    access_token=oh_access_token,
                                    refresh_token=oh_refresh_token,
                                    expires_in=-3600)
                oh_member.save()
                # oh_member._refresh_tokens(client_id=settings.OPENHUMANS_CLIENT_ID,
                #                             client_secret=settings.OPENHUMANS_CLIENT_SECRET)
                oh_member = OpenHumansMember.objects.get(oh_id=oh_id)
                print("made it to nokiamember")
                nokia_member = NokiaHealthMember(
                    userid=nokia_id,
                    oauth_token=nokia_access_token,
                    oauth_token_secret=nokia_token_secret
                )
                print(nokia_member)
                nokia_member.user = oh_member
                nokia_member.save()
                # nokia_member._refresh_tokens()
                # fetch_nokia_data.delay(oh_member.oh_id, oh_member.nokia_member.access_token)
