from __future__ import annotations
from PySide2.QtCore import QSettings
from PySide2.QtGui import QIcon
from PySide2.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout, QFormLayout, QLabel, QComboBox, QCheckBox, \
    QLineEdit, QFileDialog, QAction, QMessageBox
import os.path, util_logging as log, util_constants as const, util_ffmpeg as ffmpeg
import subprocess


class AppSettings(QDialog):
    def __init__(self, accesstokenvalue):
        super().__init__()
        self.cfg = GlobalSettings()
        self.access_token_value = accesstokenvalue
        self.initUI()
        self.Load()

    def initUI(self):
        # Title and icon
        self.setWindowTitle("Settings")
        self.setWindowIcon(QIcon(const.AppIcon()))
        self.setGeometry(100, 100, 600, 200)
        # Save or cancel button
        QBtn = QDialogButtonBox.Save | QDialogButtonBox.Cancel
        buttonBox = QDialogButtonBox(QBtn)
        buttonBox.button(QDialogButtonBox.Save).clicked.connect(self.Save)
        buttonBox.button(QDialogButtonBox.Cancel).clicked.connect(self.Cancel)
        layout = QVBoxLayout()
        formLayout = QFormLayout()
        # Path of application setting
        ActionOpenAppPath = QAction(QIcon(const.FontAweSomeIcon("folder-open.svg")), "", self)
        ActionOpenAppPath.setToolTip("Open app path")
        ActionOpenAppPath.triggered.connect(self.OnActionOpenAppPath)
        self.cfgAppPath = QLineEdit()
        self.cfgAppPath.setReadOnly(True)
        self.cfgAppPath.addAction(ActionOpenAppPath, QLineEdit.TrailingPosition)
        formLayout.addRow("App path", self.cfgAppPath)
        # Start application on monitor
        cfgStartLabel = QLabel("Open on monitor", self)
        self.cfgStartValue = QComboBox()
        self.cfgStartValue.addItem("Automatic", -1)
        self.cfgStartValue.addItem("Primary monitor", 0)
        self.cfgStartValue.addItem("Secondary monitor", 1)
        formLayout.addRow(cfgStartLabel, self.cfgStartValue)
        # FFMPEG path
        ActionSettingsDownloadInstallFFMPEG = QAction(QIcon(const.FontAweSomeIcon("download.svg")), "", self)
        ActionSettingsDownloadInstallFFMPEG.setToolTip("Download and install latest version of FFMPEG")
        ActionSettingsDownloadInstallFFMPEG.triggered.connect(self.OnActionDownloadInstallFFMPEG)
        self.cfgFFMPEGValue = QLineEdit()
        self.cfgFFMPEGValue.setReadOnly(True)
        self.cfgFFMPEGValue.addAction(ActionSettingsDownloadInstallFFMPEG, QLineEdit.TrailingPosition)
        formLayout.addRow("FFMPEG path", self.cfgFFMPEGValue)
        # Add status label for FFMPEG
        self.StatusBarLabel = QLabel("")
        formLayout.addRow("", self.StatusBarLabel)
        # Course (download) path
        ActionSettingsChooseDownloadPath = QAction(QIcon(const.FontAweSomeIcon("folder-plus.svg")), "", self)
        ActionSettingsChooseDownloadPath.setToolTip("Choose courses path")
        ActionSettingsChooseDownloadPath.triggered.connect(self.OnActionChooseDownloadPath)
        self.cfgDownValue = QLineEdit()
        self.cfgDownValue.addAction(ActionSettingsChooseDownloadPath, QLineEdit.TrailingPosition)
        formLayout.addRow("Courses path", self.cfgDownValue)
        # Do not download existing videos again
        self.cfgDownloadCourseVideoAgain = QCheckBox("Even if they already exists", self)
        formLayout.addRow("Download the course video(s):", self.cfgDownloadCourseVideoAgain)
        # Check file size on downloaded video
        self.cfgCheckFileSize = QCheckBox("Even if the file size is different", self)
        formLayout.addRow("", self.cfgCheckFileSize)
        # Add to layout
        layout.addLayout(formLayout)
        layout.addWidget(buttonBox)
        self.setLayout(layout)

    def OnActionOpenAppPath(self):
        AppPath = os.path.dirname(os.path.abspath(self.cfg.SettingsFilePath))
        if not AppPath == "":
            cmd = fr'explorer "{AppPath}"'
            subprocess.Popen(cmd)

    def OnActionChooseDownloadPath(self):
        dir = str(QFileDialog.getExistingDirectory(self, "Choose directory"))
        if not dir == "":
            self.cfgDownValue.setText(dir)
            self.Save(True)

    def OnActionDownloadInstallFFMPEG(self):
        # Save entered settings before
        self.Save(True)
        Thread = ffmpeg.FFMPEGDownloadInstallThread(self, self.access_token_value)
        Thread._signal_info.connect(self.OnSignalInfo)
        Thread._signal_error.connect(self.OnSignalError)
        Thread._signal_done.connect(self.OnSignalFFMPEGDownloadedInstalled)
        Thread.start()
        self.BlockUI(True)

    def BlockUI(self, block=True):
        self.setEnabled(not block)
        self.StatusBarLabel.setEnabled(True)

    def OnSignalInfo(self, message):
        log.info(message)
        self.StatusBarLabel.setText(message)

    def OnSignalError(self, message):
        self.BlockUI(False)
        log.error(message)
        self.StatusBarLabel.setText(message)
        QMessageBox.critical(self, "Error occured", message)

    def OnSignalFFMPEGDownloadedInstalled(self, dir):
        self.BlockUI(False)
        if not dir == "":
            self.Save(True)
            QMessageBox.information(self, "Done", "FFMPEG sucessfully downloaded and installed !")

    def Load(self):
        # Reload configs
        self.cfg.LoadConfigs()
        # Application path where FFMPEG is installed and settings are stored
        self.cfgAppPath.setText(const.GlobalPaths().AppDataPath())
        # Start on monitor
        StartValueDataIndex = self.cfgStartValue.findData(self.cfg.StartOnMonitorNumber)
        if StartValueDataIndex >= 0:
            self.cfgStartValue.setCurrentIndex(StartValueDataIndex)
        # FFMPEG
        self.cfgFFMPEGValue.setText(self.cfg.FFMPEGPath)
        if self.cfgFFMPEGValue.text() == "":
            self.StatusBarLabel.setText(const.USR_CONFIG_STATUSBAR_DEFAULT_LABEL_NOT_FOUND)
            self.StatusBarLabel.setStyleSheet("QLabel { color : red }")
        else:
            self.StatusBarLabel.setText(const.USR_CONFIG_STATUSBAR_DEFAULT_LABEL_INSTALLED)
            self.StatusBarLabel.setStyleSheet("QLabel { color : black }")
        # Download path
        self.cfgDownValue.setText(self.cfg.DownloadPath)
        # Download again
        self.cfgDownloadCourseVideoAgain.setChecked(self.cfg.DownloadCourseVideoAgain)
        # Check file size
        self.cfgCheckFileSize.setChecked(self.cfg.DownloadCourseVideoCheckFileSize)

    def Save(self, saveonly=False):
        self.cfg.StartOnMonitorNumber = int(self.cfgStartValue.currentData())
        self.cfg.DownloadPath = self.cfgDownValue.text()
        self.cfg.DownloadCourseVideoAgain = self.cfgDownloadCourseVideoAgain.isChecked()
        self.cfg.DownloadCourseVideoCheckFileSize = self.cfgCheckFileSize.isChecked()
        self.cfg.SaveConfigs()
        log.info(f"Configuration has been saved !")
        if not saveonly:
            self.accept()
        else:
            self.Load()

    def Cancel(self):
        self.reject()


