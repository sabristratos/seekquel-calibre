from calibre.customize import InterfaceActionBase

__version__ = '1.2.0'


class SeekquelSyncPlugin(InterfaceActionBase):
    name = 'Seekquel Sync'
    description = 'Sync shelves, ratings, reviews and reading dates with Seekquel, both ways.'
    author = 'Seekquel'
    version = (1, 2, 0)
    minimum_calibre_version = (6, 0, 0)
    supported_platforms = ['windows', 'osx', 'linux']

    actual_plugin = 'calibre_plugins.seekquel_sync.action:SeekquelSyncAction'

    def is_customizable(self):
        return True

    def config_widget(self):
        from calibre_plugins.seekquel_sync.config import ConfigWidget

        return ConfigWidget()

    def save_settings(self, config_widget):
        config_widget.save_settings()
