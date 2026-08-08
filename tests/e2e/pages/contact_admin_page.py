import re

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class ContactAdminPage:
    LAST_NAME = (By.ID, 'id_last_name')
    FIRST_NAME = (By.ID, 'id_first_name')
    SAVE = (By.NAME, '_save')

    def __init__(self, browser, base_url):
        self.browser = browser
        self.base_url = base_url
        self.url = f'{base_url}/admin/event/contact/add/'
        self.wait = WebDriverWait(browser, 10)

    def next_contact_name(self):
        self.browser.get(
            f'{self.base_url}/admin/event/contact/'
            '?q=Selenium+Guest&all='
        )
        numbers = []
        for link in self.browser.find_elements(
            By.CSS_SELECTOR,
            '#result_list tbody th a',
        ):
            match = re.fullmatch(r'Selenium Guest (\d+)', link.text.strip())
            if match:
                numbers.append(int(match.group(1)))
        number = max(numbers, default=0) + 1
        return 'Selenium', f'Guest {number:04d}'

    def create_contact(self, last_name, first_name):
        self.browser.get(self.url)
        self.wait.until(EC.visibility_of_element_located(self.LAST_NAME))
        self.browser.find_element(*self.LAST_NAME).send_keys(last_name)
        self.browser.find_element(*self.FIRST_NAME).send_keys(first_name)
        self.browser.find_element(*self.SAVE).click()

        full_name = f'{last_name} {first_name}'
        contact_link = self.wait.until(
            EC.element_to_be_clickable(
                (By.XPATH, f"//a[normalize-space()='{full_name}']")
            )
        )
        contact_id = int(
            contact_link.get_attribute('href').rstrip('/').split('/')[-2]
        )
        return {'id': contact_id, 'full_name': full_name}
