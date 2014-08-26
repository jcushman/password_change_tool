import StringIO
from datetime import datetime
import threading
from time import sleep
import wx
import wx.animate
from wx.lib.pubsub import pub
from browser import run_step as browser_run_step, get_browser, WINDOW_SIZE as BROWSER_WINDOW_SIZE, BrowserException

from helpers import ask, get_password_managers, data_path
from models import Rule
from global_state import GlobalState
import crypto
from widgets import SizerPanel, CheckListCtrl
import secure_log


class LogDataPanel(SizerPanel):
    selected_item = None

    def __init__(self, *args, **kwargs):
        self.log_data = kwargs.pop('log_data').items()
        super(LogDataPanel, self).__init__(*args, **kwargs)

    def add_controls(self):
        log_count = len(self.log_data)

        self.add_text("""
            Your keychain indicates that this app may have closed before you could export your passwords
            back to your password manager. Would you like to export those passwords now?
        """)

        password_managers = get_password_managers()

        self.log_list = self.add_list(
            ['Manager', 'Date'],
            [(
                password_managers[log['manager']].display_name,
                datetime.fromtimestamp(log['time']).strftime('%b. %d, %y at %I:%M%p')
            ) for key, log in self.log_data]
        )

        self.Bind(wx.EVT_LIST_ITEM_SELECTED, self.item_selected, self.log_list)
        self.Bind(wx.EVT_LIST_ITEM_DESELECTED, self.item_deselected, self.log_list)

        self.export_button = self.add_button('Export passwords from selected log', self.export_selected)
        self.export_button.Disable()
        self.add_button('No thanks, delete %s' % ('this log' if log_count == 1 else 'these logs'), self.clear_log)
        self.add_button('Decide later', self.skip)

    def clear_log(self, evt):
        crypto.delete_secure_data()
        pub.sendMessage('start')

    def skip(self, evt):
        pub.sendMessage('start')

    def item_selected(self, evt):
        self.selected_item = evt.m_itemIndex
        self.export_button.Enable()

    def item_deselected(self, evt):
        self.selected_item = None
        self.export_button.Disable()

    def export_selected(self, evt):
        GlobalState.selected_recovery_log, GlobalState.recovery_log_data = self.log_data[self.selected_item]
        pub.sendMessage('export_log')


class ExportLogPanel(SizerPanel):
    def add_controls(self):
        log = GlobalState.recovery_log_data
        GlobalState.password_manager = get_password_managers()[log['manager']]()
        GlobalState.selected_logins = logins = [entry for entry in log['entries'] if entry.get('update_attempted')]

        self.add_text("""According to our log, the accounts listed below were updated on a previous run.""")
        self.add_button("Export new passwords to %s" % GlobalState.password_manager.display_name, self.export)

        self.add_text("Details:", border=30)

        logins.sort(key=lambda login: login['label'].lower())
        self.add_list(
            ("Login", "Domain", "User", "Status"),
            [(l['label'], l.get('domain', ''), l.get('username', ''), l.get('update_error', 'Success')) for l in logins]
        )

    def export(self, evt):
        pub.sendMessage('export_changes')


class WaitPanel(SizerPanel):
    def add_controls(self):
        w, h = GlobalState.controller.frame.GetSize()
        gif = wx.animate.GIFAnimationCtrl(self, -1, data_path('resources/loader.gif'), pos=(w/2-16-70, h/2-16))
        gif.GetPlayer().UseBackgroundColour(True)
        gif.Play()


class ChoosePasswordManagerPanel(SizerPanel):
    def add_controls(self):
        self.add_text("""
            This tool will help you change passwords stored in your password manager.

            To get started, choose your password manager:
        """)
        self.add_button("1Password", self.button_clicked, flags=wx.ALL, border=30)

    def button_clicked(self, evt):
        pub.sendMessage("password_manager_selected", password_manager="onepassword")


