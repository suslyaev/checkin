import os
from pathlib import Path
import time

import pytest
from django.contrib.auth.models import Group
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

from event.models import Action, Contact, CustomUser, ModuleInstance


def _cached_chromedriver():
    configured_path = os.getenv('E2E_CHROMEDRIVER')
    if configured_path:
        return Path(configured_path)

    cache_root = Path.home() / '.cache' / 'selenium' / 'chromedriver'
    drivers = list(cache_root.glob('**/chromedriver.exe'))
    return max(drivers, key=lambda path: path.stat().st_mtime) if drivers else None


@pytest.fixture
def browser():
    options = Options()
    if os.getenv('E2E_HEADLESS', '1') == '1':
        options.add_argument('--headless=new')
    options.add_argument('--window-size=1440,1000')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-search-engine-choice-screen')

    driver_path = _cached_chromedriver()
    service = Service(executable_path=str(driver_path)) if driver_path else None
    driver = webdriver.Chrome(options=options, service=service)
    driver.implicitly_wait(0)
    yield driver
    slowmo = float(os.getenv('E2E_SLOWMO', '0'))
    if slowmo > 0:
        time.sleep(slowmo)
    driver.quit()


@pytest.fixture
def test_user(db):
    password = 'Test-password-123'
    admin_group = Group.objects.create(name='Администратор')
    user = CustomUser.objects.create_superuser(
        phone='+79991234567',
        password=password,
        first_name='Selenium',
    )
    user.groups.add(admin_group)
    return user, password


@pytest.fixture
def checkin_data(test_user, ui_event):
    user, _ = test_user
    ivanov = Contact.objects.create(last_name='Иванов', first_name='Иван')
    petrov = Contact.objects.create(last_name='Петров', first_name='Пётр')
    ivanov_action = Action.objects.create(
        contact=ivanov,
        event=ui_event,
        action_type='new',
        create_user=user,
    )
    Action.objects.create(
        contact=petrov,
        event=ui_event,
        action_type='new',
        create_user=user,
    )

    return ui_event, ivanov_action


@pytest.fixture
def ui_event(browser, live_server, test_user):
    from tests.e2e.pages.event_admin_page import EventAdminPage
    from tests.e2e.pages.login_page import LoginPage

    user, password = test_user
    login_page = LoginPage(browser, live_server.url).open()
    login_page.login(user.phone, password)
    login_page.wait_until_logged_in()

    event_name = EventAdminPage.unique_event_name()
    EventAdminPage(browser, live_server.url).open().create_event(event_name)
    return ModuleInstance.objects.get(name=event_name)
