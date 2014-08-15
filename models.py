import os
import string
from Crypto.Random.random import choice, sample
import yaml
from helpers import get_data_dir

PASSWORD_LENGTH = 14
PASSWORD_CHARS = string.letters + string.digits


class Rule(object):
    def __init__(self, name=None, matches=None, password_rules=None, steps=None):
        self.matches = matches or []
        self.password_rules = password_rules or {}
        self.steps = steps

    @classmethod
    def load_rules(cls):
        # load yaml files from rules/ dir
        rules = []
        for subdir, dirs, files in os.walk(os.path.join(get_data_dir(), 'rules')):
            for file in files:
                with open(os.path.join(subdir, file), 'rb') as f:
                    rules.append(Rule(**yaml.load(f)))
        return rules

    def applies_to(self, login):
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

        # generate password from allowed_chars or PASSWORD_CHARS
        chars = self.password_rules.get('allowed_chars', PASSWORD_CHARS)
        password = ''.join(choice(chars) for _ in range(length))

        # if certain ranges of characters are required (e.g A-Z), make sure they're each in the password
        required_ranges = self.password_rules.get('required_ranges', [])
        if required_ranges:
            # find a target character in the password to hold a letter from each required range
            indexes = sample(range(len(password)), len(required_ranges))
            # put a letter from each required range in the selected location
            for index, required_range in zip(indexes, required_ranges):
                password[index] = choice(required_range)

        return password
