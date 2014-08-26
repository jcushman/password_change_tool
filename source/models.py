import os
import re
import threading
import traceback
from urlparse import urlparse
import requests
import yaml

from browser import BrowserException, run_step as browser_run_step, get_browser
from helpers import data_path, ask, get_first_result_from_threads
import crypto
import secure_log
from global_state import GlobalState

PASSWORD_LENGTH = 14

class FileHandler(object):
    manager_class = None

    def __init__(self, extension, description, handler, wildcard=None):
        self.extension = extension
        self.description = description
        self.handler = handler
        self.wildcard = wildcard or \
                        "%s (*.%s)|*.%s" % (description, extension, extension)


class Rule(object):
    def __init__(self, file_name=None, name=None, matches=None, password_rules=None, steps=None, javascript_enabled=True):
        self.file_name = file_name
        self.name = name
        self.targets = matches or []
        self.password_rules = password_rules or {}
        self.steps = steps
        self.javascript_enabled = javascript_enabled

        # set up default target parameters
        for i, target in enumerate(self.targets):
            if type(target)==str:
                # if given as a string, treat as a domain target
                self.targets[i] = {'url':target, 'kind':'domain', 'priority':0}
            elif target['kind']=='regex':
                # pre-compile regex targets
                target['regex'] = re.compile(target['url'], flags=re.IGNORECASE)

    @classmethod
    def load_rules(cls):
        # load yaml files from rules/ dir
        rules = []
        for subdir, dirs, files in os.walk(data_path('rules')):
            for file in files:
                if file.endswith('.yaml'):
                    with open(os.path.join(subdir, file), 'rb') as f:
                        rules.append(Rule(**dict(yaml.load(f), file_name=file)))
        return rules

    @classmethod
    def attach_rules(cls, logins):
        """ Given list of logins, set login['rule'] to matching rule for each, or else login['error'] """
        rules = cls.load_rules()

        # Rules can each have multiple targets.
        # We need to get all targets in (rule, target) tuples sorted by priority.
        targets = []
        for rule in rules:
            targets += [(rule, target) for target in rule.targets]
        targets.sort(key=lambda target: target[1]['priority'], reverse=True)

        for login in GlobalState.logins:
            # skip logins where we already found an endpoint via http service
            if login.get('rule'):
                continue

            for rule, target in targets:
                match_result = rule.applies_to(target, login)
                if match_result:
                    login['rule'] = rule
                    login['match_result'] = match_result
                    break
            else:
                login['error'] = "Site not supported."

    def applies_to(self, target, login):
        # handle domain-based targets -- e.g www.foo.com, .foo.com
        if target['kind'] == 'domain':
            if not login.get('domain', None):
                return False
            if target['url'].startswith('.'):
                if login['domain'].endswith(target['url']) or login['domain'] == target['url'][1:]:
                    return True
            elif target['url'] == login['domain']:
                return True

        # handle regex-based targets -- e.g. (.+)/foo-login/
        elif target['kind'] == 'regex':
            if not login.get('location'):
                return False
            match = target['regex'].search(login['location'])
            if match:
                return match.groups()

        return False

    def generate_password(self):
        # select password length between min_length and max_length, with preference for PASSWORD_LENGTH
        length = max(
                    min(
                        PASSWORD_LENGTH,
                        self.password_rules.get('max_length', PASSWORD_LENGTH)
                    ), self.password_rules.get('min_length', 0))

        return crypto.generate_password(length,
                                        allowed_chars=self.password_rules.get('allowed_chars'),
                                        required_ranges=self.password_rules.get('required_ranges'))

    def execute(self, panel, login):
        driver = get_browser(self.javascript_enabled)

        # set up screenshot thread
        stop_screenshots = threading.Event()
        screenshot_thread = threading.Thread(target=panel.update_screenshot, args=[driver, stop_screenshots])
        screenshot_thread.start()

        # set up replacement dictionary
        replacements = {'username': login['username'],
                        'old_password': login['password'],
                        'new_password': login['new_password']}

        # for regex-based matches, we include the match groups in the replacements dict as 'url_group_N', counting from 1
        if type(login['match_result']) == tuple:
            for i, match_group in enumerate(login['match_result']):
                replacements['url_group_%s' % (i + 1)] = match_group

        # make sure a step is marked as the one that actually updates the password
        for step in self.steps:
            if type(step)==list and type(step[-1]) == dict and step[-1].get('updates_password'):
                break
        else:
            # by default, we assume it's the second to last step
            update_step = self.steps[-2]
            if type(update_step[-1]) != dict:
                update_step.append({})
            update_step[-1]['updates_password'] = True

        try:
            self.run_steps(login, driver, self.steps, replacements)
        except BrowserException as e:
            login['update_error'] = e.message
            return False # failure
        finally:
            stop_screenshots.set()
            screenshot_thread.join()

        login['update_success'] = True
        return True # success

    def run_steps(self, login, driver, steps, replacements):
        for step in steps:
            self.run_step(login, driver, step, replacements)

    def run_step(self, login, driver, step, replacements):
        print "Running", step

        if type(step)==dict:
            args = step
            for key in ('if', 'tryAll'):
                if key in step:
                    step_type = key
                    break
            else:
                raise Exception("Unrecognized step: %s" % step)
        else:
            step_type, args = step[0], step[1:]
            # get opts from end of arguments list
            if type(args[-1]) == dict and step_type != 'tryAll':
                args, opts = args[:-1], args[-1]
            else:
                opts = {}

        # replacements
        if step_type in ('type', 'ask', 'open'):
            for from_str, to_str in replacements.items():
                args[-1] = args[-1].replace("{{ %s }}" % from_str, to_str)

        if step_type == 'exit':
            raise BrowserException(opts.get('error_message','Exit.'))

        elif step_type == 'tryAll':
            # the arguments for tryAll are a series of test_steps, success_steps pairs:
            # [test_steps_1, success_steps_1, test_steps_2, success_steps_2 ...]
            # We are going to run each set of test_steps *simultaneously* in background threads.
            # The first one to either throw an error or finish we will get back.
            # The rest will be cancelled.
            # If the completed one did not throw an error,we will run its success_steps.
            parallelSteps = args['tryAll']
            index, result = get_first_result_from_threads((self.run_step, [login, driver, step['try'], replacements]) for step in parallelSteps)
            if isinstance(result, Exception):
                print traceback.print_exception(type(result), result, None)
                raise result
            elif parallelSteps[index].get('then'):
                self.run_steps(login, driver, parallelSteps[index]['then'], replacements)

        elif step_type == 'if':
            try:
                self.run_step(login, driver, args['if'], replacements)
                substeps = args['then']
            except BrowserException:
                substeps = args.get('else', [])
            self.run_steps(login, driver, substeps, replacements)

            # substeps = []
            # remaining_parts = step
            # while remaining_parts:
            #     if remaining_parts[0] == 'if' or remaining_parts[0] == 'elif':
            #         test_step, success_steps, remaining_parts = remaining_parts[1], remaining_parts[2], remaining_parts[
            #                                                                                             3:]
            #         try:
            #             self.run_step(login, driver, test_step, replacements)
            #             substeps = success_steps
            #             break
            #         except BrowserException:
            #             # condition failed
            #             pass
            #     elif remaining_parts[0] == 'else':
            #         substeps = remaining_parts[1]
            #         break
            # self.run_steps(login, driver, substeps, replacements)

        elif step_type == 'ask':
            key, prompt = args
            replacements[key] = ask(None, prompt)

        else:
            result = browser_run_step(driver, step_type, args, timeout=opts.get('timeout'),
                                      error_message=opts.get('error_message'))

            if opts.get('updates_password'):
                login['update_attempted'] = True
                secure_log.replace_last_entry(login)

            if step_type == 'capture':
                replacements[args[1]] = result


class PasswordEndpointRule(Rule):
    def __init__(self, name, announce_url, data):
        super(PasswordEndpointRule, self).__init__(file_name='password_endpoint', name=name, password_rules=data.get('password_rules'))
        self.announce_url = announce_url
        parsed_url = urlparse(announce_url)
        self.endpoint = '%s://%s%s' % (parsed_url.scheme, parsed_url.netloc, data['endpoint'])

    def execute(self, panel, login):
        timeout = GlobalState.options.timeout if GlobalState.options.timeout is not None else 15
        try:
            result = requests.post(self.endpoint, verify=True, allow_redirects=False, timeout=timeout, data={
                'username': login['username'],
                'password': login['password'],
                'new_password': login['new_password']
            })
        except Exception as e:
            login['update_error'] = str(e)
            return False
        if result.status_code == 200:
            login['update_success'] = login['update_attempted'] = True
            return True
        else:
            result['update_error'] = result.status_code
            return False


