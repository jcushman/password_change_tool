import subprocess
import sys

from .lib.unix import *

def run_applescript(script='', file=None, background=False):
    call = ['osascript']
    if file:
        call += [file]
    else:
        for line in script.split('\n'):
            call += ['-e', line]
    if background:
        return subprocess.Popen(call)
    else:
        return subprocess.check_output(call)

def authopen(path):
    """
        Open given file by requesting heightened permission from the user.
    """
    #TODO: This should really return a file-like object.
    data = subprocess.check_output(['/usr/libexec/authopen', path])
    return data.split('\n')

def bring_to_front():
    """
        Bring this app to the front.
    """
    app_name = 'FreshPass' if hasattr(sys, "frozen") else 'Python'
    # this has to run in the background because the applescript will wait for us to respond before returning
    # if it runs in the foreground, we deadlock
    run_applescript('tell application "%s" to activate' % app_name, background=True)