from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class AppPage:
    SETTINGS_MENU = (
        By.XPATH,
        "//button[.//*[contains(@class, 'settings_outline')]]",
    )
    LOGOUT = (
        By.XPATH,
        "//*[normalize-space()='Выйти']",
    )
    LOGIN_FORM = (By.ID, 'site-branding')

    def __init__(self, browser):
        self.browser = browser
        self.wait = WebDriverWait(browser, 10)

    def logout(self):
        try:
            settings_menu = self.wait.until(
                EC.element_to_be_clickable(self.SETTINGS_MENU)
            )
        except TimeoutException as error:
            visible_text = self.browser.find_element(By.TAG_NAME, 'body').text
            raise AssertionError(
                f'Events menu was not found. Page text: {visible_text!r}'
            ) from error
        settings_menu.click()
        try:
            logout = self.wait.until(EC.element_to_be_clickable(self.LOGOUT))
        except TimeoutException as error:
            surrounding_html = self.browser.execute_script(
                'return arguments[0].parentElement.parentElement.outerHTML;',
                settings_menu,
            )
            raise AssertionError(
                f'Logout item was not found. Header HTML: {surrounding_html}'
            ) from error
        logout.click()

    def wait_until_logged_out(self):
        return self.wait.until(EC.visibility_of_element_located(self.LOGIN_FORM))
