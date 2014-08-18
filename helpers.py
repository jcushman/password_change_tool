import os
import sys
import subprocess
import re
import wx
from wx.lib.pubsub import pub


def get_data_dir():
    if hasattr(sys, "frozen"):
        this_module = unicode(sys.executable, sys.getfilesystemencoding())
        if sys.platform == 'darwin':
            return os.path.dirname(this_module)
        else:
            raise NotImplementedError("Don't know where to find resources on this OS yet.")
    # running as regular script
    return os.path.dirname(__file__)

def data_path(path):
    return os.path.join(get_data_dir(), path)

def bind_click_event(button, message, **kwargs):
    button.Bind(wx.EVT_BUTTON,
                lambda evt: pub.sendMessage(message, **kwargs))
    return button

def show_message(message, title='', options=wx.OK):
    dlg = wx.MessageDialog(None, message, title, options)
    dlg.ShowModal()
    dlg.Destroy()

def show_error(message, title="Error"):
    show_message(message, title)

def ask(parent=None, message=''):
    dlg = wx.TextEntryDialog(parent, message)
    dlg.ShowModal()
    result = dlg.GetValue()
    dlg.Destroy()
    return result

def load_log_file(log_file_path):
    try:
        return open(log_file_path, 'a')
    except OSError:
        show_error("Can't write to selected log file.")

def secure_delete(file_path):
    try:
        subprocess.check_call(['srm', '-m', '-f', file_path])
    except subprocess.CalledProcessError:
        with open(file_path, "wb") as file:
            file.write("*" * os.path.getsize(file_path))
        os.unlink(file_path)

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


class SizerPanel(wx.Panel):
    def __init__(self, parent):
        super(SizerPanel, self).__init__(parent=parent)
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.add_controls()
        self.sizer.Add((30,30))
        self.SetSizer(self.sizer)

    def add_controls(self):
        raise NotImplementedError

    def add_text(self, text, flags=wx.TOP, border=0):
        from models import GlobalState
        text = "\n".join(line.strip() for line in text.strip().split("\n")) # remove whitespace at start of each line
        text_widget = wx.StaticText(self, label=text)
        self.sizer.Add(text_widget, 0, flags, border)

        # This is an ugly hack to wrap the text to the width of the frame,
        # before the panel is actually added to the frame.
        # It would be nice if this was handled by some sort of layout event instead.
        text_widget.Wrap(GlobalState.controller.frame.GetSize()[0]-140-border)

    def add_button(self, label, handler, flags=wx.TOP, border=30):
        button = wx.Button(self, label=label)
        self.Bind(wx.EVT_BUTTON, handler, button)
        self.sizer.Add(button, 0, flags, border)
        return button