from django.db import migrations

from event.staged_import.name_dictionaries_seed import KNOWN_FIRST_NAMES, KNOWN_LAST_NAMES


def seed_known_names(apps, schema_editor):
    KnownFirstName = apps.get_model('event', 'KnownFirstName')
    KnownLastName = apps.get_model('event', 'KnownLastName')
    KnownFirstName.objects.bulk_create(
        [KnownFirstName(name=name) for name in dict.fromkeys(KNOWN_FIRST_NAMES)],
        ignore_conflicts=True,
    )
    KnownLastName.objects.bulk_create(
        [KnownLastName(name=name) for name in dict.fromkeys(KNOWN_LAST_NAMES)],
        ignore_conflicts=True,
    )


def unseed_known_names(apps, schema_editor):
    # Не удаляем: список мог быть дополнен вручную через админку после сидинга,
    # разбирать «что было из сида, а что добавили руками» — лишний риск.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('event', '0012_knownfirstname_knownlastname'),
    ]

    operations = [
        migrations.RunPython(seed_known_names, unseed_known_names),
    ]