class ChoosePasswordsPanel(SizerPanel):
    def add_controls(self):
        self.add_text("""
            Select the passwords you would like to update.
        """)

        # process logins for list
        Rule.attach_rules(GlobalState.logins)
        GlobalState.matched_logins = matched_logins = [login for login in GlobalState.logins if not login.get('error')]

        parent = self
        class NotifyChecklistCtrl(CheckListCtrl):
            def OnCheckItem(self, index, flag):
                super(NotifyChecklistCtrl, self).OnCheckItem(index, flag)
                if self.selected_indexes:
                    parent.continue_button.Enable()
                else:
                    parent.continue_button.Disable()

        matched_logins.sort(key=lambda login: (login['rule'].name.lower(), login['label'].lower()))
        self.checklist = checklist = self.add_list(
            ("Site", "Account Title", "User"),
            [(l['rule'].name, l['label'], l.get('username', '')) for l in matched_logins],
            ListClass=NotifyChecklistCtrl
        )

        self.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.item_activated, checklist)
        self.Bind(wx.EVT_LIST_ITEM_SELECTED, self.item_selected, checklist)
        self.Bind(wx.EVT_LIST_ITEM_DESELECTED, self.item_deselected, checklist)

        self.continue_button = self.add_button("Change Selected Passwords", self.change_passwords)
        self.continue_button.Disable()

    def item_selected(self, evt):
        print "selected"
        pass
        #self.checklist.CheckItem(evt.m_itemIndex, True)

    def item_deselected(self, evt):
        print "deselected"
        pass
        # self.checklist.CheckItem(evt.m_itemIndex, False)

    def item_activated(self, evt):
        print "activated"
        pass
        # self.checklist.CheckItem(evt.m_itemIndex, False)

    def change_passwords(self, evt):
        logins = GlobalState.matched_logins
        GlobalState.selected_logins = [logins[index] for index in self.checklist.selected_indexes]
        pub.sendMessage("passwords_selected")


class ChangePasswordsPanel(SizerPanel):
    screenshot = None

    def __init__(self, parent):
        super(ChangePasswordsPanel, self).__init__(parent)
        self.update_thread = threading.Thread(target=self.update_passwords)
        self.update_thread.start()

    def add_controls(self):
        self.add_text("""
            Now we'll try to update each of your passwords.

            Don't worry if we get stuck for a while -- we'll let you know at the end what we were able to change and what you'll have to change manually.
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

        secure_log.start_log(GlobalState.password_manager_key)

        for login in GlobalState.selected_logins:
            rule = login['rule']

            # generate password and start log
            new_password = rule.generate_password()
            login['new_password'] = new_password
            secure_log.append_entry(login)

            success = rule.execute(self, login)
            secure_log.replace_last_entry(login)  # save success or error
            if success:
                changed_entries.append(login)

        # use CallAfter to send message from this thread back to the main thread
        wx.CallAfter(pub.sendMessage, 'update_complete')


class ResultsPanel(SizerPanel):
    def add_controls(self):
        logins = GlobalState.selected_logins
        update_count = len(logins)
        successful_count = sum(1 for login in logins if login.get('update_success',None))
        error_count = update_count - successful_count

        if successful_count:
            self.add_text("""
                Finished! We successfully updated %s account%s. Now you will need to export your new passwords back to %s.
            """ % (successful_count, ('' if successful_count==1 else 's'), GlobalState.password_manager.display_name))
            self.add_button("Export new passwords to %s" % GlobalState.password_manager.display_name, self.export)
        else:
            self.add_text("Finished! None of your passwords were changed.")
            self.add_button("Quit", self.quit)

        error_text = ''
        if error_count:
            error_text = "%s account%s could not be updated. " % (error_count, '' if error_count==1 else 's')

        self.add_text(error_text+"Details:", border=30)

        logins.sort(key=lambda login: login['label'].lower())
        self.add_list(
            ("Login", "Domain", "User", "Status"),
            [(l['label'], l.get('domain', ''), l.get('username', ''), 'Not changed' if l.get('update_error') else 'Success') for l in logins]
        )

    def export(self, evt):
        pub.sendMessage('export_changes')

    def quit(self, evt):
        pub.sendMessage('exit')


class FinishedPanel(SizerPanel):
    def add_controls(self):
        if hasattr(GlobalState, 'selected_recovery_log'):
            self.add_text("Log recovery complete!")
        else:
            self.add_text("All done!")
        self.add_button("Return to home screen", self.return_home)
        self.add_button("Quit", self.quit)

    def quit(self, evt):
        pub.sendMessage('exit')

    def return_home(self, evt):
        GlobalState.reset()
        pub.sendMessage('start')