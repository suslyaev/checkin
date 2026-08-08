import pytest

from tests.e2e.pages.checkin_page import CheckinPage


pytestmark = pytest.mark.django_db(transaction=True)


def open_checkin_page(browser, live_server, test_user, event):
    return CheckinPage(browser, live_server.url, event.pk).open()


def test_checker_can_find_guest_by_last_name(
    browser, live_server, test_user, checkin_data
):
    event, _ = checkin_data
    checkin_page = open_checkin_page(
        browser, live_server, test_user, event
    )

    checkin_page.search('Иванов')

    assert checkin_page.wait_for_guest('Иванов Иван').is_displayed()
    assert not checkin_page.has_guest('Петров Пётр')


def test_checker_can_confirm_guest(
    browser, live_server, test_user, checkin_data
):
    event, ivanov_action = checkin_data
    checkin_page = open_checkin_page(
        browser, live_server, test_user, event
    )

    message = checkin_page.confirm_guest('Иванов Иван')

    ivanov_action.refresh_from_db()
    assert message == 'Подтверждено'
    assert ivanov_action.action_type == 'visited'
    assert not checkin_page.has_guest('Иванов Иван')
