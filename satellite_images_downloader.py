# -*- coding: utf-8 -*-
"""
/***************************************************************************
 SatelliteImagesDownloader
                                 A QGIS plugin
 This plugin helps you search and download satellite images
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2018-03-27
        git sha              : $Format:%H$
        copyright            : (C) 2018 by Roman Vasilyev, USATU, Ufa
        email                : sektor_wins@mail.ru
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from PyQt5.QtCore import QSettings, QTranslator, qVersion, QCoreApplication
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QAction, QProgressBar, QApplication, QFileDialog
from qgis.gui import QgsMessageBar
# Initialize Qt resources from file resources.py
from .resources import *
# Import the code for the dialog
from .satellite_images_downloader_dialog import SatelliteImagesDownloaderDialog
import os
import satsearch
from satsearch.search import Search, Query
from satsearch.scene import Scenes
import os.path
import logging
from.globals import SATELLITES, KEYWORD_ARGS
from .workers import DownloadWorker


KWARGS = KEYWORD_ARGS
FILEKEYS = []

class SatelliteImagesDownloader:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'SatelliteImagesDownloader_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

        # Create the dialog (after translation) and keep reference
        self.dlg = SatelliteImagesDownloaderDialog()

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&Download Satellite Images')

        self.toolbar = self.iface.addToolBar(u'SatelliteImagesDownloader')
        self.toolbar.setObjectName(u'SatelliteImagesDownloader')
        self.add_satellites_combobox(SATELLITES)

        self.worker = None
        self.dlg.searchScenesButton.clicked.connect(self.finding_scenes)
        self.dlg.selectFolderButton.clicked.connect(self.showFolderDialog)
        self.dlg.downloadScenesButton.clicked.connect(self.downloading_scenes)
        self.dlg.stopDownloading.clicked.connect(self.stop_worker)
        

        self.dlg.finished.connect(self.stop_worker)

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('SatelliteImagesDownloader', message)


    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/satellite_images_downloader/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u''),
            callback=self.run,
            parent=self.iface.mainWindow())


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&Download Satellite Images'),
                action)
            self.iface.removeToolBarIcon(action)
        # remove the toolbar
        del self.toolbar


    def stop_worker(self):
        self.worker.stop()
        self.worker.quit()
        self.worker.wait()


    def showFolderDialog(self):
        folder_path = QFileDialog.getExistingDirectory(self.dlg, "Выберите папку","",QFileDialog.ShowDirsOnly)
        self.dlg.folderPath_lineEdit.setText(folder_path)


    def add_satellites_combobox(self, satellites_list):
        self.dlg.satelliteName_comboBox.addItems(satellites_list)


    def checking_landsat8_category(self):
 
        if self.dlg.categoryT1_checkBox.isChecked():
            
            if "COLLECTION_CATEGORY" in KWARGS:
                KWARGS["COLLECTION_CATEGORY"] += "T1,"
            else:
                KWARGS["COLLECTION_CATEGORY"] = "T1,"
        if self.dlg.categoryT2_checkBox.isChecked():

            if "COLLECTION_CATEGORY" in KWARGS:
                KWARGS["COLLECTION_CATEGORY"] += "T2,"
            else:
                KWARGS["COLLECTION_CATEGORY"] = "T2,"
        if self.dlg.categoryRT_checkBox.isChecked():

            if "COLLECTION_CATEGORY" in KWARGS:
                KWARGS["COLLECTION_CATEGORY"] += "RT,"
            else:
                KWARGS["COLLECTION_CATEGORY"] = "RT,"

    def check_landsat8_filekeys(self):

        if self.dlg.L8B1_checkBox.isChecked():
            FILEKEYS.append("B1")

        if self.dlg.L8B2_checkBox.isChecked():
            FILEKEYS.append("B2")

        if self.dlg.L8B3_checkBox.isChecked():
            FILEKEYS.append("B3")

        if self.dlg.L8B4_checkBox.isChecked():
            FILEKEYS.append("B4")
        
        if self.dlg.L8B5_checkBox.isChecked():
            FILEKEYS.append("B5")

        if self.dlg.L8B6_checkBox.isChecked():
            FILEKEYS.append("B6")

        if self.dlg.L8B7_checkBox.isChecked():
            FILEKEYS.append("B7")

        if self.dlg.L8B8_checkBox.isChecked():
            FILEKEYS.append("B8")

        if self.dlg.L8B9_checkBox.isChecked():
            FILEKEYS.append("B9")

        if self.dlg.L8B10_checkBox.isChecked():
            FILEKEYS.append("B10")

        if self.dlg.L8B11_checkBox.isChecked():
            FILEKEYS.append("B11") 

        if self.dlg.L8MTL_checkBox.isChecked():
            FILEKEYS.append("MTL")           


    def check_sentinel2_filekeys(self):

        if self.dlg.S2B1_checkBox.isChecked():
            FILEKEYS.append("01")

        if self.dlg.S2B2_checkBox.isChecked():
            FILEKEYS.append("02")

        if self.dlg.S2B3_checkBox.isChecked():
            FILEKEYS.append("03")

        if self.dlg.S2B4_checkBox.isChecked():
            FILEKEYS.append("04")
        
        if self.dlg.S2B5_checkBox.isChecked():
            FILEKEYS.append("05")

        if self.dlg.S2B6_checkBox.isChecked():
            FILEKEYS.append("06")

        if self.dlg.S2B7_checkBox.isChecked():
            FILEKEYS.append("07")

        if self.dlg.S2B8_checkBox.isChecked():
            FILEKEYS.append("08")

        if self.dlg.S2B8A_checkBox.isChecked():
            FILEKEYS.append("8A")

        if self.dlg.S2B9_checkBox.isChecked():
            FILEKEYS.append("09")

        if self.dlg.S2B10_checkBox.isChecked():
            FILEKEYS.append("10")

        if self.dlg.S2B11_checkBox.isChecked():
            FILEKEYS.append("11") 

        if self.dlg.S2B12_checkBox.isChecked():
            FILEKEYS.append("12")


    def clearing_landsat8_category(self):
        if "COLLECTION_CATEGORY" in KWARGS: del KWARGS["COLLECTION_CATEGORY"]

    
    def clear_filekeys(self):
        del FILEKEYS[:]


    def finding_scenes(self):
        SATTELITE_NAME = str(self.dlg.satelliteName_comboBox.currentText())
        CLOUD_FROM = str(self.dlg.cloudFrom_spinBox.value())
        CLOUD_TO = str(self.dlg.cloudTo_spinBox.value())
        DATE_FROM = str(self.dlg.dateEdit.date().toPyDate())
        DATE_TO = str(self.dlg.dateEdit_2.date().toPyDate())

        KWARGS["satellite_name"] = SATTELITE_NAME
        KWARGS["cloud_from"] = CLOUD_FROM
        KWARGS["cloud_to"] = CLOUD_TO
        KWARGS["date_from"] = DATE_FROM
        KWARGS["date_to"] = DATE_TO

        if SATTELITE_NAME == "Landsat-8 OLI/TIRS":
            self.checking_landsat8_category()

        self.iface.messageBar().pushInfo("Message", "Выполняется поиск")

        simple_query_result = Query(**KWARGS).found()
        self.dlg.logWindow.appendPlainText(str(simple_query_result)+" снимков найдено")

        self.clearing_landsat8_category()

        self.iface.messageBar().pushSuccess("Message", "Снимки найдены")


    def downloading_scenes(self):
        
        self.worker = DownloadWorker(self.dlg.logWindow)

        self.clearing_landsat8_category()
        self.clear_filekeys()

        if not os.path.exists(self.dlg.folderPath_lineEdit.text()):
            self.dlg.logWindow.appendPlainText("Введите корректный путь к директории!")
            return None

        SATTELITE_NAME = str(self.dlg.satelliteName_comboBox.currentText())
        CLOUD_FROM = str(self.dlg.cloudFrom_spinBox.value())
        CLOUD_TO = str(self.dlg.cloudTo_spinBox.value())
        DATE_FROM = str(self.dlg.dateEdit.date().toPyDate())
        DATE_TO = str(self.dlg.dateEdit_2.date().toPyDate())

        KWARGS["satellite_name"] = SATTELITE_NAME
        KWARGS["cloud_from"] = CLOUD_FROM
        KWARGS["cloud_to"] = CLOUD_TO
        KWARGS["date_from"] = DATE_FROM
        KWARGS["date_to"] = DATE_TO

        if SATTELITE_NAME == "Landsat-8 OLI/TIRS":
            self.checking_landsat8_category()
            self.check_landsat8_filekeys()
        elif SATTELITE_NAME == "Sentinel-2":
            self.check_sentinel2_filekeys()

        scenes_query_result = Query(**KWARGS).scenes()
        scenes = Scenes(scenes_query_result)
        
        PATH = str(self.dlg.folderPath_lineEdit.text()) + "/"
        self.dlg.logWindow.appendPlainText("Файлы будут загружены в директорию: " + PATH)
        self.dlg.logWindow.appendPlainText("К загрузке представлено сцен - " + str(len(scenes)))
        self.dlg.logWindow.appendPlainText("Каналы (файлы) к загрузке - " + ", ".join(FILEKEYS))

        self.dlg.stopDownloading.setEnabled(True)
        # for scene in scenes.scenes:
        #     QApplication.processEvents()
        #     for key in FILEKEYS:
        #         QApplication.processEvents()
        #         self.dlg.logWindow.appendPlainText("Загружается файл (канал) " + str(key) + " для сцены " + str(scene.product_id))
        #         QApplication.processEvents()
        #         scene.download(key=key, path=PATH)


        self.worker.scenes = scenes.scenes
        self.worker.filekeys = FILEKEYS
        self.worker.path = PATH
        self.worker.start()
        # self.dlg.logWindow.appendPlainText("Загрузка завершена!")

        # self.dlg.stopDownloading.setEnabled(False)
    def run(self):
        """Run method that performs all the real work"""
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()
        # See if OK was pressed
        if result:
            # Do something useful here - delete the line containing pass and
            # substitute with your code.
            pass