from optparse import OptionParser
import wx
from wx.lib.pubsub import pub
from helpers import load_log_file
from models import GlobalState

import views

from managers.onepassword import OnePasswordImporter
password_managers = {
    'onepassword':OnePasswordImporter
}


class MainFrame(wx.Frame):
    current_panel = None
    current_panel_item = None

    def __init__(self):
        super(MainFrame, self).__init__(None, title="Password Updater", size=(700,600))

        self.SetBackgroundColour(wx.WHITE)

        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self.sizer)

    def switch_to_panel(self, panel, title):
        if self.current_panel:
            self.current_panel.Hide()

        self.SetTitle(title)
        self.sizer.Add(panel, 1, wx.EXPAND | wx.ALL, 30)
        self.current_panel = panel
        self.Layout()

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

    def start(self):
        if GlobalState.options.manager:
            pub.sendMessage('password_manager_selected', password_manager=GlobalState.options.manager)
        else:
            self.controller.show_panel(views.ChoosePasswordManagerPanel)

    def password_manager_selected(self, password_manager):
        GlobalState.password_manager = password_managers[password_manager](self.controller)
        GlobalState.password_manager.get_password_data()

    def got_password_entries(self):
        # see if we already have a default log file provided by the password manager module
        if GlobalState.default_log_file_path:
            log_file = load_log_file(GlobalState.default_log_file_path)
            if log_file:
                GlobalState.log_file = log_file
                GlobalState.log_file_path = GlobalState.default_log_file_path
        if not GlobalState.log_file:
            # if no default, ask user to pick
            self.controller.show_panel(views.CreateLogPanel)
        else:
            # all set, move on to picking passwords
            self.controller.show_panel(views.ChoosePasswordsPanel)

    def log_file_selected(self):

        self.controller.show_panel(views.ChoosePasswordsPanel)

    def passwords_selected(self):
        self.controller.show_panel(views.ChangePasswordsPanel)

    def update_complete(self):
        self.controller.show_panel(views.ResultsPanel)

    def export_changes(self):
        GlobalState.password_manager.save_changes(login for login in GlobalState.selected_logins if login.get('new_password', None))

    def finished(self):
        self.controller.show_panel(views.FinishedPanel)

    def exit(self):
        self.controller.frame.Close()


class Controller(object):
    def __init__(self, app):
        self.current_panel = None

        self.routes = Routes(self)

        self.frame = MainFrame()
        self.frame.Show()

        GlobalState.controller = self

        pub.sendMessage('start')

    def show_panel(self, PanelClass, **kwargs):
        new_panel = PanelClass(self.frame, **kwargs)
        title = getattr(new_panel, 'title', '')
        self.frame.switch_to_panel(new_panel, title)



if __name__ == "__main__":

    # handle command line arguments
    # (mostly useful for debugging)
    parser = OptionParser(usage="usage: %prog [options]")
    parser.add_option("-m", "--manager",
                      dest="manager",
                      default=None,
                      help="Password manager to use (options: onepassword)")
    parser.add_option("-d", "--debug",
                      action="store_true",
                      dest="debug",
                      default=False,
                      help="Enable debugging (enters pdb on web browser exception)")
    parser.add_option("-t", "--timeout",
                      type="int",
                      dest="timeout",
                      default=False,
                      help="Timeout when looking for elements on page (in seconds)")
    for manager in password_managers.values():
        manager.add_command_line_arguments(parser)
    (options, args) = parser.parse_args()
    GlobalState.options = options

    app = wx.App(False)
    controller = Controller(app)

    # import wx.lib.inspection
    # wx.lib.inspection.InspectionTool().Show()

    app.MainLoop()