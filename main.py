import wx
from wx.lib.pubsub import pub
from helpers import show_message, load_log_file
from models import GlobalState

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

class Routes(object):
    """
        Once this class is initialized,
        each method can be invoked from anywhere by calling
        pub.sendMessage("method_name", *args, **kwargs)
    """
    def __init__(self, controller):
        self.controller = controller
        route_names = [attr for attr in dir(Routes) if not attr.startswith('_')]
        for route_name in route_names:
            pub.subscribe(getattr(self, route_name), route_name)

    def password_manager_selected(self, password_manager):
        if password_manager == 'onepassword':
            from managers.onepassword import OnePasswordImporter
            self.password_manager = OnePasswordImporter(self.controller)
        self.password_manager.get_password_data()

    def got_password_entries(self):
        # see if we already have a default log file provided by the password manager module
        if GlobalState.default_log_file_path:
            log_file = load_log_file(GlobalState.default_log_file_path)
            if log_file:
                GlobalState.log_file = log_file
                GlobalState.log_file_path = GlobalState.default_log_file_path
        if not GlobalState.log_file:
            # if no default, ask user to pick
            controller.show_panel(views.CreateLogPanel)
        else:
            # all set, move on to picking passwords
            controller.show_panel(views.ChoosePasswordsPanel)

    def log_file_selected(self):
        controller.show_panel(views.ChoosePasswordsPanel)

    def passwords_selected(self):
        controller.show_panel(views.ChangePasswordsPanel)

    def update_complete(self, changed_entries):
        if changed_entries:
            self.password_manager.save_changes(changed_entries)
        else:
            show_message("No logins were changed.")
            self.finished()

    def finished(self):
        controller.show_panel(views.FinishedPanel)

    def exit(self):
        controller.frame.Close()


class Controller(object):
    def __init__(self, app):
        self.current_panel = None

        self.routes = Routes(self)

        self.frame = MainFrame()
        self.show_panel(views.ChoosePasswordManagerPanel)
        self.frame.Show()

    def show_panel(self, PanelClass, **kwargs):
        new_panel = PanelClass(self.frame, **kwargs)
        title = getattr(new_panel, 'title', '')
        self.frame.switch_to_panel(new_panel, title)



if __name__ == "__main__":
    app = wx.App(False)
    controller = Controller(app)
    app.MainLoop()