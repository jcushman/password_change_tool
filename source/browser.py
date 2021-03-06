import json
import os
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, InvalidElementStateException, ElementNotVisibleException
from selenium.webdriver import DesiredCapabilities
from selenium.webdriver.common.by import By
import time
import sys
from helpers import data_path
from global_state import GlobalState


TIMEOUT = 30
WINDOW_SIZE = (1000, 800)

class UnexpectedElementError(Exception):
    pass

class BrowserException(Exception):
    def __init__(self, *args, **kwargs):
        self.original_exception = kwargs.pop('original_exception', None)
        super(BrowserException, self).__init__(*args, **kwargs)

def get_default_timeout():
    return GlobalState.options.timeout if GlobalState.options.timeout is not None else TIMEOUT

def get_browser(javascript_enabled=True):
    desired_capabilities = dict(DesiredCapabilities.PHANTOMJS)
    # use Chrome user agent so sites serve the same content we see in Selenium IDE
    desired_capabilities["phantomjs.page.settings.userAgent"] = "Mozilla/5.0 (Windows NT 5.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/36.0.1985.67 Safari/537.36"
    desired_capabilities["phantomjs.page.settings.javascriptEnabled"] = javascript_enabled
    driver = webdriver.PhantomJS(
        executable_path=data_path('contrib/phantomjs'),
        desired_capabilities=desired_capabilities,
        service_log_path='phantomjs.log' if GlobalState.options.debug else os.devnull,
        )
    driver.implicitly_wait(get_default_timeout())
    driver.set_window_size(*WINDOW_SIZE)

    # make sure that phantomjs process is terminated when we exit
    GlobalState.cleanup_message.send({'action':'kill','pid':driver.service.process.pid})

    return driver

def run_step(driver, step, step_args, timeout=None, error_message=None):
    """ Implement Selenium IDE commands. """
    try:
        if timeout is not None:
            driver.implicitly_wait(timeout)
            current_timeout = timeout
        else:
            current_timeout = get_default_timeout()
        end_time = time.time() + current_timeout

        if step == 'open':
            url = step_args[0]
            while True:
                old_url = driver.current_url
                driver.get(url)
                if time.time() > end_time or driver.current_url != old_url:
                    break

        elif step == 'type':
            selector, text = step_args
            element = get_element(driver, selector)
            while True:
                try:
                    element.clear()
                    element.send_keys(text)
                    break
                except InvalidElementStateException as e:
                    if time.time() > end_time:
                        raise
                    time.sleep(.1)

        elif step == 'click':
            selector = step_args[0]
            while True:
                try:
                    get_element(driver, selector).click()
                    break
                except ElementNotVisibleException:
                    if time.time() > end_time:
                        raise
                    time.sleep(.1)

        # Not sure if we should actually support this, in terms of limiting the damage a malicious script can do.
        # On the other hand, by the time someone is running a malicious script, they can already steal your new password,
        # so it's not clear what else we're protecting from.
        # elif step == 'executeScript':
        #     driver.execute_script(opts[1], get_element(driver, opts[0]))

        elif step == 'capture':
            selector, key = step_args
            return get_element(driver, selector).text # key isn't used here -- will be handled by the calling function

        elif step == 'assertElementPresent':
            selector = step_args[0]
            get_element(driver, step_args[0])

        elif step == 'assertText':
            selector, text = step_args
            while True:
                try:
                    assert text in get_element(driver, selector).text
                    break
                except AssertionError:
                    if time.time() > end_time:
                        raise
                    time.sleep(.1)

        elif step == 'assertNotFound':
            selector = step_args[0]
            try:
                get_element(driver, selector)
                raise UnexpectedElementError("Found unexpected element. This usually means a login was wrong.")
            except NoSuchElementException:
                pass

        else:
            raise BrowserException("Unrecognized command: %s" % step)

    except (UnexpectedElementError, NoSuchElementException, InvalidElementStateException, AssertionError, BrowserException) as e:
        # debugging
        if GlobalState.options.debug:
            import pdb; pdb.set_trace()

        # capture all expected errors and group into single exception type
        if error_message:
            message = error_message
        else:
            try:
                # simplify selenium errors, which have a weird JSON format
                message = json.loads(e.msg)['errorMessage']
            except Exception:
                message = str(e)
        raise BrowserException, BrowserException(message, original_exception=e), sys.exc_info()[2]

    finally:
        # reset timeout
        if timeout is not None:
            driver.implicitly_wait(get_default_timeout())


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
    out = None
    if specifier.startswith('//'):
        out = driver.find_elements_by_xpath(specifier)
    elif '=' in specifier:
        search_type, value = specifier.split('=', 1)
        if search_type in search_types:
            out = driver.find_elements(by=search_types[search_type], value=value)
    if not out:
        out = driver.find_elements_by_id(specifier)
    if not out:
        raise BrowserException("No element matching specifier: %s" % specifier)
    if len(out)>1:
        raise BrowserException("Multiple elements returned for specifier: %s" % specifier)
    return out[0]


