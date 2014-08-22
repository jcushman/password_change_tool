import os
import pwd

from .base import *

def get_username():
    return pwd.getpwuid(os.getuid()).pw_name