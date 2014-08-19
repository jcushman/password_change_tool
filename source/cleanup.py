import multiprocessing
import os
import threading
import time
import signal
import psutil

from ramdisk import RamDisk


def start_cleanup_watcher():
    """
        Start a subprocess that will check every .2 seconds to make sure the parent process is still running,
        and if not, run cleanup and exit.

        We will return a pipe that can be used to add cleanup tasks to the queue, in the form

            pipe.send({'action':'foo'})

        See cleanup() for valid actions.
    """

    # subprocess
    def cleanup_watcher_process(output_pipe):
        this_process = psutil.Process(os.getpid())
        messages = []

        try:
            waiting = True
            while waiting:
                if output_pipe.poll(.2):
                    while output_pipe.poll():
                        message = output_pipe.recv()

                        if message['action'] == 'kill':
                            # grab a handle to the process as soon as it comes in,
                            # so we won't accidentally kill a different process with the same pid later
                            message['process'] = psutil.Process(message['pid'])

                        elif message['action'] == 'exit':
                            waiting = False
                            continue

                        messages.append(message)

                parent = this_process.parent()
                if not parent or parent.pid==1:
                    break

        except KeyboardInterrupt:
            pass
        finally:
            cleanup(messages)

    output_pipe, input_pipe = multiprocessing.Pipe()

    cleanup_process = multiprocessing.Process(target=cleanup_watcher_process, args=(output_pipe,))
    cleanup_process.start()

    return input_pipe


def cleanup(messages):
    print "running cleanup"
    print messages
    for message in messages:
        try:
            if message['action']=='unmount':
                ramdisk = RamDisk(path=message['path'])
                ramdisk.unmount()
            elif message['action']=='kill':
                message['process'].terminate()
        except Exception as e:
            print e