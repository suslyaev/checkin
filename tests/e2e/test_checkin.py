import pytest

from tests.e2e.pages.action_admin_page import ActionAdminPage
from tests.e2e.pages.checkin_page import CheckinPage
from tests.e2e.pages.contact_admin_page import ContactAdminPage


@pytest.fixture
def registered_guest(authenticated_browser, base_url, ui_event):
    contact_page = ContactAdminPage(authenticated_browser, base_url)
    last_name, first_name = contact_page.unique_contact_name()
    contact = contact_page.create_contact(last_name, first_name)
    ActionAdminPage(authenticated_browser, base_url).create_registration(
        ui_event['id'],
        contact,
    )
    return ui_event, contact


def test_checker_can_find_guest_by_last_name(
    authenticated_browser, base_url, registered_guest
):
    event, contact = registered_guest
    checkin_page = CheckinPage(
        authenticated_browser,
        base_url,
        event['id'],
    ).open()

    last_name = contact['full_name'].split()[0]
    checkin_page.search(last_name)

    assert checkin_page.wait_for_guest(contact['full_name']).is_displayed()


def test_checker_can_confirm_guest(
    authenticated_browser, base_url, registered_guest
):
    event, contact = registered_guest
    checkin_page = CheckinPage(
        authenticated_browser,
        base_url,
        event['id'],
    ).open()

    message = checkin_page.confirm_guest(contact['full_name'])

    assert message == 'Подтверждено'
    assert not checkin_page.has_guest(contact['full_name'])
