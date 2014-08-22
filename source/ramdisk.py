import subprocess
import threading
import sys
import wx
from wx.lib.pubsub import pub
import os

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class RamDisk(object):
    """OSX-only ramdrive with file watches"""

    def __init__(self, name="RAM Disk", size=1024*25, path=None, device=None, source_image=None):
        self.name = name
        self.path = path or "/Volumes/%s" % name
        self.device = device
        self.size = size  # size is measured in kb
        self.watch_timer = None
        self.source_image = source_image  # path to a disk image to initialize the ramdisk from

    def __del__(self):
        self.unmount()

    def mount(self):
        if sys.platform=='darwin':
            # multiply size by 2 because hdiutil expects a size in 512-byte sectors
            self.device = subprocess.check_output(['hdiutil', 'attach', '-nomount', '-readwrite', 'ram://%s' % self.size*2]).strip()
            if self.source_image:
                subprocess.check_call(['asr', 'restore', '--noprompt', '--erase', '--source', self.source_image, '--target', self.device])
                subprocess.check_call(['diskutil', 'mount', self.device])
            else:
                subprocess.check_call(['diskutil', 'erasevolume', 'HFS+', self.name, self.device])
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

    def unwatch(self):
        if self.watch_timer:
            try:
                self.watch_timer.stop()
            except TypeError:
                # this can fail if the disk was already unmounted, causing a pointer error
                pass
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
