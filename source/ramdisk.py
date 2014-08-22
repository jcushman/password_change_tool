import subprocess
import threading
import sys
import time
import wx
from wx.lib.pubsub import pub
import os

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class RamDisk(object):
    """OSX-only ramdrive with file watches"""

    def __init__(self, name="RAM Disk", size=1024*25, path=None, device=None):
        self.name = name
        self.path = path or "/Volumes/%s" % name
        self.device = device
        self.size = size
        self.watch_timer = None

    def __del__(self):
        self.unmount()

    def mount(self):
        if sys.platform=='darwin':
            self.device = subprocess.check_output(['hdiutil', 'attach', '-nomount', '-readwrite', 'ram://%s' % self.size]).strip()
            subprocess.check_call(['diskutil', 'erasevolume', 'HFS+', self.name, self.device])

            # it would be cool to be able to initialize the ram disk from a disk image
            # something like this should work, but right now when you view the resulting disk in Finder it re-mounts a duplicate version for some reason
            # subprocess.check_call(['asr', 'restore', '--noprompt', '--erase', '--source', data_path('assets/mac_disk_image_compressed.dmg'), '--target', self.device])
        else:
            raise NotImplementedError

    def watch(self):
        """publish any top-level files added to the drive"""
        if self.watch_timer:
            raise Exception("only one watch can be active on a ramdisk")

        class DelayedEventHandler(FileSystemEventHandler):
            """
                Event handler that sends file change messages only if no other event
                 occurs for that file within .1 seconds.
            """
            previous_events = {}

            def dispatch(self, event):
                self.previous_events[event.src_path] = event
                threading.Timer(.5, self.check_time, args=[event]).start()

            def check_time(self, event):
                if self.previous_events[event.src_path] == event:
                    wx.CallAfter(pub.sendMessage, 'ramdisk.files_added',
                                 event_type=event.event_type,
                                 path=event.src_path,
                                 is_directory=event.is_directory)


        observer = Observer()
        observer.schedule(DelayedEventHandler(), self.path, recursive=True)
        observer.start()

        self.watch_timer = observer

        # self.current_files = set(os.listdir(self.path))
        # def check():
        #     new_files = set(os.listdir(self.path))
        #     changed_files = new_files - self.current_files
        #     if changed_files:
        #         self.current_files = new_files
        #         wx.CallAfter(pub.sendMessage, 'ramdisk.files_added', paths=[self.absolute_path(name) for name in changed_files])
        #     self.watch_timer = threading.Timer(0.1, check)
        #     self.watch_timer.start()
        # check()

    def unwatch(self):
        if self.watch_timer:
            self.watch_timer.stop() #cancel()
            self.watch_timer = None

    def unmount(self):
        """terminate any watches and unmount the drive"""
        self.unwatch()
        if sys.platform == 'darwin':
            subprocess.call(["umount", "-f", self.path])
            subprocess.call(["hdiutil", "detach", self.device])
        else:
            raise NotImplementedError

    def absolute_path(self, name):
        return os.path.join(self.path, name)
