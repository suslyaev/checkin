import os
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class LoginPage:
    USERNAME = (By.ID, 'id_username')
    PASSWORD = (By.ID, 'id_password')
    SUBMIT = (By.CSS_SELECTOR, 'button[type="submit"]')
    BRANDING = (By.ID, 'site-branding')
    APP_ROOT = (By.ID, 'root')

    def __init__(self, browser, base_url):
        self.browser = browser
        self.url = f'{base_url}/'
        self.wait = WebDriverWait(browser, 10)
        self.slowmo = float(os.getenv('E2E_SLOWMO', '0'))

    def _pause(self):
        if self.slowmo > 0:
            time.sleep(self.slowmo)

    def open(self):
        self.browser.get(self.url)
        self.wait.until(EC.visibility_of_element_located(self.USERNAME))
        self._pause()
        return self

    def login(self, phone, password):
        self.browser.find_element(*self.USERNAME).send_keys(phone)
        self._pause()
        self.browser.find_element(*self.PASSWORD).send_keys(password)
        self._pause()
        self.browser.find_element(*self.SUBMIT).click()
        self._pause()

    def wait_until_logged_in(self):
        return self.wait.until(EC.presence_of_element_located(self.APP_ROOT))

    def is_login_form_visible(self):
        return self.browser.find_element(*self.BRANDING).is_displayed()
