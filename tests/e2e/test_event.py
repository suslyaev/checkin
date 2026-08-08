import pytest


pytestmark = pytest.mark.django_db(transaction=True)


def test_admin_can_create_event_through_ui(ui_event):
    assert ui_event.is_visible
    assert ui_event.address == 'Selenium test address'
    assert ui_event.date_start is not None
    assert ui_event.date_end is not None
