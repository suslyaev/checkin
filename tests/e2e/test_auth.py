from tests.e2e.pages.app_page import AppPage
from tests.e2e.pages.login_page import LoginPage


def test_user_can_log_in(browser, base_url, credentials):
    phone, password = credentials
    login_page = LoginPage(browser, base_url).open()

    login_page.login(phone, password)

    assert login_page.wait_until_logged_in().is_displayed()


def test_user_stays_on_login_page_with_wrong_password(
    browser, base_url, credentials
):
    phone, _ = credentials
    login_page = LoginPage(browser, base_url).open()

    login_page.login(phone, 'wrong-password')

    assert login_page.is_login_form_visible()


def test_user_can_log_out(browser, base_url, credentials):
    phone, password = credentials
    login_page = LoginPage(browser, base_url).open()
    login_page.login(phone, password)
    login_page.wait_until_logged_in()

    app_page = AppPage(browser)
    app_page.logout()

    assert app_page.wait_until_logged_out().is_displayed()
