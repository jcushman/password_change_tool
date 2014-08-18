import re
import sys
from models import Rule


def process_selenium_ide_file(input_path):
    with open(input_path) as file:
        text = file.read()
    text = re.sub('^\s*','',text,flags=re.MULTILINE)  # strip spaces from start of lines to simplify matching
    text = text.split('<tbody>\n<tr>\n<td>',1)[1].split('</td>\n</tr>\n</tbody>')[0]  # remove head and tail
    text = text.replace('</td>\n<td>', '", "')  # turn table cells to commas
    text = text.replace('</td>\n</tr>\n<tr>\n<td>', '"]\n  - ["')  # turn table rows to arrays
    text = """name: <<name>>
matches:
  - <<url>>
steps:
  # log in
  - ["%s"]
""" % text
    text = text.replace(', ""]\n', ']\n')  # remove empty third cells
    text = re.sub(r'^  - \[\"(\w+)\"', r'  - [\1', text, flags=re.MULTILINE)  # remove quotes around commands
    text = re.sub(r'^(  - \[\w+)AndWait', r'\1', text, flags=re.MULTILINE)  # remove 'AndWait' from commands

    # use stderr for prompts so we can pipe to stdout
    sys.stderr.write("Username: ")
    text = text.replace(raw_input(), "{{ username }}")
    sys.stderr.write("Old password: ")
    text = text.replace(raw_input(), "{{ old_password }}")
    sys.stderr.write("New password: ")
    text = text.replace(raw_input(), "{{ new_password }}")

    print text

def list_rules():
    for rule in Rule.load_rules():
        print "* %s" % rule.name