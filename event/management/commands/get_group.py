from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group

class Command(BaseCommand):
    help = "Принтит текущие группы и разрешения"

    def handle(self, *args, **options):
        groups_dict = {}

        for g in Group.objects.all():
            perms = [p.codename for p in g.permissions.all()]
            groups_dict[g.name] = perms

        import pprint
        pprint.pprint(groups_dict)
