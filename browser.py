import os
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver import DesiredCapabilities
from selenium.webdriver.common.by import By
import time
from helpers import get_data_dir


TIMEOUT = 30
WINDOW_SIZE = (1000, 800)

class UnexpectedElementError(Exception):
    pass

def get_browser():
    desired_capabilities = dict(DesiredCapabilities.PHANTOMJS)
    # use Chrome user agent so sites serve the same content we see in Selenium IDE
    desired_capabilities["phantomjs.page.settings.userAgent"] = "Mozilla/5.0 (Windows NT 5.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/36.0.1985.67 Safari/537.36"
    driver = webdriver.PhantomJS(
        executable_path=os.path.join(get_data_dir(), 'contrib/phantomjs'),
        desired_capabilities=desired_capabilities,
        service_log_path='phantomjs.log',
        )
    driver.implicitly_wait(TIMEOUT)
    driver.set_window_size(*WINDOW_SIZE)
    return driver

def run_step(driver, step, opts):
    """ Implement Selenium IDE commands. """

    if step == 'open':
        end_time = time.time() + TIMEOUT
        while True:
            old_url = driver.current_url
            driver.get(opts[0])
            if time.time() > end_time or driver.current_url != old_url:
                break

    elif step == 'type':
        element = get_element(driver, opts[0])
        element.clear()
        element.send_keys(opts[1])

    elif step == 'click':
        get_element(driver, opts[0]).click()

    elif step == 'executeScript':
        driver.execute_script(opts[1], get_element(driver, opts[0]))

    elif step == 'assertElementPresent':
        get_element(driver, opts[0])

    elif step == 'assertText':
        end_time = time.time() + TIMEOUT
        while True:
            try:
                assert opts[1] in get_element(driver, opts[0]).text
                break
            except AssertionError:
                if time.time() > end_time:
                    raise
                time.sleep(.1)

    elif step == 'assertNotFound':
        if opts[1] is not None:
            driver.implicitly_wait(opts[1])
        try:
            get_element(driver, opts[0])
            raise UnexpectedElementError(opts[2] if len(opts)>2 else "Error condition met. This usually means a login was wrong.")
        except NoSuchElementException:
            pass
        finally:
            driver.implicitly_wait(TIMEOUT)


search_types = {
    'id':By.ID,
    'xpath':By.XPATH,
    'link':By.PARTIAL_LINK_TEXT,
    'name':By.NAME,
    'css':By.CSS_SELECTOR,
}

def get_element(driver, specifier):
    """
        Find an element according to Selenium IDE syntax.
        See http://selenium.googlecode.com/svn/trunk/docs/api/py/selenium/selenium.selenium.html#selenium.selenium.selenium
    """
    if specifier.startswith('//'):
        return driver.find_element_by_xpath(specifier)

    if '=' in specifier:
        search_type, value = specifier.split('=', 1)
        if search_type in search_types:
            return driver.find_element(by=search_types[search_type], value=value)

    return driver.find_element_by_id(specifier)

