import tablib
from django.db import transaction

from event.resources import ContactImport

from .contact_columns import CONTACT_IMPORT_COLUMNS
from .contact_validation import normalize_row_for_import


def import_contact_rows(rows, user):
    """Загружает отредактированные строки через существующий ContactImport."""
    resource = ContactImport()
    dataset = tablib.Dataset(headers=CONTACT_IMPORT_COLUMNS)

    for row in rows:
        if row.get('excluded'):
            continue
        normalized = normalize_row_for_import(row)
        dataset.append([normalized[col] for col in CONTACT_IMPORT_COLUMNS])

    if len(dataset) == 0:
        raise ValueError('Нет строк для загрузки')

    with transaction.atomic():
        result = resource.import_data(dataset, dry_run=False, user=user, raise_errors=True)
    return result
