import os
import sys
import wx
from wx.lib.pubsub import pub


def get_data_dir():
    if hasattr(sys, "frozen"):
        this_module = unicode(sys.executable, sys.getfilesystemencoding())
        if sys.platform == 'darwin':
            return os.path.join(os.path.dirname(os.path.dirname(this_module)), 'Resources')
        else:
            raise NotImplementedError("Don't know where to find resources on this OS yet.")
    # running as regular script
    return os.path.dirname(__file__)

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

def load_log_file(log_file_path):
    try:
        return open(log_file_path, 'a')
    except OSError:
        show_error("Can't write to selected log file.")

class SizerPanel(wx.Panel):
    def __init__(self, parent):
        super(SizerPanel, self).__init__(parent=parent)
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.add_controls()
        self.SetSizer(self.sizer)

    def add_controls(self):
        raise NotImplementedError

    def add_text(self, text, flags=wx.TOP, border=0):
        text = "\n".join(line.strip() for line in text.strip().split("\n")) # remove whitespace at start of each line
        self.sizer.Add(wx.StaticText(self, label=text), 0, flags, border)

    def add_button(self, label, handler, flags=wx.TOP, border=30):
        button = wx.Button(self, label=label)
        self.Bind(wx.EVT_BUTTON, handler, button)
        self.sizer.Add(button, 0, flags, border)
        return button