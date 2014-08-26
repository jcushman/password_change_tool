from contextlib import contextmanager
import json
import time

import crypto
from global_state import GlobalState


class ObjectEncoder(json.JSONEncoder):
    def default(self, o):
        from models import Rule
        if isinstance(o, Rule):
            return o.file_name
        if hasattr(o, '__dict__'):
            return o.__dict__
        return super(ObjectEncoder, self).default(o)

def serialize(data):
    return ObjectEncoder().encode(data)

def deserialize(data):
    return json.loads(data)

def save_data(data):
    crypto.save_secure_data(serialize(data))

def get_data():
    data = crypto.load_secure_data()
    if data:
        data = deserialize(data)
    else:
        data = {}
    return data

def start_log(manager_key):
    if not hasattr(GlobalState, 'log_id'):
        GlobalState.log_id = crypto.generate_password(10)
    data = get_data()
    if not data.get(GlobalState.log_id):
        data[GlobalState.log_id] = {'time':time.time(),'entries':[],'manager':manager_key}
    save_data(data)

def delete_log(log_id):
    data = get_data()
    if log_id in data:
        del data[log_id]
        if data:
            save_data(data)
        else:
            crypto.delete_secure_data()

@contextmanager
def edit_log():
    data = get_data()
    yield data[GlobalState.log_id]
    save_data(data)

def append_entry(entry):
    with edit_log() as log:
        log['entries'].append(entry)

def replace_last_entry(entry):
    with edit_log() as log:
        log['entries'][-1] = entry

def get_nonempty_logs():
    """
        Clear out any logs from storage that don't contain password update attempts.
        Then return the remaining logs that do contain attempts.
    """
    data = get_data()
    if not data:
        return None

    new_data = {}
    log_removed = False
    for key, log in data.items():
        for entry in log['entries']:
            if entry.get('update_attempted'):
                new_data[key] = log
                break
        else:
            log_removed = True

    if not new_data:
        crypto.delete_secure_data()
    elif log_removed:
        save_data(new_data)

    return new_data