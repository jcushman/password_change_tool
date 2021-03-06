import json
import os
import tempfile
import threading
from urlparse import urlparse
import time
import sys
import subprocess
import wx
from wx.lib.pubsub import pub

from helpers import show_error, use_ramdisk, data_path, set_up_import_ramdisk
from managers.base import BaseImporter
from models import GlobalState, FileHandler
import platform_tools
from ramdisk import RamDisk
from crypto import secure_delete, set_access_control_for_import_folder
from widgets import SizerPanel

wildcard = "1Password Interchange File (*.1pif)|*.1pif"

class OnePasswordImporter(BaseImporter):
    display_name = "1Password"

    def __init__(self, *args, **kwargs):
        super(OnePasswordImporter, self).__init__(*args, **kwargs)
        GlobalState.onepassword = {}
        pub.subscribe(self.show_import_instructions, "onepassword__show_import_instructions")

    def get_password_data(self):
        if GlobalState.args:
            OnePasswordGetFile.process_file(GlobalState.args[0])
        else:
            # try to load ramdisk:

            # show wait screen
            pub.sendMessage("wait")

            # subscribe to success/failure messages
            pub.subscribe(self.ramdisk_loaded, 'ramdisk.loaded')
            pub.subscribe(self.ramdisk_loaded, 'ramdisk.failed')

            # start loading in background
            set_up_import_ramdisk()

    def save_changes(self, changed_entries):
        GlobalState.controller.show_panel(GetOutputLocationPanel, changed_entries=changed_entries)

    def show_import_instructions(self, import_file_path):
        GlobalState.controller.show_panel(ImportInstructionsPanel, import_file_path=import_file_path)

    def ramdisk_loaded(self):
        GlobalState.controller.show_panel(OnePasswordGetFile)

    @classmethod
    def get_file_handlers(self):
        return [
            FileHandler('1pif', '1Password Interchange File', OnePasswordGetFile.process_file)
        ]


class OnePasswordGetFile(SizerPanel):
    def add_controls(self):
        if hasattr(GlobalState, 'ramdisk'):

            self.add_text("""
                First you'll need to export your accounts from 1Password.

                We've created a secure virtual drive to safely store your passwords while we change them. Your passwords won't be written to disk.

                To export your accounts from 1Password, go to "File -> Export -> All Items ..." and save the file inside the "FreshPass Secure Disk" drive. You can pick which passwords you want to update on the next screen.
            """)
            #self.add_button("Open 1Password", None)
            pub.subscribe(self.watch_files, 'ramdisk.files_added')

        else:
            # platform doesn't support ramdisk

            self.add_text("""
                First you'll need to export your accounts from 1Password.

                IMPORTANT: Your password file will NOT leave your computer, but it will also NOT be encrypted. Make sure you keep it safe and delete it after we're done.

                To export your accounts from 1Password, go to "File -> Export -> All Items ...". You can pick which passwords you want to update on the next screen.

                Select your exported file:
             """)
            self.add_button("Choose 1Password File", self.choose_file)

    def watch_files(self, event_type, path, is_directory):
        if not is_directory and path.endswith('.1pif'):
            print "processing", path

            # raise to front
            GlobalState.controller.frame.Iconize(False)
            GlobalState.controller.frame.Raise()
            platform_tools.bring_to_front()

            GlobalState.ramdisk.unwatch()
            self.process_file(path)
            secure_delete(path)


    def choose_file(self, evt):
        dlg = wx.FileDialog(
            self, message="Choose a file",
            # defaultDir=os.getcwd(),
            defaultFile="",
            wildcard=wildcard,
            style=wx.OPEN | wx.CHANGE_DIR
        )

        if dlg.ShowModal() == wx.ID_OK:
            OnePasswordGetFile.process_file(dlg.GetPath())

    @classmethod
    def process_file(cls, path):
        entries = []

        original_path = path
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
            show_error("No password entries were found in that file. Are you sure it is a 1Password interchange file?")
            return

        GlobalState.onepassword['original_path'] = original_path

        def set_error(entry, error="Entry must have a location, username, and password."):
            entry['error'] = error

        for entry in entries:
            entry['label'] = entry['data']['title']

            if entry['data'].get('trashed', None):
                set_error(entry, "Item is in trash.")
                continue

            if not 'location' in entry['data'] or not 'secureContents' in entry['data'] or not 'fields' in entry['data']['secureContents']:
                set_error(entry)
                continue

            entry['location'] = entry['data'].get("location", None)
            entry['id'] = entry['data'].get("uuid", None)
            if not entry['location'] or not entry['id']:
                set_error(entry)
                continue

            parsed_url = urlparse(entry['location'])
            entry['domain'] = parsed_url.netloc
            entry['scheme'] = parsed_url.scheme
            if not entry['domain']:
                set_error(entry)
                continue

            for field in entry['data']['secureContents']['fields']:
                for target in ('username', 'password'):
                    if field.get('designation', None) == target:
                        entry[target] = field.get('value', None)
                        break

            if not entry.get('username', None) or not entry.get('password', None):
                set_error(entry)
                continue

        GlobalState.logins = entries
        pub.sendMessage("got_password_entries")


