import os
import re
import yaml
from helpers import data_path

import crypto

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
    def __init__(self, file=file, name=None, matches=None, password_rules=None, steps=None, javascript_enabled=True):
        self.file = file
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
                        rules.append(Rule(**dict(yaml.load(f), file=file)))
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


class GlobalState(object):
    """
        Store data we need during the run.
    """
    state = {}

    @classmethod
    def reset(cls):
        cls.state = {}

    def __getattr__(self, item):
        if item in self.state:
            return self.state
        raise AttributeError

    def __setattr(self, key, value):
        self.state[key] = value
