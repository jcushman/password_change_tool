import base64
import json
import os
import string
import subprocess
from Crypto import Random
import sys
from Crypto.Random.random import choice, sample
import keyring
import simplecrypt

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
        subprocess.check_call(['srm', '-m', '-f', file_path])
    except subprocess.CalledProcessError:
        # fallback to overwriting with random data and deleting
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
        return simplecrypt.decrypt(get_hardware_id(), encrypted_data)

def delete_secure_data():
    keyring.delete_password("FreshPass Encrypted Log", "log")

def generate_password(length, allowed_chars=None, required_ranges=None):
    if not allowed_chars:
        allowed_chars = string.letters+string.digits
    # generate password
    password = ''.join(choice(allowed_chars) for _ in range(length))

    # if certain ranges of characters are required (e.g A-Z), make sure they're each in the password
    if required_ranges:
        # find a target character in the password to hold a letter from each required range
        indexes = sample(range(len(password)), len(required_ranges))
        # put a letter from each required range in the selected location
        for index, required_range in zip(indexes, required_ranges):
            password[index] = choice(required_range)

    return password