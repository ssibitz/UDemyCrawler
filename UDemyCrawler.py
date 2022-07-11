import json
import os
import pickle
import re
import sys
import traceback
import webbrowser

import config
import util_logging as log
from PySide2 import QtWidgets, QtCore, QtGui
from PySide2.QtGui import QIcon, QFont
from PySide2.QtWidgets import QWidget, QVBoxLayout, QApplication, \
    QProgressBar, QLabel, QMainWindow, QAction, QDialog, QDialogButtonBox, QLineEdit, QFormLayout, QMessageBox, \
    QFileDialog, QComboBox, QCheckBox
from util_downloader import DownloaderThread
from util_webengine import QWebEngineViewPlus
from urllib.request import Request, urlopen
from bs4 import BeautifulSoup
from pprint import pformat

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

        #
        # --- File menu
        #
        fileMenu = mainMenu.addMenu("File")
        # -User configuration
        fileMenu.addSeparator()
        userConfigAction = QAction(QIcon(config.FontAweSomeIcon("wrench.svg")), "Settings", self)
        userConfigAction.setShortcut("Ctrl+Alt+S")
        userConfigAction.triggered.connect(self.OnConfigChange)
        fileMenu.addAction(userConfigAction)
        # Log off currrent user + exit
        fileMenu.addSeparator()
        switchAction = QAction(QIcon(config.FontAweSomeIcon("right-from-bracket.svg")), "Log off current user + Quit application", self)
        switchAction.setShortcut("Ctrl+U")
        switchAction.triggered.connect(self.OnSwitchUserClicked)
        fileMenu.addAction(switchAction)
        # Exit
        fileMenu.addSeparator()
        exitAction = QAction("Exit", self)
        exitAction.setShortcut("Ctrl+X")
        exitAction.triggered.connect(self.exit_app)
        fileMenu.addAction(exitAction)

        #
        # --- Actions menu
        #
        actionsMenu = mainMenu.addMenu("Actions")
        # Reload page
        restartAction = QAction(QIcon(config.FontAweSomeIcon("rotate.svg")), "Jump to my courses landing page", self)
        restartAction.setShortcut("Ctrl+Alt+R")
        restartAction.triggered.connect(self.OnJump2Overview)
        actionsMenu.addAction(restartAction)
        # Jump to generated overview page
        overviewAction = QAction(QIcon(config.FontAweSomeIcon("box-archive.svg")), "Jump to generated overview of all downloaded courses", self)
        overviewAction.triggered.connect(self.OnJump2GeneratedOverview)
        actionsMenu.addAction(overviewAction)
        # Generate an overview of all courses (html)
        actionsMenu.addSeparator()
        overviewAction = QAction(QIcon(config.FontAweSomeIcon("table-list.svg")), "Generate an overview of all downloaded courses", self)
        overviewAction.setShortcut("Ctrl+Alt+O")
        overviewAction.triggered.connect(self.OnGenerateOverview)
        actionsMenu.addAction(overviewAction)
        # Cancel current download
        actionsMenu.addSeparator()
        cancelDownloadAction = QAction("Cancel current download", self)
        cancelDownloadAction.setShortcut("Ctrl+Alt+C")
        cancelDownloadAction.triggered.connect(self.OnCancelDownload)
        actionsMenu.addAction(cancelDownloadAction)

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
        ret = QMessageBox.question(self, 'Logoff user',
                                   f"Do you really want to logout from UDemy?\n\nYou must re-start the application and re-login!",
                                   QMessageBox.Yes | QMessageBox.No)
        if ret == QMessageBox.Yes:
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

    def GetTitleFromCourseId(self, CourseId):
        url = config.UDEMY_API_COURSE_TITLE.format(CourseId=CourseId)
        log.info(f"Getting course title for course with id '{CourseId}'")
        log.info(f" Course url is: '{url}'")
        # Get more information on course:
        req = Request(url, headers=self.RequestHeaders())
        res = urlopen(req).read()
        # Convert to json
        CourseInfo = json.loads(res.decode("utf-8"))
        log.debug(pformat(CourseInfo))
        Title = CourseInfo[config.UDEMY_API_FIELD_COURSE_TITLE]
        log.info(f"Title:\n{Title}")
        return Title

    def GenerateCourseInfoFile(self, CourseInfoFile, CourseInfo):
        with open(CourseInfoFile, 'wb') as f:
            pickle.dump(CourseInfo, f, pickle.HIGHEST_PROTOCOL)

    def LoadCourseInfoFile(self, CourseInfoFile):
        with open(CourseInfoFile, 'rb') as f:
            return pickle.load(f)

    def BuildCourseInfos(self):
        CourseFolders = [f.path for f in os.scandir(self.cfg.DownloadPath) if f.is_dir()]
        Courses = []
        for CourseFolder in CourseFolders:
            # Check if course in in folder exists
            CourseInfo = {
                "Id" : 0,
                "Title" : "",
                "Path" : ""
            }
            # Load already stored course info if available:
            CourseInfoFile = CourseFolder+os.sep+config.COURSE_ID_FILE_NAME
            if os.path.exists(CourseInfoFile):
                CourseInfo = self.LoadCourseInfoFile(CourseInfoFile)
            else:
                # Get course id from hashtag in pathname:
                try:
                    CourseId = re.findall(r'#(.+?)#', CourseFolder)[0]
                    CourseInfo["Id"] = int(CourseId)
                    CourseInfo["Title"] = self.GetTitleFromCourseId(CourseInfo["Id"])
                    CourseInfo["Path"] = CourseFolder
                    self.GenerateCourseInfoFile(CourseInfoFile, CourseInfo)
                except Exception as error:
                    CourseInfo["Id"] = 0
                    log.error(f"An error has been occured on CourseFolder {CourseFolder}:")
                    log.error(traceback.format_exc())

            # Add course info to list
            if CourseInfo["Id"] > 0:
                Courses.append(CourseInfo)
        return Courses

    def AddHTMLCourse(self, CourseId, CourseTitle, CoursePath):
        CoursePathPrepared = CoursePath.replace("\\","/").replace("#","%23")
        CoursePathURL = f"file:///{CoursePathPrepared}/"
        CourseImage = f"{CoursePathURL}/{config.COURSE_PREVIEW_IMAGE_NAME}"
        HTMLCourse = (
            "\n"
           f"       <div class='card' data-filter='{CourseTitle}'>\n"
           f"           <img src='{CourseImage}' class='card-img-top' alt='' width='240px'></img>" 
            "           <div class='card-body'>\n"
           f"               <h4 class='card-title'>Course ID: {CourseId}</h4>\n"
           f"               <p>{CourseTitle}</p>\n"
           f"               <a class='card-link' href='{CoursePathURL}'>Open folder</a>\n"   
            "           </div>\n"
            "       </div>\n\n"
        )
        return HTMLCourse

    def GenerateOverview(self, dogenerate, askuser):
        # Overview filename
        overviewfilename = self.cfg.DownloadPath + os.sep + config.COURSE_OVERVIEW_FILE_NAME
        # Generate overview ?
        if dogenerate:
            # Build a list of all courses in each folder
            Courses = self.BuildCourseInfos()
            # Now build an html overview of all available courses
            if Courses:
                HTML = ""
                for Course in Courses:
                    CourseId = Course["Id"]
                    CourseTitle = Course["Title"]
                    CoursePath = Course["Path"]
                    HTML = HTML + self.AddHTMLCourse(CourseId, CourseTitle, CoursePath)
                # Add header and footer
                HTML = config.HTML_HEADER + HTML + config.HTML_FOOTER
                # Write an index.html file to main download folder
                desc = open(overviewfilename, "w", encoding="utf-8")
                desc.write(HTML)
                desc.close()
        # Open generated overview ?
        openit = True
        if askuser:
            ret = QMessageBox.question(self, 'Finished',
                                       f"Overview has been generated.\nDo you want to view it ?",
                                       QMessageBox.Yes | QMessageBox.No)
            if not ret == QMessageBox.Yes:
                openit = False
        if openit:
            overviewfilename = overviewfilename.replace("\\", "/")
            OverviewFile = f"file:///{overviewfilename}"
            webbrowser.open(OverviewFile, new=0, autoraise=True)

    def OnGenerateOverview(self):
        self.GenerateOverview(True, True)

    def OnJump2GeneratedOverview(self):
        overviewfilename = self.cfg.DownloadPath + os.sep + config.COURSE_OVERVIEW_FILE_NAME
        if not os.path.exists(overviewfilename):
            self.GenerateOverview(True, False)
        else:
            self.GenerateOverview(False, False)

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
