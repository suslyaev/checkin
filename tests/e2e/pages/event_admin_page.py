import os
import time
from datetime import timedelta
from uuid import uuid4

from django.utils import timezone
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class EventAdminPage:
    NAME = (By.ID, 'id_name')
    ADDRESS = (By.ID, 'id_address')
    IS_VISIBLE = (By.ID, 'id_is_visible')
    DATE_START = (By.ID, 'id_date_start_0')
    TIME_START = (By.ID, 'id_date_start_1')
    DATE_END = (By.ID, 'id_date_end_0')
    TIME_END = (By.ID, 'id_date_end_1')
    SAVE = (By.NAME, '_save')

    def __init__(self, browser, base_url):
        self.browser = browser
        self.url = f'{base_url}/admin/event/moduleinstance/add/'
        self.wait = WebDriverWait(browser, 10)
        self.slowmo = float(os.getenv('E2E_SLOWMO', '0'))

    @staticmethod
    def unique_event_name():
        return f'Selenium Event {uuid4().hex[:8]}'

    def _pause(self):
        if self.slowmo > 0:
            time.sleep(self.slowmo)

    def _fill(self, locator, value):
        field = self.browser.find_element(*locator)
        field.clear()
        field.send_keys(value)

    def open(self):
        self.browser.get(self.url)
        self.wait.until(EC.visibility_of_element_located(self.NAME))
        self._pause()
        return self

    def create_event(self, name):
        now = timezone.localtime()
        end = now + timedelta(hours=3)
        self._fill(self.NAME, name)
        self._fill(self.ADDRESS, 'Selenium test address')
        if not self.browser.find_element(*self.IS_VISIBLE).is_selected():
            self.browser.find_element(*self.IS_VISIBLE).click()
        self._fill(self.DATE_START, now.strftime('%d.%m.%Y'))
        self._fill(self.TIME_START, now.strftime('%H:%M:%S'))
        self._fill(self.DATE_END, end.strftime('%d.%m.%Y'))
        self._fill(self.TIME_END, end.strftime('%H:%M:%S'))
        self._pause()
        self.browser.find_element(*self.SAVE).click()
        try:
            self.wait.until(
                EC.url_matches(
                    r'.*/admin/event/moduleinstance/(?:\d+/change/)?$'
                )
            )
        except TimeoutException as error:
            errors = [
                item.text
                for item in self.browser.find_elements(By.CSS_SELECTOR, '.errorlist')
            ]
            raise AssertionError(
                f'Event was not saved. URL: {self.browser.current_url}; '
                f'validation errors: {errors}'
            ) from error
        self._pause()
