from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class ActionAdminPage:
    SAVE = (By.NAME, '_save')

    def __init__(self, browser, base_url):
        self.browser = browser
        self.base_url = base_url
        self.wait = WebDriverWait(browser, 10)

    @staticmethod
    def _row(full_name):
        return By.XPATH, f"//tr[.//a[normalize-space()='{full_name}']]"

    def create_registration(self, event_id, contact):
        self.browser.get(
            f'{self.base_url}/admin/event/action/add/'
            f'?event={event_id}&contact={contact["id"]}'
        )
        self.wait.until(EC.element_to_be_clickable(self.SAVE)).click()
        self.wait.until(EC.visibility_of_element_located(self._row(contact['full_name'])))

        self._change_status(contact['full_name'], 'button-invited')
        self._change_status(contact['full_name'], 'button-registered')

    def _change_status(self, full_name, button_class):
        row = self.wait.until(EC.visibility_of_element_located(self._row(full_name)))
        row.find_element(By.CSS_SELECTOR, f'.{button_class}').click()
        self.wait.until(
            lambda driver: not driver.find_elements(
                By.CSS_SELECTOR,
                f'.{button_class}',
            )
        )
        self.browser.refresh()
        self.wait.until(EC.visibility_of_element_located(self._row(full_name)))