class GetOutputLocationPanel(SizerPanel):
    temp_file_path = None

    def __init__(self, parent, changed_entries):
        super(GetOutputLocationPanel, self).__init__(parent)
        self.changed_entries = changed_entries

    def add_controls(self):
        self.add_text("We can export your passwords directly to your 1Password application, if you use the default settings, "
                      "or you can export a .1pif file and import it into 1Password yourself. What would you like to do?")
        self.add_button("Send my passwords to 1Password", self.direct_export, flags=wx.TOP|wx.LEFT)
        self.add_button("Save .1pif file", self.choose_file, flags=wx.TOP|wx.LEFT)
        self.add_text("IMPORTANT: If you choose this option, the .1pif file will contain unencrypted passwords. Save it somewhere safe.", flags=wx.TOP|wx.LEFT, border=30)
        self.add_text("Do not leave this screen until you have verfied that your new passwords made it into 1Password.", border=30)
        self.add_button("OK, all set", self.done)

    def direct_export(self, evt):
        # create temp file
        temp_file = tempfile.NamedTemporaryFile(
            suffix='.1pif',
            delete=False,
            dir=GlobalState.ramdisk.path if hasattr(GlobalState, 'ramdisk') else None)
        self.save_file(temp_file)
        temp_file.close()

        # open temp file in 1Password
        temp_file_path = temp_file.name
        if sys.platform.startswith('darwin'):
            subprocess.call(('open', temp_file_path))
        elif os.name == 'nt':
            os.startfile(temp_file_path)
        elif os.name == 'posix':
            subprocess.call(('xdg-open', temp_file_path))

        self.temp_file_path = temp_file_path

    def choose_file(self, evt):
        default_dir, default_file = os.path.split(GlobalState.onepassword["original_path"])
        default_file = default_file.replace(".1pif", "_reimport.1pif")
        dlg = wx.FileDialog(
            self, message="Choose a file",
            defaultDir=default_dir,
            defaultFile=default_file,
            wildcard=wildcard,
            style=wx.SAVE
        )

        if dlg.ShowModal() == wx.ID_OK:
            with open(dlg.GetPath(), 'wb') as out_file:
                self.save_file(out_file)

    def save_file(self, out_file):
        epoch_seconds = int(time.time())
        for entry in self.changed_entries:
            out = entry['data']
            for field in out['secureContents']['fields']:
                if field.get('designation', None) == 'password':
                    field['value'] = entry['new_password']
            if not 'passwordHistory' in out:
                out['passwordHistory'] = []
            out['passwordHistory'].insert(0, {'value':entry['password'], 'time':epoch_seconds})
            out_file.write(json.dumps(out)+"\n"+entry['separator_line'])

    def done(self, evt):
        if self.temp_file_path:
            secure_delete(self.temp_file_path)
        pub.sendMessage("finished")

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