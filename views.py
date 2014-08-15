import StringIO
import json
import os
import sys
import threading
from time import sleep
from selenium.common.exceptions import NoSuchElementException, InvalidElementStateException
import wx
from wx.lib.pubsub import pub
from browser import run_step, get_browser, UnexpectedElementError, WINDOW_SIZE as BROWSER_WINDOW_SIZE

from helpers import SizerPanel, show_error


class ChoosePasswordManagerPanel(SizerPanel):
    def add_controls(self):
        self.add_text("""
            This tool will help you change passwords stored in your password manager.

            To get started, choose your password manager:
        """)
        self.add_button("1Password", self.button_clicked, flags=wx.ALL, border=30)

    def button_clicked(self, evt):
        pub.sendMessage("password_manager_selected", password_manager="onepassword")


class CreateLogPanel(SizerPanel):
    def add_controls(self):
        self.add_text("""
            Next, choose a location to save the log file. This will record all of the changes we make in case anything goes wrong.

            IMPORTANT: The log file will contain your new passwords unencrypted. Be sure to keep it safe and delete it after you're done with it.
        """)
        self.add_button("Choose Log File", self.choose_file)

    def choose_file(self, evt):
        dlg = wx.FileDialog(
            self, message="Choose a file",
            # defaultDir=os.getcwd(),
            defaultFile="",
            wildcard="*.log",
            style=wx.SAVE
        )

        while True:
            if dlg.ShowModal() == wx.ID_OK:
                log_file_path = dlg.GetPath()
                try:
                    log_file = open(log_file_path, 'a')
                except OSError:
                    show_error("Can't write to selected log file.")
                    continue
                log_file.write("==== Beginning update process ... ====\n\n")
                pub.sendMessage("log_file_selected", log_file=log_file)
            break


class ChangePasswordsPanel(SizerPanel):
    screenshot = None

    def __init__(self, parent, logins, log_file):
        super(ChangePasswordsPanel, self).__init__(parent)

        self.logins = logins
        self.log_file = log_file
        self.update_thread = threading.Thread(target=self.update_passwords)
        self.update_thread.start()

    def add_controls(self):
        self.add_text("""
            Now we'll update each of your passwords ...
        """)
        #TODO: self.add_button(label="Cancel", self.cancel)
        self.screenshot_well = wx.Panel(self, size=BROWSER_WINDOW_SIZE, style=wx.SUNKEN_BORDER | wx.SHAPED)
        self.screenshot_well_sizer = wx.BoxSizer(wx.VERTICAL)
        self.screenshot_well.SetSizer(self.screenshot_well_sizer)
        self.sizer.Add(self.screenshot_well, 1, wx.ALL | wx.SHAPED, 30)

    def update_screenshot(self, driver, stop_screenshots):
        while not stop_screenshots.isSet():
            screenshot_data = driver.get_screenshot_as_png()
            if screenshot_data:
                image = wx.ImageFromStream(StringIO.StringIO(screenshot_data), wx.BITMAP_TYPE_PNG)
                if self.screenshot:
                    width, height = self.screenshot.GetClientSize()
                    image = image.Scale(width, height, wx.IMAGE_QUALITY_HIGH)
                bitmap = wx.BitmapFromImage(image)
                screenshot = self.screenshot or wx.StaticBitmap(self.screenshot_well, wx.ID_ANY, size=BROWSER_WINDOW_SIZE)
                screenshot.SetBitmap(bitmap)
                if not self.screenshot:
                    self.screenshot = screenshot
                    self.screenshot_well_sizer.Add(self.screenshot, 1, wx.ALL | wx.SHAPED, 10)
                    self.screenshot_well_sizer.Layout()
        sleep(1)

    def update_passwords(self):
        changed_entries = []
        for rule, login in self.logins:
            new_password = rule.generate_password()
            self.log_file.write("Updating password for %s on %s to %s ... " % (login['username'], login['domain'], new_password))
            self.log_file.flush()
            driver = get_browser()

            # set up screenshot thread
            stop_screenshots = threading.Event()
            screenshot_thread = threading.Thread(target=self.update_screenshot, args=[driver, stop_screenshots])
            screenshot_thread.start()

            try:
                for i, step in enumerate(rule.steps):
                    print "Running", step
                    while len(step)<3:
                        step += [None]
                    step_type, opts = step[0], step[1:]

                    # handle templating
                    if step_type == 'type' and opts[1]:
                        for from_str, to_str in (('username', login['username']),
                                           ('old_password', login['password']),
                                           ('new_password', new_password)):
                            opts[1] = opts[1].replace("{{ %s }}" % from_str, to_str)

                    # run step
                    run_step(driver, step_type, opts)
            except (UnexpectedElementError, NoSuchElementException, InvalidElementStateException, AssertionError) as e:
                #import ipdb; ipdb.set_trace()
                if type(e) == NoSuchElementException:
                    message = json.loads(e.msg)['errorMessage']
                else:
                    message = str(e)
                self.log_file.write("Probably failed:\n    %s" % message)
                self.log_file.flush()
                show_error("Update process failed for %s on step %s: %s" % (
                    login['domain'], i+1, message))
                continue
            finally:
                stop_screenshots.set()

            # success
            self.log_file.write("Success.\n")
            self.log_file.flush()
            login['new_password'] = new_password
            changed_entries.append(login)

        pub.sendMessage('update_complete', changed_entries=changed_entries)


class FinishedPanel(SizerPanel):
    def add_controls(self):
        self.add_text("""
            All done! Remember to delete any files you created during this process that contain unencrypted passwords.
        """)
        self.add_button("Quit", self.quit)

    def quit(self, evt):
        pub.sendMessage('exit')