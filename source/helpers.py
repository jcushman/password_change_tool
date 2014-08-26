import ctypes
from multiprocessing.pool import ThreadPool
import os
import sys
import threading
import wx
from wx.lib.pubsub import pub

import crypto
import platform_tools
from ramdisk import RamDisk
from global_state import GlobalState


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
    """
        Mount a ramdisk in a background thread and configure it for file import.

        Callers can subscribe to 'ramdisk.loaded' and 'ramdisk.failed' to be alerted when load is complete.
        If successful, ramdisk object will be stored in GlobalState.ramdisk.

        Callers can subscribe to 'ramdisk.files_added' to be alerted when files are added to the disk.
    """
    def load_ramdisk():
        try:
            ramdisk = RamDisk(name, source_image=data_path('resources/mac_disk_image_compressed.dmg'))
            ramdisk.mount()
            GlobalState.cleanup_message.send({'action': 'unmount', 'path': ramdisk.path, 'device': ramdisk.device})
            if sys.platform == 'darwin':
                platform_tools.run_applescript(file=data_path('resources/display disk image.scpt'))
            crypto.set_access_control_for_import_folder(ramdisk.path)
            ramdisk.watch()
            GlobalState.ramdisk = ramdisk
            wx.CallAfter(pub.sendMessage, 'ramdisk.loaded')
        except NotImplementedError:
            wx.CallAfter(pub.sendMessage, 'ramdisk.failed')

    ramdisk_loading_thread = threading.Thread(target=load_ramdisk)
    ramdisk_loading_thread.start()

def get_first_result_from_threads(calls):
    calls = list(enumerate(calls))

    def run_func(call):
        i, call = call
        func = call[0]
        args = call[1] if len(call)>1 else []
        kwargs = call[2] if len(call)>2 else {}
        try:
            return i, func(*args, **kwargs)
        except Exception as e:
            return i, e

    pool = ThreadPool(processes=len(calls))
    result = pool.imap_unordered(run_func, calls).next()

    for thread in pool._pool:
        # via http://stackoverflow.com/a/15274929
        if not thread.isAlive():
            continue
        exc = ctypes.py_object(SystemExit)
        res = ctypes.pythonapi.PyThreadState_SetAsyncExc(
            ctypes.c_long(thread.ident), exc)
        if res == 0:
            raise ValueError("nonexistent thread id")
        elif res > 1:
            # """if it returns a number greater than one, you're in trouble,
            # and you should call it again with exc=NULL to revert the effect"""
            ctypes.pythonapi.PyThreadState_SetAsyncExc(thread.ident, None)
            raise SystemError("PyThreadState_SetAsyncExc failed")

    return result

