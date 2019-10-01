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
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QSettings, QTranslator, qVersion, QCoreApplication
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QAction, QProgressBar, QApplication, QFileDialog
from qgis.gui import QgsMessageBar
from qgis.core import QgsProject, QgsRasterLayer
# Initialize Qt resources from file resources.py
from .resources import *
# Import the code for the dialog
from .satellite_images_downloader_dialog import SatelliteImagesDownloaderDialog
import os
import json

import datetime
from time import gmtime, strftime

from satsearch import Search

import requests
import logging
from .globals import SATELLITES, KEYWORD_ARGS, AOI_COORDINATES
from .workers import DownloadWorker, FindWorker
from .helpers import CaptureCoordinates

KWARGS = KEYWORD_ARGS
FILEKEYS = []
# SHOWTIME = strftime("%H:%M:%S", gmtime())

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
        self.dlg.setWindowTitle("Поиск и загрузка космоснимков")

        # устанавливаем иконку плагина
        main_icon = QtGui.QIcon()
        main_icon.addPixmap(QtGui.QPixmap(":/plugins/satellite_images_downloader/ui/icons/search_tab_logo.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.dlg.setWindowIcon(main_icon)

        # устанавливаем иконку для вкладки с поисковыми параметрами
        # search_tab_icon = QtGui.QIcon()
        # search_tab_icon.addPixmap(QtGui.QPixmap(":/plugins/satellite_images_downloader/ui/icons/search_tab_logo.png"),QtGui.QIcon.Normal, QtGui.QIcon.Off)
        # self.dlg.seacrhFilters_Tab.setWindowIcon(search_tab_icon)
        # self.dlg.downloadOptions_Tab.setWindowIcon(search_tab_icon)


        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&Download Satellite Images')

        self.toolbar = self.iface.addToolBar(u'SatelliteImagesDownloader')
        self.toolbar.setObjectName(u'SatelliteImagesDownloader')
        self.add_satellites_combobox(SATELLITES)



        self.capturer = CaptureCoordinates(self.iface.mapCanvas(), 
                                self.dlg.logWindow, 
                                destination_crs="EPSG:4326")


        self.dlg.searchScenesButton.clicked.connect(self.finding_scenes)
        self.dlg.selectFolderButton.clicked.connect(self.showFolderDialog)
        self.dlg.downloadScenesButton.clicked.connect(self.downloading_scenes)
        self.dlg.stopDownloadingButton.clicked.connect(self.stop_worker)
        self.dlg.interruptingButton.clicked.connect(self.interrupt_worker)
        self.dlg.GoogleStreetsButton.clicked.connect(self.displayGoogleStreets)
        self.dlg.GoogleHybridButton.clicked.connect(self.displayGoogleHybrid)
        self.dlg.AOIButton.clicked.connect(self.captureAOI)
        self.dlg.setupCoordinatesButton.clicked.connect(self.setup_coordinates)
        self.dlg.cancelCoordinatesButton.clicked.connect(self.clear_coordinates)

        # self.dlg.finished.connect(self.stop_worker)

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
        status_tip="Plugin for searching and downloading satellite images",
        whats_this="Search and Download Satellite Images",
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
            action.setText(whats_this)

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


    def start_worker(self):
        pass


    def stop_worker(self):
        """
        Вспомогательная функция для остановки работы воркера-загрузчика
        """
        self.worker.stop()
        self.worker.quit()
        self.worker.wait()
        self.worker.terminate()
        del self.worker
        self.dlg.stopDownloadingButton.setEnabled(False)
        self.dlg.interruptingButton.setEnabled(False)
        self.dlg.downloadScenesButton.setEnabled(True)


    def stop_finder(self):
        """
        Вспомогательная функция для остановки работы воркера-поисковика
        """
        self.finder.stop()
        self.finder.quit()
        self.finder.wait()
        self.finder.terminate()
        del self.finder


    def interrupt_worker(self):

        self.worker.stop()
        self.worker.terminate()
        del self.worker
        self.dlg.logWindow.appendPlainText("["+str(datetime.datetime.now().strftime ("%H:%M:%S")) + "]" + " Загрузка была прервана!")
        self.dlg.stopDownloadingButton.setEnabled(False)
        self.dlg.interruptingButton.setEnabled(False)
        self.dlg.downloadScenesButton.setEnabled(True)


    """ Ряд методов-коллбэков на эвенты от воркеров """
    def work_is_starting(self, data):
        """ Общий коллбэк на эвент начала работы воркеров """
        self.dlg.logWindow.appendPlainText(data)


    def download_ready(self, data):
        """ Коллбэк на эвент загрузки 1 файла """
        self.dlg.logWindow.appendPlainText(data)


    def files_are_found(self, files_count, searching_collection_name):
        """
        Коллбэк на эвент завершения запроса на определение количества снимков при заданных параметрах
        """
        if searching_collection_name == 'landsat-8-l1':
            info_str = f"{str(files_count)} снимков Landsat-8 найдено"
        else:
            info_str = f"{str(files_count)} снимков Sentinel-2 найдено"
        self.dlg.logWindow.appendPlainText(f"[{str(datetime.datetime.now().strftime ('%H:%M:%S'))}] {info_str}")


    def work_ready(self, data):
        """ 
        Коллбэк на эвент завершений всего процесса загрузки снимков
        """
        self.dlg.logWindow.appendPlainText(data)
        self.dlg.stopDownloadingButton.setEnabled(False)
        self.dlg.interruptingButton.setEnabled(False)
        self.dlg.downloadScenesButton.setEnabled(True)


    def showFolderDialog(self):
        """
        Отображает диалоговое окно для выбора директории сохранения снимков 
        и сохраняет выбор в текстовое поле.
        """
        folder_path = QFileDialog.getExistingDirectory(self.dlg, "Выберите папку","",QFileDialog.ShowDirsOnly)
        self.dlg.folderPath_lineEdit.setText(folder_path)


    def add_satellites_combobox(self, satellites_list):
        """
        Добавляет в комбобокс список доступных спутников 
        из конфига globals.SATELLITES.
        """
        self.dlg.satelliteName_comboBox.addItems(satellites_list)


    def add_basemap(self, service_url, name):
        import qgis.utils	
        service_uri = "type=xyz&zmin=0&zmax=22&url=http://"+requests.utils.quote(service_url)
        tms_layer = qgis.utils.iface.addRasterLayer(service_uri, name, "wms")


    def displayGoogleHybrid(self):
        """
        Скачивает подложку Google Hybrid, добавляет ее в проект 
        и отображает в списке слоев.
        """
        service_url ="mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}"
        name = "Google Hybrid"
        self.add_basemap(service_url, name)

    
    def displayGoogleStreets(self):
        """
        Скачивает подложку Google Streets, добавляет ее в проект 
        и отображает в списке слоев.
        """
        service_url ="mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}"
        name = "Google Streets"
        self.add_basemap(service_url, name)


    def captureAOI(self):
        """
        Фиксирует координаты интересуемой области.
        """
        if AOI_COORDINATES:
            self.dlg.logWindow.appendPlainText("["+str(datetime.datetime.now().strftime ("%H:%M:%S")) + "] " + "Координаты были сброшены")
        self.capturer.cancelCoordinates()
        try:
            self.capturer.layer = self.iface.activeLayer()
            self.capturer.source_crs = self.capturer.layer.crs().authid()
            self.iface.mapCanvas().setMapTool(self.capturer)
        except:
            self.dlg.logWindow.appendPlainText("["+str(datetime.datetime.now().strftime ("%H:%M:%S")) + "] " + "Необходимо выбрать базовый слой для выделения области интереса!")


    def setup_coordinates(self):
        """
        Устанавливает координаты известной области.
        """
        self.capturer.layer = self.iface.activeLayer()
        if self.capturer.layer == None:
            self.dlg.logWindow.appendPlainText("["+str(datetime.datetime.now().strftime ("%H:%M:%S")) + "] " + "Необходимо выбрать базовый слой для выделения области интереса!")
        else:
            self.capturer.source_crs = self.capturer.layer.crs().authid()
            try:
                x_wgs84 = float(self.dlg.x_wgs84_lineEdit.text())
                y_wgs84 = float(self.dlg.y_wgs84_lineEdit.text())
                if -180<=x_wgs84<=180 and -90<=y_wgs84<=90:
                    self.capturer.addCoordinates(x_wgs84, y_wgs84)
                else:
                    self.dlg.logWindow.appendPlainText("["+str(datetime.datetime.now().strftime ("%H:%M:%S")) + "] " + "Проверьте правильность ввода координаты! Точка не была установлена.")
            except:
                self.dlg.logWindow.appendPlainText("["+str(datetime.datetime.now().strftime ("%H:%M:%S")) + "] " + "Проверьте правильность ввода координаты! Точка не была установлена.")


    def clear_coordinates(self):
        if AOI_COORDINATES:
            self.dlg.logWindow.appendPlainText("["+str(datetime.datetime.now().strftime ("%H:%M:%S")) + "] " + "Координаты были сброшены")
        self.capturer.cancelCoordinates()


    def checking_landsat8_category(self):
        """
        Проверяет какие категории снимков Landsat-8 были выбраны.
        """
        tiers = []
        if self.dlg.categoryT1_checkBox.isChecked():
            tiers.append("T1")
        if self.dlg.categoryT2_checkBox.isChecked():
            tiers.append("T2")
        if self.dlg.categoryRT_checkBox.isChecked():
            tiers.append("RT")
        return tiers


    def check_landsat8_filekeys(self):
        """
        Проверяет какие каналы (файлы) к загрузке были выбраны для Landsat-8.
        """
        if self.dlg.L8MTL_checkBox.isChecked():
            FILEKEYS.append("MTL")

        for i in range(1,12):
            t = "self.dlg.L8B" + str(i) + "_checkBox.isChecked()"
            cast_t = eval(t)
            if cast_t:
                FILEKEYS.append("B"+str(i))


    def check_sentinel2_filekeys(self):
        """
        Проверяет какие каналы (файлы) к загрузке были выбраны для Sentinel-2.
        """
        if self.dlg.S2B8A_checkBox.isChecked():
            FILEKEYS.append("B8A")

        for i in range(1,12):
            t = "self.dlg.S2B" + str(i) + "_checkBox.isChecked()"
            cast_t = eval(t)
            if cast_t:
                if i<10:
                    FILEKEYS.append("B0"+str(i))
                else:
                    FILEKEYS.append("B1"+str(i))


    def clearing_landsat8_category(self):
        """
        Вспомогательная функция для очистки параметра категории снимков L8.
        """
        if "COLLECTION_CATEGORY" in KWARGS: del KWARGS["COLLECTION_CATEGORY"]

    
    def clear_filekeys(self):
        """
        Вспомогательная функция для очистки списка ключей для загрузки каналов.
        """
        del FILEKEYS[:]


    def finding_scenes(self):
        """
        Делает запрос по API на количество снимков согласно выбранным параметрам.
        """
        SATTELITE_NAME = str(self.dlg.satelliteName_comboBox.currentText())

        searching_collection_name = None

        if SATTELITE_NAME == "Landsat-8":
            searching_collection_name = "landsat-8-l1"
        elif SATTELITE_NAME == "Sentinel-2":
            searching_collection_name = "sentinel-2-l1c"

        CLOUD_FROM = str(self.dlg.cloudFrom_spinBox.value())
        CLOUD_TO = str(self.dlg.cloudTo_spinBox.value())
        DATE_FROM = str(self.dlg.dateEdit.date().toPyDate())
        DATE_TO = str(self.dlg.dateEdit_2.date().toPyDate())

        intersects_geojson_data = self.buildGeoJSON()
        date_param_string = f"{DATE_FROM}/{DATE_TO}"

        query = {
            'eo:cloud_cover': {
                'lte' : CLOUD_TO,
                'gte' : CLOUD_FROM
            }
        }

        if searching_collection_name:
            query['collection'] = {'eq' : searching_collection_name}

        # is really shit-shit code,
        # но ребятишки, сделавшие API, видимо не подумали о том, 
        # что может потребоваться передавать параметры через OR (||)
        landsat_queries =[]
        if searching_collection_name == "landsat-8-l1":
            landsat_tiers = self.checking_landsat8_category()
            for tier in landsat_tiers:
                query['landsat:tier'] = {"eq" : tier}
                landsat_queries.append(query.copy())
            
        # инициализируем воркера-поисковика
        # снабжаем его всеми необходимыми параметрами
        if searching_collection_name == "landsat-8-l1" and len(landsat_queries) >= 2:
            self.finder = FindWorker(intersects=intersects_geojson_data, time=date_param_string, query=landsat_queries)
        else:
            self.finder = FindWorker(intersects=intersects_geojson_data, time=date_param_string, query=query)

        # вешаем коллбэки на его эвенты
        self.finder.search_is_started.connect(self.work_is_starting)
        self.finder.files_are_found.connect(self.files_are_found)

        # запускаем поисковик и ждем результат
        try:
            self.finder.start()
        except Exception as e:
            self.dlg.logWindow.appendPlainText(str(e))
            self.stop_finder()




    def downloading_scenes(self):
        """
        Делает запрос по API на загрузку снимков на основе выбранных параметров.
        """
        self.clearing_landsat8_category()
        self.clear_filekeys()

        if not os.path.exists(self.dlg.folderPath_lineEdit.text()):
            self.dlg.logWindow.appendPlainText("["+str(datetime.datetime.now().strftime ("%H:%M:%S")) + "]" +" Введите корректный путь к директории!")
            return None

        SATTELITE_NAME = str(self.dlg.satelliteName_comboBox.currentText())

        searching_collection_name = None

        if SATTELITE_NAME == "Landsat-8":
            searching_collection_name = "landsat-8-l1"
        elif SATTELITE_NAME == "Sentinel-2":
            searching_collection_name = "sentinel-2-l1c"

        CLOUD_FROM = str(self.dlg.cloudFrom_spinBox.value())
        CLOUD_TO = str(self.dlg.cloudTo_spinBox.value())
        DATE_FROM = str(self.dlg.dateEdit.date().toPyDate())
        DATE_TO = str(self.dlg.dateEdit_2.date().toPyDate())

        query = {
            'eo:cloud_cover': {
                'lte' : CLOUD_TO,
                'gte' : CLOUD_FROM
            }
        }

        if searching_collection_name:
            query['collection'] = {'eq' : searching_collection_name}

        intersects_geojson_data = self.buildGeoJSON()

        date_param_string = f"{DATE_FROM}/{DATE_TO}"
        
        if searching_collection_name == "landsat-8-l1":
            self.check_landsat8_filekeys()
        elif searching_collection_name == "sentinel-2-l1c":
            self.check_sentinel2_filekeys()

        items = []
        if searching_collection_name == "landsat-8-l1":
            landsat_tiers = self.checking_landsat8_category()
            for tier in landsat_tiers: 
                query['landsat:tier'] = {"eq" : tier}

                if intersects_geojson_data is not None:
                    search = Search(intersects=intersects_geojson_data, time=date_param_string, query=query)
                else:
                    search = Search(time=date_param_string, query=query)
                
                items += search.items()
        else:
            if intersects_geojson_data is not None:
                search = Search(intersects=intersects_geojson_data, time=date_param_string, query=query)
            else:
                search = Search(time=date_param_string, query=query)
            items = search.items()

        PATH = str(self.dlg.folderPath_lineEdit.text())
        self.dlg.logWindow.appendPlainText("["+str(datetime.datetime.now().strftime ("%H:%M:%S")) + "]" +" Файлы будут загружены в директорию: " + PATH)
        self.dlg.logWindow.appendPlainText("["+str(datetime.datetime.now().strftime ("%H:%M:%S")) + "]" +" К загрузке представлено сцен - " + str(len(items)))
        self.dlg.logWindow.appendPlainText("["+str(datetime.datetime.now().strftime ("%H:%M:%S")) + "]" +" Каналы (файлы) к загрузке - " + ", ".join(FILEKEYS))

        self.dlg.stopDownloadingButton.setEnabled(True)
        self.dlg.interruptingButton.setEnabled(True)
        self.dlg.downloadScenesButton.setEnabled(False)

        self.worker = DownloadWorker()
        self.worker.scenes = items
        self.worker.filekeys = FILEKEYS
        self.worker.path = PATH
        self.worker.work_started.connect(self.work_is_starting)
        self.worker.data_downloaded.connect(self.download_ready)
        self.worker.work_finished.connect(self.work_ready)

        try:
            self.worker.start()
        except:
            self.stop_worker()


    def reloadAOICoordinates(self):
        del AOI_COORDINATES[:]


    def buildGeoJSON(self):

        if not AOI_COORDINATES:
            self.dlg.logWindow.appendPlainText("["+str(datetime.datetime.now().strftime ("%H:%M:%S")) + "]" +" Область интереса не была выбрана! Поиск будет осуществляться по всей территории Земли.")
            return None

        if not self.capturer.rubberBand.asGeometry().isGeosValid():
            self.iface.messageBar().pushWarning("Error", "Не валидный полигон! Дальнейший поиск будет осуществляться без учета выбранной территории")           
            return None

        geojson = "{\"type\": \"Feature\", \"properties\": {},\"geometry\": {\"type\": \"Polygon\", \"coordinates\": [" + str(AOI_COORDINATES + [AOI_COORDINATES[0]])+"]}}"
        # self.dlg.logWindow.appendPlainText(str(geojson))

        return str(geojson)


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
