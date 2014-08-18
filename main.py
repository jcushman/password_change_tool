from optparse import OptionParser
import sys
import wx
from wx.lib.pubsub import pub
from helpers import load_log_file, process_selenium_ide_file, show_error, data_path
from models import GlobalState

import views

# process password manager plugins
# TODO: make this auto-discover and move it somewhere sensible
from managers.onepassword import OnePasswordImporter
password_managers = {
    'onepassword':OnePasswordImporter
}

# get dictionary of file_handlers from password_managers
file_handlers = {}
for manager in password_managers.values():
    for file_handler in manager.get_file_handlers():
        file_handlers[file_handler.extension] = file_handler
        file_handler.manager_class = manager

class HeaderPanel(wx.Panel):
    def __init__(self, *args, **kwargs):
        super(HeaderPanel, self).__init__(*args, **kwargs)
        self.Bind(wx.EVT_PAINT, self.paint)

    def paint(self, evt):
        dc = wx.PaintDC(self)

        # background
        dc.SetBackground(wx.Brush("#e2e2e2"))
        dc.Clear()

        # shadow
        w, h = self.GetSize()
        dc.GradientFillLinear((0, h-10, w, h), '#4d7685', "#e2e2e2", wx.NORTH)

        # title
        dc.SetTextForeground('#4d7685')
        dc.SetFont(wx.Font(66, wx.FONTFAMILY_SWISS, wx.NORMAL, wx.LIGHT, False))
        dc.DrawText("FreshPass",
                    65, 8)

        # icon
        with open(data_path('assets/icon.iconset/icon_128x128.png')) as icon_file:
            image = wx.ImageFromStream(icon_file, wx.BITMAP_TYPE_PNG)
        image = image.Scale(64, 64, wx.IMAGE_QUALITY_HIGH)
        bitmap = wx.BitmapFromImage(image)
        if "gtk1" in wx.PlatformInfo:
            # via wxPython ImageAlpha demo -- fake alpha for wxGTK (gtk+ 1.2)
            img = bitmap.ConvertToImage()
            img.ConvertAlphaToMask(220)
            bitmap = img.ConvertToBitmap()
        dc.DrawBitmap(bitmap, 2, 5, True)

class MainFrame(wx.Frame):
    current_panel = None
    current_panel_item = None

    def __init__(self, controller):
        super(MainFrame, self).__init__(None, title="Password Updater", size=(700,600))
        self.controller = controller

        # set up contents
        self.SetBackgroundColour(wx.WHITE)
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self.sizer)

        # set up header
        top_panel = HeaderPanel(self, size=(300, 70))
        # top_panel_sizer = wx.BoxSizer(wx.HORIZONTAL)
        # top_panel.SetSizer(top_panel_sizer)
        self.sizer.Add(top_panel, 0, wx.EXPAND)
        self.sizer.Add((30,30))

        # set up menu
        MenuBar = wx.MenuBar()

        FileMenu = wx.Menu()
        item = FileMenu.Append(wx.ID_EXIT, text="&Exit")
        self.Bind(wx.EVT_MENU, self.exit, item)
        item = FileMenu.Append(wx.ID_ANY, text="&Open")
        self.Bind(wx.EVT_MENU, self.open, item)
        item = FileMenu.Append(wx.ID_PREFERENCES, text="&Preferences")
        self.Bind(wx.EVT_MENU, self.exit, item)
        MenuBar.Append(FileMenu, "&File")

        HelpMenu = wx.Menu()
        item = HelpMenu.Append(wx.ID_HELP, "Test &Help", "Help for this simple test")
        self.Bind(wx.EVT_MENU, self.exit, item)
        item = HelpMenu.Append(wx.ID_ABOUT, "&About", "More information About this program")
        self.Bind(wx.EVT_MENU, self.exit, item)
        MenuBar.Append(HelpMenu, "&Help")

        self.SetMenuBar(MenuBar)

    def switch_to_panel(self, panel, title):
        if self.current_panel:
            self.current_panel.Hide()

        self.SetTitle(title)
        self.sizer.Add(panel, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 70)
        self.current_panel = panel
        self.Layout()

    def exit(self, evt):
        pub.sendMessage("exit")

    def open(self, evt):
        pub.sendMessage("open_file")

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

    def open_file(self, filename=None):
        print "opening", filename
        if not filename:
            wildcard = "|".join(file_handler.wildcard for file_handler in file_handlers.values())
            dlg = wx.FileDialog(
                self.controller.frame, message="Choose a file",
                # defaultDir=os.getcwd(),
                defaultFile="",
                wildcard=wildcard,
                style=wx.OPEN | wx.CHANGE_DIR
            )

            if dlg.ShowModal() == wx.ID_OK:
                filename = dlg.GetPath()

        if filename:
            extension = filename.rsplit('.', 1)[1]
            file_handler = file_handlers.get(extension, None)
            if not file_handler:
                show_error("Unrecognized file type: .%s" % extension)
            GlobalState.password_manager = file_handler.manager_class(self.controller)
            file_handler.handler(filename)

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


class App(wx.App):
    def __init__(self, *args, **kwargs):
        wx.App.__init__(self, *args, **kwargs)

        # This catches events when the app is asked to activate by some other process
        self.Bind(wx.EVT_ACTIVATE_APP, self.OnActivate)

    def OnInit(self):
        self.routes = Routes(self)
        self.frame = MainFrame(self)
        self.frame.Show()
        GlobalState.controller = self

        if GlobalState.args:
            pub.sendMessage('open_file', filename=GlobalState.args[0])
        else:
            pub.sendMessage('start')

        return True

    def show_panel(self, PanelClass, **kwargs):
        new_panel = PanelClass(self.frame, **kwargs)
        title = getattr(new_panel, 'title', '')
        self.frame.switch_to_panel(new_panel, title)

    def BringWindowToFront(self):
        try:
            self.GetTopWindow().Raise()
        except:
            pass

    def OnActivate(self, event):
        if event.GetActive():
            self.BringWindowToFront()
        event.Skip()

    def MacOpenFiles(self, filenames):
        pub.sendMessage("open_file", filename=filenames[0])

    def MacReopenApp(self):
        self.BringWindowToFront()


if __name__ == "__main__":

    # handle command line arguments
    # (mostly useful for debugging)
    parser = OptionParser(usage="usage: %prog [options] [password_file]")
    parser.add_option("-m", "--manager",
                      dest="manager",
                      default=None,
                      help="Password manager to use (options: onepassword)")
    parser.add_option("-d", "--debug",
                      action="store_true",
                      dest="debug",
                      default=False,
                      help="Enable debugging (enters pdb on web browser exception)")
    parser.add_option("--convert-selenium",
                      dest="selenium_file",
                      default=None,
                      help="Convert a Selenium IDE file (html) into a FreshPass script")
    parser.add_option("-t", "--timeout",
                      type="int",
                      dest="timeout",
                      default=None,
                      help="Timeout when looking for elements on page (in seconds)")
    for manager in password_managers.values():
        manager.add_command_line_arguments(parser)
    (options, args) = parser.parse_args()
    GlobalState.options = options
    GlobalState.args = args

    if options.selenium_file:
        process_selenium_ide_file(options.selenium_file)
        sys.exit()

    app = App(False)

    # handy for debugging layout
    # import wx.lib.inspection
    # wx.lib.inspection.InspectionTool().Show()

    app.MainLoop()