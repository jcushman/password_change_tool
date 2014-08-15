import wx
from wx.lib.pubsub import pub
from helpers import show_error, show_message
from models import Rule

import views


class MainFrame(wx.Frame):
    current_panel = None

    def __init__(self):
        super(MainFrame, self).__init__(None, title="Password Updater", size=(700,600))

        self.SetBackgroundColour(wx.WHITE)
        self.SetAutoLayout(True)

        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self.sizer)

    def switch_to_panel(self, panel, title):
        if self.current_panel:
            self.current_panel.Hide()

        self.SetTitle(title)
        self.sizer.Add(panel, 1, wx.EXPAND | wx.ALL, 30)
        self.current_panel = panel
        panel.SetAutoLayout(True)
        self.Layout()
        panel.sizer.Layout()

class Controller:
    def __init__(self, app):
        self.current_panel = None

        self.frame = MainFrame()
        self.show_panel(views.ChoosePasswordManagerPanel)
        self.frame.Show()

        pub.subscribe(self.password_manager_selected, "password_manager_selected")
        pub.subscribe(self.got_password_entries, "got_password_entries")
        pub.subscribe(self.log_file_selected, "log_file_selected")
        pub.subscribe(self.update_complete, "update_complete")
        pub.subscribe(self.finished, "finished")
        pub.subscribe(self.exit, "exit")


    def password_manager_selected(self, password_manager):
        if password_manager == 'onepassword':
            from managers.onepassword import OnePasswordImporter
            self.password_manager = OnePasswordImporter(self)
        self.password_manager.get_password_data()

    def got_password_entries(self, entries):
        rules = Rule.load_rules()
        matched_entries = []
        for entry in entries:
            for rule in rules:
                if rule.applies_to(entry):
                    matched_entries.append([rule, entry])
                    break

        if not matched_entries:
            show_error("We have no rules matching these logins. See [TK] for a list of currently supported sites.")
            return

        self.matched_entries = matched_entries
        self.show_panel(views.CreateLogPanel)

    def log_file_selected(self, log_file):
        self.show_panel(views.ChangePasswordsPanel, logins=self.matched_entries, log_file=log_file)

    def update_complete(self, changed_entries):
        if changed_entries:
            self.password_manager.save_changes(changed_entries)
        else:
            show_message("No logins were changed.")
            self.finished()

    def finished(self):
        self.show_panel(views.FinishedPanel)

    def exit(self):
        self.frame.Close()

    def show_panel(self, PanelClass, **kwargs):
        new_panel = PanelClass(self.frame, **kwargs)
        title = getattr(new_panel, 'title', '')
        self.frame.switch_to_panel(new_panel, title)



if __name__ == "__main__":
    app = wx.App(False)
    controller = Controller(app)
    app.MainLoop()