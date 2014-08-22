import subprocess
from .lib.unix import *

import helpers

def set_up_import_ramdisk(*args, **kwargs):
    ramdisk = helpers.set_up_import_ramdisk(*args, **kwargs)
    subprocess.call(['osascript', helpers.data_path('assets/configure disk image.scpt')])
    return ramdisk

def authopen(path):
    """
        Open given file by requesting heightened permission from the user.
    """
    #TODO: This should really return a file-like object.
    data = subprocess.check_output(['/usr/libexec/authopen', path])
    return data.split('\n')