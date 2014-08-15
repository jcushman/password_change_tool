import StringIO
import json
import os
import sys
import threading
from time import sleep
from selenium.common.exceptions import NoSuchElementException, InvalidElementStateException
import wx
from wx.lib.mixins.listctrl import CheckListCtrlMixin
from wx.lib.pubsub import pub
from browser import run_step, get_browser, UnexpectedElementError, WINDOW_SIZE as BROWSER_WINDOW_SIZE

from helpers import SizerPanel, show_error, load_log_file
from models import GlobalState, Rule


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
                log_file = load_log_file(log_file_path)
                if not log_file:
                    continue
                GlobalState.log_file_path = log_file_path
                GlobalState.log_file = log_file
                pub.sendMessage("log_file_selected")
            break


class ChoosePasswordsPanel(SizerPanel):
    def add_controls(self):
        self.add_text("""
            Select the passwords you would like to update.

            A log of all changes will be stored to %s
        """ % GlobalState.log_file_path)

        self.selected_indexes = selected_indexes = set()

        continue_button = wx.Button(self, label="Change Selected Passwords")
        continue_button.Disable()
        self.Bind(wx.EVT_BUTTON, self.change_passwords, continue_button)

        class CheckListCtrl(wx.ListCtrl, CheckListCtrlMixin):
            def __init__(self, parent):
                wx.ListCtrl.__init__(self, parent, -1, style=wx.LC_REPORT)
                CheckListCtrlMixin.__init__(self)
                self.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.OnItemActivated)

            def OnItemActivated(self, evt):
                self.ToggleItem(evt.m_itemIndex)

            def OnCheckItem(self, index, flag):
                if flag:
                    selected_indexes.add(index)
                else:
                    selected_indexes.remove(index)
                if selected_indexes:
                    continue_button.Enable()
                else:
                    continue_button.Disable()

        list = CheckListCtrl(self)
        self.sizer.Add(list, 1, wx.EXPAND)

        for i, title in enumerate(("Login", "Domain", "User", "Reason unavailable")):
            list.InsertColumn(i, title)

        # process logins for list
        logins = GlobalState.logins
        Rule.attach_rules(logins)

        def login_sort_key(login):
            prefix = "A" if not login.get('error', None) else "B" if login.get('rule', None) else "C"
            return prefix + login['label'].lower()

        logins.sort(key=login_sort_key)

        # add logins to list
        for login_index, login in enumerate(logins):
            if not login.get('error',None):
                # insert line with checkbox
                index = list.InsertStringItem(sys.maxint, login['label'])
            else:
                # insert line with no checkbox
                item = wx.ListItem()
                item.SetId(sys.maxint)
                item.SetText(login['label'])
                index = list.InsertItem(item)
            for i, value in enumerate((login.get('domain', ''), login.get('username', ''), login.get('error', ''))):
                list.SetStringItem(index, i + 1, value)
            list.SetItemData(index, login_index)

        for i in range(4):
            list.SetColumnWidth(i, wx.LIST_AUTOSIZE)

        self.Bind(wx.EVT_LIST_ITEM_SELECTED, self.item_selected, list)
        self.Bind(wx.EVT_LIST_ITEM_DESELECTED, self.item_deselected, list)

        self.sizer.Add(continue_button, 0, wx.TOP, border=30)

    def item_selected(self, evt):
        print 'item selected: %s\n' % evt.m_itemIndex

    def item_deselected(self, evt):
        print 'item deselected: %s\n' % evt.m_itemIndex

    def change_passwords(self, evt):
        logins = GlobalState.logins
        GlobalState.selected_logins = [logins[index] for index in self.selected_indexes]
        pub.sendMessage("passwords_selected")

class ChangePasswordsPanel(SizerPanel):
    screenshot = None

    def __init__(self, parent):
        super(ChangePasswordsPanel, self).__init__(parent)
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
        log_file = GlobalState.log_file
        for login in GlobalState.selected_logins:
            rule = login['rule']
            new_password = rule.generate_password()
            log_file.write("Updating password for %s on %s to %s ... " % (login['username'], login['domain'], new_password))
            log_file.flush()
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
                log_file.write("Probably failed:\n    %s" % message)
                log_file.flush()
                show_error("Update process failed for %s on step %s: %s" % (
                    login['domain'], i+1, message))
                continue
            finally:
                stop_screenshots.set()

            # success
            log_file.write("Success.\n")
            log_file.flush()
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