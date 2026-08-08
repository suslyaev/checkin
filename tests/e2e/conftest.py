import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse
import time

import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

from tests.e2e.pages.event_admin_page import EventAdminPage
from tests.e2e.pages.login_page import LoginPage


SAFE_REMOTE_HOST = '62.113.111.146'
SAFE_REMOTE_PORT = 8001


@dataclass(frozen=True)
class Credentials:
    phone: str
    password: str = field(repr=False)


def _cached_chromedriver():
    configured_path = os.getenv('E2E_CHROMEDRIVER')
    if configured_path:
        return Path(configured_path)

    cache_root = Path.home() / '.cache' / 'selenium' / 'chromedriver'
    drivers = list(cache_root.glob('**/chromedriver.exe'))
    return max(drivers, key=lambda path: path.stat().st_mtime) if drivers else None


@pytest.fixture(scope='session')
def base_url():
    url = os.getenv(
        'E2E_BASE_URL',
        f'http://{SAFE_REMOTE_HOST}:{SAFE_REMOTE_PORT}',
    ).rstrip('/')
    parsed = urlparse(url)
    if parsed.hostname != SAFE_REMOTE_HOST or parsed.port != SAFE_REMOTE_PORT:
        pytest.exit(
            'Remote UI tests are allowed only against '
            f'{SAFE_REMOTE_HOST}:{SAFE_REMOTE_PORT}.',
        )
    return url


@pytest.fixture(scope='session')
def credentials():
    phone = os.getenv('E2E_PHONE')
    password = os.getenv('E2E_PASSWORD')
    if not phone or not password:
        pytest.exit(
            'Set E2E_PHONE and E2E_PASSWORD for the testAnis superuser.'
        )
    return Credentials(phone=phone, password=password)


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
def authenticated_browser(browser, base_url, credentials):
    login_page = LoginPage(browser, base_url).open()
    login_page.login(credentials.phone, credentials.password)
    login_page.wait_until_logged_in()
    return browser


@pytest.fixture
def ui_event(authenticated_browser, base_url):
    page = EventAdminPage(authenticated_browser, base_url)
    event_name = page.next_event_name()
    return page.open().create_event(event_name)
