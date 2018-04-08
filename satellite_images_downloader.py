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
from PyQt5.QtWidgets import QAction, QProgressBar
from qgis.gui import QgsMessageBar
# Initialize Qt resources from file resources.py
from .resources import *
# Import the code for the dialog
from .satellite_images_downloader_dialog import SatelliteImagesDownloaderDialog
import os
import satsearch
from satsearch.search import Search, Query
from satsearch.scene import Scenes
from satsearch.main import main
import os.path
from.globals import SATELLITES, KEYWORD_ARGS

KWARGS = KEYWORD_ARGS

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
        # TODO: We are going to let the user set this up in a future iteration
        self.toolbar = self.iface.addToolBar(u'SatelliteImagesDownloader')
        self.toolbar.setObjectName(u'SatelliteImagesDownloader')
        self.add_satellites_combobox(SATELLITES)
        self.dlg.searchScenesButton.clicked.connect(self.finding_scenes)
        

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

    def add_satellites_combobox(self, satellites_list):
        self.dlg.satelliteName_comboBox.addItems(satellites_list)

    def checking_landsat8_category(self):
        self.dlg.checkParams.appendPlainText("RT IS stated - " + str(self.dlg.categoryRT_checkBox.checkState()))
        self.dlg.checkParams.appendPlainText("T2 IS stated - " + str(self.dlg.categoryT2_checkBox.checkState()))
        self.dlg.checkParams.appendPlainText("T1 IS stated - " + str(self.dlg.categoryT1_checkBox.checkState()))
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

    def clearing_landsat8_category(self):
        if "COLLECTION_CATEGORY" in KWARGS: del KWARGS["COLLECTION_CATEGORY"]

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
            self.dlg.checkParams.appendPlainText("YES ITS LANDSAT-8")
            self.checking_landsat8_category()

        self.iface.messageBar().pushInfo("Message", "Выполняется поиск")
        self.dlg.checkParams.appendPlainText(str(KWARGS))
        simple_query_result = Query(**KWARGS).found()
        self.dlg.finalScenes_lineEdit.setText(str(simple_query_result))
        self.clearing_landsat8_category()

        self.iface.messageBar().pushSuccess("Message", "Снимки найдены")


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