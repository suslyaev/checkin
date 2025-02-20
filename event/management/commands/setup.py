from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission

class Command(BaseCommand):
    help = "Создаёт или обновляет базовые группы (Администратор, Менеджер, Проверяющий) с нужными правами."

    def handle(self, *args, **options):
        # Определяем набор разрешений для каждой группы
        # Список 'codename' можно посмотреть в админке -> Permissions или в базе
        group_specs = {'Администратор': ['add_action',
                   'change_action',
                   'delete_action',
                   'view_action',
                   'add_categorycontact',
                   'change_categorycontact',
                   'delete_categorycontact',
                   'view_categorycontact',
                   'add_checkin',
                   'change_checkin',
                   'delete_checkin',
                   'view_checkin',
                   'add_companycontact',
                   'change_companycontact',
                   'delete_companycontact',
                   'view_companycontact',
                   'add_contact',
                   'change_contact',
                   'delete_contact',
                   'view_contact',
                   'add_customuser',
                   'change_customuser',
                   'delete_customuser',
                   'view_customuser',
                   'add_infocontact',
                   'change_infocontact',
                   'delete_infocontact',
                   'view_infocontact',
                   'add_moduleinstance',
                   'change_moduleinstance',
                   'delete_moduleinstance',
                   'view_moduleinstance',
                   'add_socialnetwork',
                   'change_socialnetwork',
                   'delete_socialnetwork',
                   'view_socialnetwork',
                   'add_statuscontact',
                   'change_statuscontact',
                   'delete_statuscontact',
                   'view_statuscontact'],
 'Менеджер': ['add_categorycontact',
              'change_categorycontact',
              'view_categorycontact',
              'add_checkin',
              'change_checkin',
              'delete_checkin',
              'view_checkin',
              'add_companycontact',
              'change_companycontact',
              'view_companycontact',
              'add_contact',
              'change_contact',
              'view_contact',
              'view_customuser',
              'add_infocontact',
              'change_infocontact',
              'delete_infocontact',
              'view_infocontact',
              'add_moduleinstance',
              'change_moduleinstance',
              'view_moduleinstance',
              'add_socialnetwork',
              'change_socialnetwork',
              'view_socialnetwork',
              'add_statuscontact',
              'change_statuscontact',
              'view_statuscontact'],
 'Проверяющий': ['view_categorycontact',
                 'add_checkin',
                 'delete_checkin',
                 'view_checkin',
                 'view_companycontact',
                 'add_contact',
                 'view_contact',
                 'add_infocontact',
                 'view_infocontact',
                 'view_moduleinstance',
                 'view_socialnetwork',
                 'view_statuscontact']}

        for group_name, permission_codenames in group_specs.items():
            # Создаём или получаем группу по имени
            group, created = Group.objects.get_or_create(name=group_name)

            # Находим разрешения по списку codename
            perms = Permission.objects.filter(codename__in=permission_codenames)
            # Привязываем разрешения к группе
            group.permissions.set(perms)
            group.save()

            if created:
                self.stdout.write(self.style.SUCCESS(f"Группа '{group_name}' создана."))
            else:
                self.stdout.write(self.style.WARNING(f"Группа '{group_name}' обновлена."))

        self.stdout.write(self.style.SUCCESS("Группы успешно созданы/обновлены!"))