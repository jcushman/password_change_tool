import json
import os
from urlparse import urlparse
import time
import sys
import subprocess
import wx
from wx.lib.pubsub import pub

from helpers import SizerPanel, show_error

wildcard = "1Password Interchange File (*.1pif)|*.1pif"

class OnePasswordImporter(object):
    def __init__(self, controller):
        self.controller = controller
        pub.subscribe(self.show_import_instructions, "onepassword__show_import_instructions")

    def get_password_data(self):
        self.controller.show_panel(OnePasswordGetFile)

    def save_changes(self, changed_entries):
        self.controller.show_panel(GetOutputLocationPanel, changed_entries=changed_entries)

    def show_import_instructions(self, import_file_path):
        self.controller.show_panel(ImportInstructionsPanel, import_file_path=import_file_path)


class OnePasswordGetFile(SizerPanel):
    def add_controls(self):
        self.add_text("""
            First you'll need to export your passwords from 1Password so we can import them.

            IMPORTANT: Your password file will NOT leave your computer, but it will also NOT be encrypted. Make sure you keep it safe and delete it after we're done.

            To export your logins from 1Password, select the items you want to export and go to "File -> Export -> Selected Items ...".

            Select your exported file:
         """)
        self.add_button("Choose 1Password File", self.choose_file)


    def choose_file(self, evt):
        dlg = wx.FileDialog(
            self, message="Choose a file",
            # defaultDir=os.getcwd(),
            defaultFile="",
            wildcard=wildcard,
            style=wx.OPEN | wx.CHANGE_DIR
        )

        if dlg.ShowModal() == wx.ID_OK:
            self.process_file(dlg.GetPath())

    def process_file(self, path):
        entries = []
        file_id = None

        if os.path.isdir(path):
            path = os.path.join(path, "data.1pif")

        last_entry = None
        with open(path, 'rb') as file:
            for line in file:
                if line.startswith('{'):
                    entry = {
                        'data':json.loads(line)
                    }
                    entries.append(entry)
                    last_entry = entry
                elif line.startswith('***') and last_entry:
                    last_entry['separator_line'] = line
                else:
                    print "Unrecognized line:", line

        if not entries:
            show_error("No password entries were found in that file. Are you sure it was a 1Password interchange file?")
            return

        processed_entries = []
        for entry in entries:
            if not 'location' in entry['data'] or not 'secureContents' in entry['data'] or not 'fields' in entry['data']['secureContents']:
                continue

            entry['location'] = entry['data'].get("location", None)
            entry['id'] = entry['data'].get("uuid", None)
            if not entry['location'] or not entry['id']:
                continue

            entry['domain'] = urlparse(entry['location']).netloc
            if not entry['domain']:
                continue

            for field in entry['data']['secureContents']['fields']:
                for target in ('username', 'password'):
                    if field.get('designation', None) == target:
                        entry[target] = field.get('value', None)
                        break

            if not entry.get('username', None) or not entry.get('password', None):
                continue

            processed_entries.append(entry)

        if not processed_entries:
            show_error("No entries in this file are eligible for updates. Exported entries must have a username, password, and website.")
            return

        pub.sendMessage("got_password_entries", entries=processed_entries)



class GetOutputLocationPanel(SizerPanel):
    def __init__(self, parent, changed_entries):
        super(GetOutputLocationPanel, self).__init__(parent)
        self.changed_entries = changed_entries

    def add_controls(self):
        self.add_text("""
            Your passwords have been updated. Next you will need to import your new passwords back into 1Password.

            IMPORTANT: This file will contain unencrypted passwords. Save it somewhere safe and delete it once you are done with it.
         """)
        self.add_button("Choose 1Password Export Destination", self.choose_file)

    def choose_file(self, evt):
        dlg = wx.FileDialog(
            self, message="Choose a file",
            # defaultDir=os.getcwd(),
            defaultFile="",
            wildcard=wildcard,
            style=wx.SAVE
        )

        if dlg.ShowModal() == wx.ID_OK:
            self.save_file(dlg.GetPath())

    def save_file(self, path):
        epoch_seconds = int(time.time())
        with open(path, 'wb') as out_file:
            for entry in self.changed_entries:
                out = entry['data']
                for field in out['secureContents']['fields']:
                    if field.get('designation', None) == 'password':
                        field['value'] = entry['new_password']
                if not 'passwordHistory' in out:
                    out['passwordHistory'] = []
                out['passwordHistory'].insert(0, {'value':entry['password'], 'time':epoch_seconds})
                out_file.write(json.dumps(out)+"\n"+entry['separator_line'])
        pub.sendMessage("onepassword__show_import_instructions", import_file_path=path)


class ImportInstructionsPanel(SizerPanel):
    def __init__(self, parent, import_file_path):
        super(ImportInstructionsPanel, self).__init__(parent)
        self.import_file_path = import_file_path

    def add_controls(self):
        self.add_text("""
            The last step is to import the file you just saved back into 1Password.

            You can do that manually by going to "File -> Import ...", or we can try to open it for you now:
        """)
        self.add_button("Open file in 1Password", self.open_file)
        self.add_button("All set", self.done)

    def open_file(self, evt):
        path = self.import_file_path
        if sys.platform.startswith('darwin'):
            subprocess.call(('open', path))
        elif os.name == 'nt':
            os.startfile(path)
        elif os.name == 'posix':
            subprocess.call(('xdg-open', path))

    def done(self, evt):
        pub.sendMessage("finished")