import time
import os.path

from PyQt5.QtCore import QSettings, QCoreApplication
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QAction, QApplication

from .resources import *
from .controllers.collection_loading_dialog import CollectionLoadingDialog
from .controllers.query_dialog import QueryDialog
from .controllers.item_loading_dialog import ItemLoadingDialog
from .controllers.results_dialog import ResultsDialog
from .controllers.downloading_controller import DownloadController
from .controllers.download_selection_dialog import DownloadSelectionDialog
from .utils.config import Config
from .utils.logging import debug, info, warning, error


class STACBrowser:
    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)

        self.actions = []
        self.application = None
        self.menu = u'&STAC Browser'

        self.current_window = 'COLLECTION_LOADING'
        
        self.windows = {
                    'COLLECTION_LOADING': {
                        'class': CollectionLoadingDialog,
                        'hooks': { 
                                     'on_finished': self.collection_load_finished, 
                                     'on_close': self.on_close
                                 },
                        'data': None,
                        'dialog': None
                    },
                    'QUERY': {
                        'class': QueryDialog,
                        'hooks': {
                                     'on_close': self.on_close, 
                                     'on_search': self.on_search
                                 },
                        'data': None,
                        'dialog': None
                    },
                    'ITEM_LOADING': {
                        'class': ItemLoadingDialog,
                        'hooks': {
                                     'on_close': self.on_close, 
                                     'on_finished': self.item_load_finished, 
                                     'on_error': self.results_error
                                 },
                        'data': None,
                        'dialog': None
                    },
                    'RESULTS': {
                        'class': ResultsDialog,
                        'hooks': {
                                     'on_close': self.on_close, 
                                     'on_back': self.on_back, 
                                     'on_download': self.on_download, 
                                     'select_downloads': self.select_downloads
                                 },
                        'data': None,
                        'dialog': None
                    },
                }

    def on_search(self, api_collections, extent_layer, time_period):
        (start_time, end_time) = time_period

        extent_rect = extent_layer.extent()
        extent = [ 
                     extent_rect.xMinimum(), 
                     extent_rect.yMinimum(), 
                     extent_rect.xMaximum(), 
                     extent_rect.yMaximum()
                 ]

        self.windows['ITEM_LOADING']['data'] = {
                    'api_collections': api_collections,
                    'extent': extent,
                    'start_time': start_time,
                    'end_time': end_time
                }
        self.current_window = 'ITEM_LOADING'
        self.windows['QUERY']['dialog'].close()
        self.load_window()

    def on_back(self):
        self.windows['RESULTS']['data'] = None
        self.windows['RESULTS']['dialog'].close()
        self.windows['RESULTS']['dialog'] = None

        self.current_window = 'QUERY'
        self.load_window()

    def on_close(self):
        if self.windows is None:
            return
        self.reset_windows() 

    def on_download(self, download_items, download_directory):
        self._download_controller = DownloadController(
                                                       data = { 
                                                                  'downloads': download_items, 
                                                                  'download_directory': download_directory, 
                                                              },
                                                       hooks = {}, iface=self.iface)
        self.reset_windows()

    def downloading_finished(self):
        self.windows['DOWNLOADING']['dialog'].close()
        self.current_window = 'COLLECTION_LOADING'
        self.reset_windows()

    def collection_load_finished(self, apis):
        self.windows['QUERY']['data'] = { 'apis': apis }
        self.current_window = 'QUERY'
        self.windows['COLLECTION_LOADING']['dialog'].close()
        self.load_window()

    def results_error(self):
        self.windows['ITEM_LOADING']['dialog'].close()
        self.windows['ITEM_LOADING']['dialog'] = None
        self.windows['ITEM_LOADING']['data'] = None
        self.current_window = 'QUERY'
        self.load_window()

    def item_load_finished(self, items):
        self.windows['RESULTS']['data'] = { 'items': items }
        self.current_window = 'RESULTS'
        self.windows['ITEM_LOADING']['dialog'].close()
        self.windows['ITEM_LOADING']['data'] = None
        self.windows['ITEM_LOADING']['dialog'] = None
        self.load_window()

    def select_downloads(self, items, download_directory):
        dialog = DownloadSelectionDialog(data={'items': items},
                                         hooks={'on_close': self.on_close},
                                         parent=self.windows['RESULTS']['dialog'])

        result = dialog.exec_()

        if not result:
            return

        self.on_download(dialog.downloads, download_directory)

    def add_action(self, icon_path, text, callback, enabled_flag=True,
                   add_to_menu=True, add_to_toolbar=True, status_tip=None,
                   whats_this=None, parent=None):
        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToWebMenu(self.menu, action)

        self.actions.append(action)

        return action

    def load_window(self):
        if self.current_window == 'COLLECTION_LOADING':
            config = Config()
            if config.last_update is not None and time.time() - config.last_update < config.api_update_interval:
                self.current_window = 'QUERY'
                self.windows['QUERY']['data'] = { 'apis': config.apis }

        window = self.windows.get(self.current_window, None)

        if window is None:
            logging.error(f'Window {self.current_window} does not exist')
            return

        if window['dialog'] is None:
            window['dialog'] = window.get('class')(data=window.get('data'), 
                                                   hooks=window.get('hooks'), 
                                                   parent=self.iface.mainWindow(),
                                                   iface=self.iface)
            window['dialog'].show()
        else:
            window['dialog'].raise_()
            window['dialog'].show()
            window['dialog'].activateWindow()
    
    def reset_windows(self):
        for key, window in self.windows.items():
            if window['dialog'] is not None:
                window['dialog'].close()
            window['data'] = None
            window['dialog'] = None
        self.current_window = 'COLLECTION_LOADING'

    def initGui(self):
        icon_path = ':/plugins/stac_browser/assets/icon.png'
        self.add_action(
            icon_path,
            text='Browse STAC Catalogs',
            callback=self.load_window,
            parent=self.iface.mainWindow())

    def unload(self):
        for action in self.actions:
            self.iface.removePluginWebMenu(u'&STAC Browser', action)
            self.iface.removeToolBarIcon(action)
