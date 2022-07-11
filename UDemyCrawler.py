import json
import os
import sys
import traceback
from urllib.request import Request, urlopen
from bs4 import BeautifulSoup

import config
import util_logging as log
from PySide2 import QtWidgets, QtCore, QtGui
from PySide2.QtGui import QIcon, QFont, QIntValidator
from PySide2.QtWidgets import QWidget, QVBoxLayout, QApplication, QHBoxLayout, QPushButton, \
    QProgressBar, QLabel, QMainWindow, QAction, QDialog, QDialogButtonBox, QLineEdit, QFormLayout, QMessageBox, \
    QFileDialog, QComboBox, QCheckBox
from util_downloader import DownloaderThread
from util_webengine import QWebEngineViewPlus

class UDemyWebCrawlerConfig(QDialog):
    def __init__(self):
        super().__init__()
        self.cfg = config.UserConfig()
        self.cfg.LoadConfigs()
        self.setWindowTitle("User configuration")
        self.setWindowIcon(QIcon(config.AppIcon()))
        self.initUI()

    def initUI(self):
        # Save or cancel button
        QBtn = QDialogButtonBox.Save | QDialogButtonBox.Open | QDialogButtonBox.Cancel
        self.buttonBox = QDialogButtonBox(QBtn)
        self.buttonBox.button(QDialogButtonBox.Save).clicked.connect(self.Save)
        self.buttonBox.button(QDialogButtonBox.Open).setText("Choose path")
        self.buttonBox.button(QDialogButtonBox.Open).clicked.connect(self.Open)
        self.buttonBox.button(QDialogButtonBox.Cancel).clicked.connect(self.Cancel)
        self.layout = QVBoxLayout()
        formLayout = QFormLayout()
        # Start on monitor
        cfgStartLabel = QLabel("Default start on monitor", self)
        self.cfgStartValue = QComboBox()
        self.cfgStartValue.addItem("Disabled", -1)
        self.cfgStartValue.addItem("Primary monitor", 0)
        self.cfgStartValue.addItem("Secondary monitor", 1)
        StartValueDataIndex = self.cfgStartValue.findData(self.cfg.StartOnMonitorNumber)
        if StartValueDataIndex >= 0:
            self.cfgStartValue.setCurrentIndex(StartValueDataIndex)
        formLayout.addRow(cfgStartLabel, self.cfgStartValue)
        # Do not download existing videos again
        cfgDownloadCourseVideoAgainLabel = QLabel("Download course video(s) again", self)
        self.cfgDownloadCourseVideoAgain= QCheckBox(self)
        self.cfgDownloadCourseVideoAgain.setChecked(self.cfg.DownloadCourseVideoAgain)
        formLayout.addRow(cfgDownloadCourseVideoAgainLabel, self.cfgDownloadCourseVideoAgain)
        # Download path
        cfgDownLabel = QLabel("Download path", self)
        self.cfgDownValue = QLineEdit()
        self.cfgDownValue.setText(self.cfg.DownloadPath)
        formLayout.addRow(cfgDownLabel, self.cfgDownValue)
        # Add to layout
        self.layout.addLayout(formLayout)
        self.layout.addWidget(self.buttonBox)
        self.setLayout(self.layout)

    def Save(self):
        self.cfg.StartOnMonitorNumber = int(self.cfgStartValue.currentData())
        self.cfg.DownloadPath = self.cfgDownValue.text()
        self.cfg.DownloadCourseVideoAgain = self.cfgDownloadCourseVideoAgain.isChecked()
        self.cfg.SaveConfigs()
        log.info(f"Configuration has been saved !")
        self.accept()

    def Open(self):
        self.cfgDownValue.setText(str(QFileDialog.getExistingDirectory(self, "Select directory")))

    def Cancel(self):
        self.reject()

