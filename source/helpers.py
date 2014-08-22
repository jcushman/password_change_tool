import os
import sys
import wx
from wx.lib.pubsub import pub
import crypto
from ramdisk import RamDisk


def get_data_dir():
    if hasattr(sys, "frozen"):
        this_module = unicode(sys.executable, sys.getfilesystemencoding())
        if sys.platform == 'darwin':
            return os.path.dirname(this_module)
        else:
            raise NotImplementedError("Don't know where to find resources on this OS yet.")
    # running as regular script
    return os.path.dirname(os.path.dirname(__file__))

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

def use_ramdisk():
    """ Return True if password managers can use a ramdisk on this platform for file exchange. """
    return sys.platform == 'darwin'

def get_password_managers():
    # process password manager plugins
    # TODO: make this auto-discover and move it somewhere sensible
    from managers.onepassword import OnePasswordImporter
    return {
        'onepassword':OnePasswordImporter
    }

def set_up_import_ramdisk(name="FreshPass Secure Disk"):
    from models import GlobalState
    ramdisk = RamDisk(name)
    ramdisk.mount()
    GlobalState.cleanup_message.send({'action': 'unmount', 'path': ramdisk.path, 'device': ramdisk.device})
    crypto.set_access_control_for_import_folder(ramdisk.path)
    ramdisk.watch()
    return ramdisk
