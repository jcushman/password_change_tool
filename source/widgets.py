import sys
import wx
from wx.lib.mixins.listctrl import ListCtrlAutoWidthMixin, CheckListCtrlMixin


class ListCtrl(wx.ListCtrl, ListCtrlAutoWidthMixin):
    def __init__(self, *args, **kwargs):
        wx.ListCtrl.__init__(self, *args, **kwargs)
        ListCtrlAutoWidthMixin.__init__(self)


class CheckListCtrl(ListCtrl, CheckListCtrlMixin):
    selected_indexes = set()

    def __init__(self, *args, **kwargs):
        ListCtrl.__init__(self, *args, **kwargs)
        CheckListCtrlMixin.__init__(self)
        self.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.OnItemActivated)

    def OnItemActivated(self, evt):
        self.ToggleItem(evt.m_itemIndex)

    def OnCheckItem(self, index, flag):
        if flag:
            self.selected_indexes.add(index)
        else:
            self.selected_indexes.remove(index)


class SizerPanel(wx.Panel):
    def __init__(self, parent):
        super(SizerPanel, self).__init__(parent=parent)
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.add_controls()
        self.sizer.Add((30, 30))
        self.SetSizer(self.sizer)

    def add_controls(self):
        raise NotImplementedError

    def add_text(self, text, flags=wx.TOP, border=0):
        from models import GlobalState

        text = "\n".join(
            line.strip() for line in text.strip().split("\n"))  # remove whitespace at start of each line
        text_widget = wx.StaticText(self, label=text)
        self.sizer.Add(text_widget, 0, flags, border)

        # This is an ugly hack to wrap the text to the width of the frame,
        # before the panel is actually added to the frame.
        # It would be nice if this was handled by some sort of layout event instead.
        text_widget.Wrap(GlobalState.controller.frame.GetSize()[0] - 160 - border)

    def add_button(self, label, handler, flags=wx.TOP, border=30):
        button = wx.Button(self, label=label)
        self.Bind(wx.EVT_BUTTON, handler, button)
        self.sizer.Add(button, 0, flags, border)
        return button

    def add_list(self, headers, rows, ListClass=ListCtrl,
                 style=wx.LC_REPORT | wx.BORDER_SUNKEN):
        list_ctl = ListClass(self, -1, style=style)
        self.sizer.Add(list_ctl, 1, wx.EXPAND)

        for i, title in enumerate(headers):
            list_ctl.InsertColumn(i, title)

        for row in rows:
            index = list_ctl.InsertStringItem(sys.maxint, row[0])
            if len(headers)>1:
                for i, value in enumerate(row[1:]):
                    list_ctl.SetStringItem(index, i + 1, value)

        for i in range(len(headers)):
            list_ctl.SetColumnWidth(i, wx.LIST_AUTOSIZE)

        return list_ctl