class UDemyWebCrawler(QMainWindow):

    def __init__(self):
        super().__init__()
        log.InitLogging()
        self.init()
        self.initUI()
        self.CreateMenu()

    def init(self):
        # Reset cancel trigger
        self.ThreadCancelTrigger = None
        # Reset vars
        self.access_token = ""
        self.access_token_value = ""
        # Build webview
        self.cfg = config.UserConfig()
        self.web = QWebEngineViewPlus()
        self.OnSwitchUser(False, None)

    def initUI(self):
        # Progress bar
        self.progressBar = QProgressBar(self)
        self.progressBar.setGeometry(QtCore.QRect(170, 420, 391, 23))
        self.progressBar.setProperty("value", 0)
        self.progressBar.setAlignment(QtCore.Qt.AlignCenter)
        # Progress bar label
        self.progressBarLabel = QLabel(config.PROGRESSBAR_LABEL_DEFAULT, self)
        self.progressBarLabel.setFont(QFont('Times', 16))
        self.progressBarLabel.setAlignment(QtCore.Qt.AlignCenter)
        self.progressBarLabel.setMaximumHeight(26)
        # Layout
        vbox = QVBoxLayout(self)
        vbox.addWidget(self.web)
        vbox.addWidget(self.progressBarLabel)
        vbox.addWidget(self.progressBar)
        # Central widget
        central = QWidget()
        central.setLayout(vbox)
        self.setCentralWidget(central)
        self.setGeometry(100, 100, 1024, 768)
        self.setWindowTitle(config.APP_TITLE)
        self.setWindowIcon(QIcon(config.AppIcon()))
        self.show()
        # Center window on custom monitor
        NumberOfScreens = len(QtGui.QGuiApplication.screens())
        StartOnMonitor = int(self.cfg.StartOnMonitorNumber)
        if  NumberOfScreens > 1 and StartOnMonitor >= 0:
            w = self.window()
            w.setGeometry(QtWidgets.QStyle.alignedRect(QtCore.Qt.LeftToRight, QtCore.Qt.AlignCenter, w.size(),
                                                       QtGui.QGuiApplication.screens()[StartOnMonitor].availableGeometry(), ), )

    def CreateMenu(self):
        mainMenu = self.menuBar()
        fileMenu = mainMenu.addMenu("File")
        # Switch user + exit
        switchAction = QAction("Switch user + Quit application", self)
        switchAction.setShortcut("Ctrl+U")
        switchAction.triggered.connect(self.OnSwitchUserClicked)
        fileMenu.addAction(switchAction)
        # Reload page
        restartAction = QAction("Reload my coursess", self)
        restartAction.setShortcut("Ctrl+Alt+R")
        restartAction.triggered.connect(self.OnJump2Overview)
        fileMenu.addAction(restartAction)
        # Cancel current download
        cancelDownloadAction = QAction("Cancel current download", self)
        cancelDownloadAction.setShortcut("Ctrl+Alt+C")
        cancelDownloadAction.triggered.connect(self.OnCancelDownload)
        fileMenu.addAction(cancelDownloadAction)
        # User config
        fileMenu.addSeparator()
        userConfigAction = QAction("Settings", self)
        userConfigAction.setShortcut("Ctrl+Alt+S")
        userConfigAction.triggered.connect(self.OnConfigChange)
        fileMenu.addAction(userConfigAction)
        # Load all courses
        #loadAllAction = QAction("Load all courses on site", self)
        #loadAllAction.triggered.connect(self.LoadAll)
        #fileMenu.addAction(loadAllAction)
        # Exit
        fileMenu.addSeparator()
        exitAction = QAction("Exit", self)
        exitAction.setShortcut("Ctrl+X")
        exitAction.triggered.connect(self.exit_app)
        fileMenu.addAction(exitAction)

    def exit_app(self):
        self.close()

    def BlockUI(self, block=True):
        self.web.setDisabled(block)
        if not block:
            self.progressBarLabel.setText(config.PROGRESSBAR_LABEL_DEFAULT)
        else:
            self.progressBarLabel.setText(config.PROGRESSBAR_LABEL_DOWNLOAD)
            self.ApplyBlockStyle()

    def RequestHeaders(self):
        HEADERS = config.HEADER_DEFAULT
        HEADERS.update({config.HEADER_COOKIE_NAME : config.HEADER_COOKIE_ACCESS_TOKEN.format(access_token_value=self.access_token_value)})
        HEADERS.update({'Content-Type' : 'application/json; charset=utf-8'})
        return HEADERS

    # Handlers + Helpers
    def OnSwitchUser(self, clearall, ondonecallback=None):
        self.web.AddCookieFilterCallbackOnURL(config.UDEMY_MAIN_COURSE_OVERVIEW, config.UDEMY_ACCESS_TOKEN_NAME,
                                              self.OnTokenFound)
        self.web.ConnectOnUrlChanged(self.OnURLChanged)
        self.web.ClearCookiesOnURL(config.UDEMY_MAIN_LOGON_URL, ondonecallback, clearall)

    def OnSwitchUserClicked(self):
        self.OnSwitchUser(True, self.OnSwitchUserClickedDone)

    def LoadAll(self):
        script = (
            #"document.documentElement.innerHTML;"
            "document.getElementsByClassName('my-courses__course-card-grid')[0].innerHTML"
        )
        log.info(f"Loadall script:\n{script}")
        self.web.RunJavaScript(script, self.LoadAllDone)

    def LoadAllDone(self, html):
        log.info("------- LoadAllDone result:")
        log.info(html)
        soup = BeautifulSoup(html, "html.parser")
        alllinks = soup.find_all("a")
        log.info(alllinks)

    def OnConfigChange(self):
        dlg = UDemyWebCrawlerConfig()
        if dlg.exec_():
            self.cfg.LoadConfigs()

    def OnSwitchUserClickedDone(self, html):
        self.close()

    def OnJump2Overview(self):
        # Jump to course overview
        self.web.href(config.UDEMY_MAIN_COURSE_OVERVIEW, None, self.OnCourseClicked)

    def ApplyStyleChanges(self):
        script = (
            "var sheet = document.createElement('style');\n"
            f"sheet.innerHTML = {config.MAIN_STYLE} ;\n"
            "document.body.appendChild(sheet);"
        )
        log.info(f"Script:\n{script}")
        self.web.RunJavaScript(script)

    def ApplyBlockStyle(self):
        script = (
            "var sheet = document.createElement('style');\n"
            f"sheet.innerHTML = {config.BLOCK_STYLE} ;\n"
            "document.body.appendChild(sheet);"
        )
        log.info(f"Script blockstyle:\n{script}")
        self.web.RunJavaScript(script)

    # Page states
    def OnURLChanged(self, url):
        log.info(f"URL has been changed : '{url}' - apply style changes.")
        if "my-courses" in url.toString():
            self.ApplyStyleChanges()

    def OnTokenFound(self, TokenName, TokenValue):
        self.access_token_value = TokenValue
        self.access_token = TokenName + "=" + self.access_token_value
        log.info(f"Got access_token : {self.access_token}")
        self.OnJump2Overview()

    def OnCourseClicked(self, course_url):
        log.info(f"Start downloading course from url : {course_url}")
        self.course_url = course_url
        self.ResetProgress()
        Thread = DownloaderThread(self, course_url, self.access_token_value)
        Thread._signal_progress.connect(self.OnCourseDownloadProgressChanged)
        Thread._signal_done.connect(self.OnCourseDownloaded)
        Thread._signal_error.connect(self.OnCourseDownloadError)
        self.ThreadCancelTrigger = Thread.TriggerCancelDownload
        Thread.start()
        self.BlockUI(True)

    def OnCancelDownload(self):
        if not self.ThreadCancelTrigger is None:
            ret = QMessageBox.question(self, 'Cancel download',
                                       f"Do you want to cancel downloading course ?",
                                       QMessageBox.Yes | QMessageBox.No)
            try:
                if ret == QMessageBox.Yes:
                    self.ThreadCancelTrigger()
                    self.ThreadCancelTrigger = None
            except Exception as error:
                pass

    def ResetProgress(self):
        self.progressBar.setValue(0)
        self.progressBar.setFormat(config.PROGRESSBAR_LABEL_DEFAULT)
        self.BlockUI(False)

    def OnCourseDownloadProgressChanged(self, cnt, idx, max, coursetitle, finishtime):
        self.progressBar.setValue(int(cnt))
        self.progressBar.setFormat(f"{cnt}% [{idx}\\{max}] courses loaded from '{coursetitle}', estimated finish time: {finishtime}")

    def OnCourseDownloaded(self, courseid, coursename):
        self.ThreadCancelTrigger = None
        self.ResetProgress()
        # Ask user to archive course
        ret = QMessageBox.question(self,'Finished', f"Course {coursename} has been downloaded.\nDo you want to archive course ?", QMessageBox.Yes | QMessageBox.No)
        if ret == QMessageBox.Yes:
            try:
                # Get more information on course:
                body = {
                    "course_id": courseid
                }
                req = Request(config.UDEMY_API_ARCHIVE_COURSE)
                for key in self.RequestHeaders():
                    req.add_header(key, self.RequestHeaders()[key])
                jsondata = json.dumps(body)
                jsondataasbytes = jsondata.encode('utf-8')
                req.add_header('Content-Length', len(jsondataasbytes))
                self.result = urlopen(req, jsondataasbytes)
            except Exception as error:
                log.error(f"An error has been occured on Course {coursename}:")
                log.error(traceback.format_exc())
            else:
                # Reload current page
                log.info(self.result)
                self.web.href(self.web.url(), self.OnCourseDownloadedReloaded, self.OnCourseClicked)
        else:
            # Reload current page
            self.web.href(self.web.url(), self.OnCourseDownloadedReloaded, self.OnCourseClicked)

    def OnCourseDownloadedReloaded(self, html):
        self.ThreadCancelTrigger = None
        self.ApplyStyleChanges()

    def OnCourseDownloadError(self, message):
        self.ThreadCancelTrigger = None
        self.ResetProgress()
        # Show/Log message
        log.error(message)
        QMessageBox.critical(self, "An error has been occured", message)
        # Reload current page
        self.web.href(self.web.url(), self.OnCourseDownloadedReloaded, self.OnCourseClicked)

if __name__ == '__main__':
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    app = QApplication(sys.argv)
    app.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)
    ex = UDemyWebCrawler()
    sys.exit(app.exec_())