class Settings():
    __instance = None

    @staticmethod
    def getInstance() -> Settings:
        """ Static access method. """
        if Settings.__instance == None:
            Settings()
        return Settings.__instance

    def __init__(self):
        """ Virtually private constructor. """
        if Settings.__instance != None:
            raise Exception("This class is a singleton!")
        else:
            Settings.__instance = self
        # Use ffmpeg util to check if installed or not
        self.ffmpeg_util = ffmpeg.FFMPEGUtil()
        # Set default values
        self.StartOnMonitorNumber = const.USR_CONFIG_START_ON_MONITOR_DEFAULT
        self.DownloadPath = const.USR_CONFIG_DOWNLOAD_PATH_DEFAULT
        self.DownloadCourseVideoCheckFileSize = const.USR_CONFIG_DOWNLOAD_CHECK_FILESIZE_DEFAULT
        self.DownloadCourseVideoAgain = const.USR_CONFIG_DOWNLOAD_COURSE_AGAIN_DEFAULT
        # Check if FFMPEG ist available (as relative path)
        self.FFMPEGPath = const.USR_CONFIG_FFMPEG_PATH_DEFAULT
        if self.ffmpeg_util.Available():
            path = const.GlobalPaths().AppDataPath()
            self.FFMPEGPath = os.path.relpath(self.ffmpeg_util.FFMPEGUtilFullPath(), path)
        else:
            self.FFMPEGPath = const.USR_CONFIG_FFMPEG_PATH_DEFAULT
        # Init setting
        self.SettingsFilePath = const.GlobalPaths().AppDataPath() + "/" + const.APP_INIFILE_NAME
        self.settings = None
        self.InitSettings()
        self.LoadConfigs()

    def InitSettings(self, recreate=False):
        if self.settings is None:
            log.info(f"(Re)load setting stored in '{self.SettingsFilePath}'")
            self.settings = QSettings(self.SettingsFilePath, QSettings.IniFormat)
        else:
            if recreate:
                del self.settings
                self.settings = None
                self.InitSettings(False)

    def LoadConfigs(self):
        self.StartOnMonitorNumber = self.valueToInt(self.settings.value(const.USR_CONFIG_START_ON_MONITOR,
                                                                        const.USR_CONFIG_START_ON_MONITOR_DEFAULT))
        self.DownloadPath = self.settings.value(const.USR_CONFIG_DOWNLOAD_PATH, const.USR_CONFIG_DOWNLOAD_PATH_DEFAULT)
        # self.TempPath = self.settings.value(const.USR_CONFIG_TEMP_PATH, const.USR_CONFIG_TEMP_PATH_DEFAULT)
        # Check if FFMPEG ist available (as relative path)
        if self.ffmpeg_util.Available():
            path = const.GlobalPaths().AppDataPath()
            self.FFMPEGPath = os.path.relpath(self.ffmpeg_util.FFMPEGUtilFullPath(), path)
        else:
            self.FFMPEGPath = const.USR_CONFIG_FFMPEG_PATH_DEFAULT
        self.DownloadCourseVideoAgain = self.valueToBool(
            self.settings.value(const.USR_CONFIG_DOWNLOAD_COURSE_AGAIN, const.USR_CONFIG_DOWNLOAD_COURSE_AGAIN_DEFAULT))
        self.DownloadCourseVideoCheckFileSize = self.valueToBool(
            self.settings.value(const.USR_CONFIG_DOWNLOAD_CHECK_FILESIZE,
                                const.USR_CONFIG_DOWNLOAD_CHECK_FILESIZE_DEFAULT))

    def SaveConfigs(self):
        self.settings.setValue(const.USR_CONFIG_START_ON_MONITOR, self.StartOnMonitorNumber)
        self.settings.setValue(const.USR_CONFIG_DOWNLOAD_PATH, self.DownloadPath)
        # self.settings.setValue(const.USR_CONFIG_TEMP_PATH, self.TempPath)
        self.settings.setValue(const.USR_CONFIG_DOWNLOAD_COURSE_AGAIN, self.DownloadCourseVideoAgain)
        self.settings.setValue(const.USR_CONFIG_DOWNLOAD_CHECK_FILESIZE, self.DownloadCourseVideoCheckFileSize)
        self.settings.sync()
        self.InitSettings(True)

    @staticmethod
    def valueToBool(value):
        return value.lower() == 'true' if isinstance(value, str) else bool(value)

    @staticmethod
    def valueToInt(value):
        return int(value)


# Global access settings via singleton function
def GlobalSettings() -> Settings:
    return Settings.getInstance()
