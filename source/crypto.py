import base64
import json
import os
import string
import subprocess
from Crypto import Random
import sys
from Crypto.Random.random import choice, sample
import errno
import keyring
import keyring.backends.file
import simplecrypt

import platform_tools

####################################################################
# NOTE:
# This file collects functions that require cryptographic review,
# which they have not yet received.
#
# With that said, nothing we are doing here risks exposing password
# data to remote parties. We are using crypto only to make life harder
# for an attacker who already has read access to the user's files
# and/or keychain, at which point there is probably not much we
# can do to protect the user in any event.
####################################################################

def get_hardware_id():
    """
        Get a unique ID consistent to this computer.
        Ideally this would be something that can't be read from the filesystem.
    """
    if sys.platform=='darwin':
        out = subprocess.check_output("/usr/sbin/system_profiler SPHardwareDataType | fgrep 'Hardware UUID' | awk '{print $NF}'", shell=True).strip()
    else:
        raise NotImplementedError("Can't get UUID for platform "+sys.platform)
    if not out:
        raise Exception("Failed to get UUID")
    return out

def secure_delete(file_path):
    """
        Delete file and wipe it from disk.
    """
    try:
        # use system tool -- should work on mac and linux
        subprocess.check_call(['srm', '-m', '-f', '-r', file_path])
    except subprocess.CalledProcessError:
        # fallback to overwriting with random data and deleting
        # TODO: this should be recursive, like the srm call
        with open(file_path, "wb") as file:
            file.write(Random.new().read(os.path.getsize(file_path)))
        os.unlink(file_path)

def save_secure_data(data):
    """
        Save a data structure such that it can only be read from the user's keychain,
        while they are logged in, and only with knowledge of the user's hardware ID.
    """
    encrypted_data = simplecrypt.encrypt(get_hardware_id(), data)
    encoded_data = base64.b64encode(encrypted_data)
    keyring.set_password("FreshPass Encrypted Log", "log", encoded_data)

def load_secure_data():
    """
        Load data stored by save_secure_data.
    """
    encoded_data = keyring.get_password("FreshPass Encrypted Log", "log")
    if encoded_data:
        encrypted_data = base64.b64decode(encoded_data)
        decrypted_data = simplecrypt.decrypt(get_hardware_id(), encrypted_data)
        return decrypted_data

def delete_secure_data():
    keyring.delete_password("FreshPass Encrypted Log", "log")

named_ranges = {
    'a-z': string.lowercase,
    'A-Z': string.uppercase,
    '0-9': string.digits,
}
def generate_password(length, allowed_chars=None, required_ranges=None):
    if not allowed_chars:
        allowed_chars = string.letters+string.digits
    # generate password
    password = [choice(allowed_chars) for _ in range(length)]

    # if certain ranges of characters are required (e.g A-Z), make sure they're each in the password
    if required_ranges:
        # find a target character in the password to hold a letter from each required range
        indexes = sample(range(len(password)), len(required_ranges))
        # put a letter from each required range in the selected location
        for index, required_range in zip(indexes, required_ranges):
            if required_range in named_ranges:
                required_range = named_ranges[required_range]
            password[index] = choice(required_range)

    return ''.join(password)

def set_access_control_for_import_folder(path):
    """
        Set access control for given directory so that current user can write files to it,
        but no one including user can read files from it.
    """
    if sys.platform == 'darwin':
        subprocess.check_call(['chmod', '-R', 'u+rw,o-rwx', path])
    else:
        raise NotImplementedError("Can't set access controls for platform "+sys.platform)
    # if sys.platform=='darwin':
    #     def chmod(*args):
    #         subprocess.call(['chmod']+list(args)+[path])
    #     chmod('-N')
    #     chmod('+a', 'everyone deny list,read,write,append,delete,execute,directory_inherit,file_inherit')
    #     chmod('+a#', '0', '%s allow write,list,file_inherit,directory_inherit,add_subdirectory' % platform_tools.get_username())
    # else:
    #     raise NotImplementedError("Can't set access controls for platform "+sys.platform)
    # # confirm access restrictions
    # test_file_path = os.path.join(path, 'test')
    # with open(test_file_path, 'w') as f:
    #     f.write('test')
    # try:
    #     open(test_file_path, 'r')
    #     raise Exception("Attempt to set access controls failed.")
    # except IOError as e:
    #     if e.errno != errno.EACCES:
    #         raise
    # os.unlink(test_file_path)