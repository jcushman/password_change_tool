import os
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
    def __init__(self, name=None, matches=None, password_rules=None, steps=None, javascript_enabled=True):
        self.name = name
        self.matches = matches or []
        self.password_rules = password_rules or {}
        self.steps = steps
        self.javascript_enabled = javascript_enabled

    @classmethod
    def load_rules(cls):
        # load yaml files from rules/ dir
        rules = []
        for subdir, dirs, files in os.walk(data_path('rules')):
            for file in files:
                if file.endswith('.yaml'):
                    with open(os.path.join(subdir, file), 'rb') as f:
                        rules.append(Rule(**yaml.load(f)))
        return rules

    @classmethod
    def attach_rules(cls, logins):
        """ Given list of logins, set login['rule'] to matching rule for each, or else login['error'] """
        rules = cls.load_rules()
        for login in GlobalState.logins:
            for rule in rules:
                if rule.applies_to(login):
                    login['rule'] = rule
                    break
            else:
                login['error'] = "Site not supported."

    def applies_to(self, login):
        if not login.get('domain', None):
            return False
        for match_domain in self.matches:
            if match_domain.startswith('.'):
                if login['domain'].endswith(match_domain) or login['domain'] == match_domain[1:]:
                    return True
            elif match_domain == login['domain']:
                return True
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
