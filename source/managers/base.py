class BaseImporter(object):
    def __init__(self, controller):
        self.controller = controller

    def get_password_data(self):
        raise NotImplementedError

    def save_changes(self, changed_entries):
        raise NotImplementedError

    @classmethod
    def add_command_line_arguments(self, parser):
        """
            If you want to add command line options, you can do that here.
            They should have a unique prefix (e.g. "--onepassword-option").
        """
        # parser.add_option(...)
        pass

    @classmethod
    def get_file_handlers(self):
        """
            Override to register to handle certain file types.
        """
        return []
