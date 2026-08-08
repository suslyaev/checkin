import os
import time
from urllib.parse import parse_qs, urlparse

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class CheckinPage:
    SEARCH = (By.NAME, 'q')

    def __init__(self, browser, base_url, event_id):
        self.browser = browser
        self.url = f'{base_url}/event/instance/{event_id}/checkins/'
        self.wait = WebDriverWait(browser, 10)
        self.slowmo = float(os.getenv('E2E_SLOWMO', '0'))

    def _pause(self):
        if self.slowmo > 0:
            time.sleep(self.slowmo)

    @staticmethod
    def _guest_link(full_name):
        return By.XPATH, f"//a[normalize-space()='{full_name}']"

    @staticmethod
    def _confirm_button(full_name):
        return (
            By.XPATH,
            f"//li[.//a[normalize-space()='{full_name}']]//button[1]",
        )

    def open(self):
        self.browser.get(self.url)
        self.wait.until(EC.visibility_of_element_located(self.SEARCH))
        self._pause()
        return self

    def search(self, last_name):
        field = self.browser.find_element(*self.SEARCH)
        field.clear()
        field.send_keys(last_name)
        self._pause()
        field.send_keys(Keys.ENTER)
        self.wait.until(
            lambda driver: parse_qs(urlparse(driver.current_url).query).get('q')
            == [last_name]
        )
        self._pause()

    def wait_for_guest(self, full_name):
        return self.wait.until(
            EC.visibility_of_element_located(self._guest_link(full_name))
        )

    def has_guest(self, full_name):
        return bool(self.browser.find_elements(*self._guest_link(full_name)))

    def confirm_guest(self, full_name):
        self.wait.until(
            EC.element_to_be_clickable(self._confirm_button(full_name))
        ).click()
        alert = self.wait.until(EC.alert_is_present())
        message = alert.text
        self._pause()
        alert.accept()
        self.wait.until(
            EC.invisibility_of_element_located(self._guest_link(full_name))
        )
        self._pause()
        return message
