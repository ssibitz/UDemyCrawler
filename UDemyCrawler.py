import json, os, sys, traceback, util_logging as log, util_constants as const, util_downloader as downloader, \
    util_webengine as webengine, util_settings, util_overview as overview, util_ffmpeg as ffmpeg
from urllib.request import Request, urlopen
from PySide2 import QtWidgets, QtCore, QtGui
from PySide2.QtGui import QIcon, QFont
from PySide2.QtWidgets import QWidget, QVBoxLayout, QApplication, \
    QProgressBar, QLabel, QMainWindow, QAction, QMessageBox
from bs4 import BeautifulSoup


class UDemyWebCrawler(QMainWindow):

    def __init__(self):
        super().__init__()
        log.InitLogging()
        self.init()
        self.initUI()
        self.CreateMenu()
        self.BlockUI()

    def init(self):
        # Reset cancel trigger
        self.ThreadCancelTrigger = None
        # Reset vars
        self.access_token = ""
        self.access_token_value = ""
        # Init used classes
        self.cfg = util_settings.Settings()
        self.web = webengine.QWebEngineViewPlus()
        # Load mysources page of udemy
        self.SwitchUser(False, None)

    def initUI(self):
        # Main application settings
        self.setGeometry(100, 100, 1024, 768)
        self.setWindowTitle(const.APP_TITLE)
        self.setWindowIcon(QIcon(const.AppIcon()))
        # Progress bar label
        self.progressBarLabel = QLabel(const.PROGRESSBAR_LABEL_DEFAULT, self)
        self.progressBarLabel.setFont(QFont('Times', 16))
        self.progressBarLabel.setAlignment(QtCore.Qt.AlignCenter)
        self.progressBarLabel.setMaximumHeight(26)
        # Progress bar
        self.progressBar = QProgressBar(self)
        self.progressBar.setGeometry(QtCore.QRect(170, 420, 391, 23))
        self.progressBar.setProperty('value', 0)
        self.progressBar.setAlignment(QtCore.Qt.AlignCenter)
        # Layout
        vbox = QVBoxLayout(self)
        vbox.addWidget(self.web)
        vbox.addWidget(self.progressBarLabel)
        vbox.addWidget(self.progressBar)
        # Central widget
        central = QWidget()
        central.setLayout(vbox)
        self.setCentralWidget(central)
        # Center window on custom monitor if activated
        if len(QtGui.QGuiApplication.screens()) > 1 and self.cfg.StartOnMonitorNumber >= 0:
            w = self.window()
            w.setGeometry(QtWidgets.QStyle.alignedRect(QtCore.Qt.LeftToRight, QtCore.Qt.AlignCenter, w.size(),
                                                       QtGui.QGuiApplication.screens()[
                                                           self.cfg.StartOnMonitorNumber].availableGeometry(), ), )
        self.show()

    def CreateMenu(self):
        mainMenu = self.menuBar()

        #
        # --- File menu
        #
        fileMenu = mainMenu.addMenu("File")
        # -User settings
        fileMenu.addSeparator()
        ActionSettings = QAction(QIcon(const.FontAweSomeIcon("wrench.svg")), "Settings", self)
        ActionSettings.setShortcut("Ctrl+Alt+S")
        ActionSettings.triggered.connect(self.OnActionSettings)
        fileMenu.addAction(ActionSettings)
        # Log off currrent user + exit
        fileMenu.addSeparator()
        ActionSwitchUser = QAction(QIcon(const.FontAweSomeIcon("right-from-bracket.svg")),
                                   "Log off current user + Quit application", self)
        ActionSwitchUser.setShortcut("Ctrl+U")
        ActionSwitchUser.triggered.connect(self.OnActionSwitchUser)
        fileMenu.addAction(ActionSwitchUser)
        # Exit
        fileMenu.addSeparator()
        ActionExit = QAction("Exit", self)
        ActionExit.setShortcut("Ctrl+X")
        ActionExit.triggered.connect(self.OnActionExit)
        fileMenu.addAction(ActionExit)

        #
        # --- Actions menu
        #
        actionsMenu = mainMenu.addMenu("Actions")
        # Reload page
        ActionJump2MyCourses = QAction(QIcon(const.FontAweSomeIcon("house.svg")), "(Re)load my courses",
                                       self)
        ActionJump2MyCourses.setShortcut("Ctrl+Alt+R")
        ActionJump2MyCourses.triggered.connect(self.OnActionJump2MyCourses)
        actionsMenu.addAction(ActionJump2MyCourses)
        # Generate an overview of all courses (html)
        # actionsMenu.addSeparator()
        # ActionGenerateOverview = QAction(QIcon(const.FontAweSomeIcon("table-list.svg")),
        #                                  "Generate an overview (html) of all downloaded courses", self)
        # ActionGenerateOverview.setShortcut("Ctrl+Alt+O")
        # ActionGenerateOverview.triggered.connect(self.OnActionGenerateOverview)
        # actionsMenu.addAction(ActionGenerateOverview)
        # Concat all video files to one using ffmpeg
        actionsMenu.addSeparator()
        ActionCombine = QAction(QIcon(const.FontAweSomeIcon("code-merge.svg")),
                                "Combine selected downloaded video courses into one video", self)
        ActionCombine.triggered.connect(self.OnActionCombine)
        actionsMenu.addAction(ActionCombine)
        # Cancel current download
        actionsMenu.addSeparator()
        self.ActionCancel = QAction("Cancel current process", self)
        self.ActionCancel.setShortcut("Ctrl+Alt+C")
        self.ActionCancel.setEnabled(False)
        self.ActionCancel.triggered.connect(self.OnActionCancel)
        actionsMenu.addAction(self.ActionCancel)

    #
    # Action(s) called by menu
    #
    def OnActionSettings(self):
        dlg = util_settings.AppSettings(self.access_token_value)
        # Center window on custom monitor if activated
        if len(QtGui.QGuiApplication.screens()) > 1 and self.cfg.StartOnMonitorNumber >= 0:
            w = dlg.window()
            w.setGeometry(QtWidgets.QStyle.alignedRect(QtCore.Qt.LeftToRight, QtCore.Qt.AlignCenter, w.size(),
                                                       QtGui.QGuiApplication.screens()[
                                                           self.cfg.StartOnMonitorNumber].availableGeometry(), ), )
        if dlg.exec_():
            self.cfg.LoadConfigs()

    def OnActionSwitchUser(self):
        ret = QMessageBox.question(self, 'Logoff user',
                                   f"Do you really want to logout from UDemy?\n\nYou must re-start the application and re-login!",
                                   QMessageBox.Yes | QMessageBox.No)
        if ret == QMessageBox.Yes:
            self.SwitchUser(True, self.OnSwitchUserDone)

    def OnActionExit(self):
        self.close()

    def OnActionGenerateOverview(self):
        if not self.access_token_value == "":
            self.overview = overview.Overview(self.access_token_value)
            self.overview.GenerateOverview(True, True)

    # When user clicked on a course - start download course
    def OnCourseClicked(self, course_url):
        log.info(f"Start downloading course from url : {course_url}")
        self.course_url = course_url
        self.ResetProgress()
        Thread = downloader.DownloaderThread(self, course_url, self.access_token_value)
        Thread._signal_progress_parts.connect(self.OnSignalPartsChanged)
        Thread._signal_progress.connect(self.OnSignalProgressChanged)
        Thread._signal_info.connect(self.OnSignalInfo)
        Thread._signal_error.connect(self.OnSignalError)
        Thread._signal_canceled.connect(self.OnSignalCanceled)
        self.ThreadCancelTrigger = Thread.TriggerCancelDownload
        Thread._signal_done.connect(self.OnSignalCoursesDownloaded)
        # Pre-check if course is protected:
        if Thread.IsCourseProtected():
            ret = QMessageBox.question(self, 'Protection',
                                       f"Course is protected!\nOnly the non protected parts will be downloaded.\n\nDo you want to continue ?",
                                       QMessageBox.Yes | QMessageBox.No)
            if not ret == QMessageBox.Yes:
                return
        Thread.start()
        self.BlockUI(True)
        self.ActionCancel.setEnabled(True)

    def OnActionCombine(self):
        # Check if FFMPEG is already installed:
        ffmpeg_util = ffmpeg.FFMPEGUtil()
        if not ffmpeg_util.Available():
            QMessageBox.critical(self, "Error!",
                                 "FFMPEG is not installed or found.\nPlease set up by opening menu\nFile->Settings : 'FFMPEG path'\n and set it up by clicking the download icon!")
            return
        # Show dialog with course selection
        dlg = ffmpeg.CourseSelection(self.access_token_value)
        # Center window on custom monitor if activated
        if len(QtGui.QGuiApplication.screens()) > 1 and self.cfg.StartOnMonitorNumber >= 0:
            w = dlg.window()
            w.setGeometry(QtWidgets.QStyle.alignedRect(QtCore.Qt.LeftToRight, QtCore.Qt.AlignCenter, w.size(),
                                                       QtGui.QGuiApplication.screens()[
                                                           self.cfg.StartOnMonitorNumber].availableGeometry(), ), )
        if dlg.exec_():
            ret = QMessageBox.question(self, 'Combine all course videos',
                                       f"This could take a long time.\nDo you want to continue?",
                                       QMessageBox.Yes | QMessageBox.No)
            if ret == QMessageBox.Yes:
                # Start combine process:
                course = dlg.Selected
                log.info(f"Start combining videos for course ")
                self.ResetProgress()
                Thread = ffmpeg.FFMPEGThread(self, self.access_token_value, course)
                Thread._signal_progress.connect(self.OnSignalProgressChanged)
                Thread._signal_info.connect(self.OnSignalInfo)
                Thread._signal_error.connect(self.OnSignalError)
                Thread._signal_canceled.connect(self.OnSignalCanceled)
                self.ThreadCancelTrigger = Thread.TriggerCancelDownload
                Thread._signal_done.connect(self.OnSignalCoursesCombined)
                Thread.start()
                self.BlockUI(True)
                self.ActionCancel.setEnabled(True)

    def OnActionCancel(self):
        if not self.ThreadCancelTrigger is None:
            ret = QMessageBox.question(self, 'Cancel',
                                       f"Do you want to cancel current process ?",
                                       QMessageBox.Yes | QMessageBox.No)
            try:
                if ret == QMessageBox.Yes:
                    self.ThreadCancelTrigger()
                    self.ThreadCancelTrigger = None
                    self.ActionCancel.setEnabled(False)
            except Exception as error:
                pass

    def OnActionJump2MyCourses(self):
        # Jump to course overview
        self.BlockUI()
        self.web.href(const.UDEMY_MAIN_COURSE_OVERVIEW, None, self.OnCourseClicked)
        self.BlockUI(False)

    #
    # Slots connected if signal from thread is coming
    #
    def OnSignalProgressChanged(self, cnt, idx, max, coursetitle, finishtime):
        self.progressBar.setValue(int(cnt))
        self.progressBar.setFormat(
            f"{cnt}% [{idx}\\{max}] courses loaded from '{coursetitle}', estimated finish time: {finishtime}")

    def OnSignalPartsChanged(self, sectionindex, lectureindex, segment, count):
        processed = int(segment / count * 100)
        PartsLabel = const.PROGRESSBAR_LABEL_DOWNLOAD_PARTS.format(Section_Index=sectionindex,
                                                                   Lecture_Index=lectureindex,
                                                                   segmentid=segment,
                                                                   segmentscount=count,
                                                                   percentdone=processed)
        self.progressBarLabel.setText(PartsLabel)

    def OnSignalInfo(self, message):
        log.info(message)
        self.progressBarLabel.setText(message)

    def OnSignalError(self, message):
        self.ThreadCancelTrigger = None
        self.ActionCancel.setEnabled(False)
        self.ResetProgress()
        # Show/Log message
        log.error(message)
        QMessageBox.critical(self, "An error has been occured", message)
        # Reload current page
        self.web.href(self.web.url(), self.OnCoursePageReloaded, self.OnCourseClicked)

    def OnSignalCanceled(self):
        self.ThreadCancelTrigger = None
        self.ActionCancel.setEnabled(False)
        self.ResetProgress()
        # Reload current page
        self.web.href(self.web.url(), self.OnCoursePageReloaded, self.OnCourseClicked)
        # Inform user
        QMessageBox.warning(self, "Canceled", "Process has been canceled !")

    def OnSignalCoursesDownloaded(self, courseid, coursename):
        self.ThreadCancelTrigger = None
        self.ActionCancel.setEnabled(False)
        self.ResetProgress()
        # Ask user to archive course
        ret = QMessageBox.question(self, 'Finished',
                                   f"Course {coursename} has been downloaded.\nDo you want to archive course ?",
                                   QMessageBox.Yes | QMessageBox.No)
        if ret == QMessageBox.Yes:
            try:
                # Get more information on course:
                body = {
                    "course_id": courseid
                }
                req = Request(const.UDEMY_API_ARCHIVE_COURSE)
                # Build request header
                RequestHeaders = const.RequestHeaders(self.access_token_value)
                for key in RequestHeaders:
                    req.add_header(key, RequestHeaders[key])
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
                self.web.href(self.web.url(), self.OnCoursePageReloaded, self.OnCourseClicked)
        else:
            # Reload current page
            self.web.href(self.web.url(), self.OnCoursePageReloaded, self.OnCourseClicked)

    def OnSignalCoursesCombined(self):
        self.ThreadCancelTrigger = None
        self.ActionCancel.setEnabled(False)
        self.ResetProgress()
        # Reload current page
        self.web.href(self.web.url(), self.OnCoursePageReloaded, self.OnCourseClicked)
        # Inform user
        QMessageBox.warning(self, "Done.", "Video has been combined into one !")

    #
    # Helper functions
    #

    def BlockUI(self, block=True):
        self.web.setDisabled(block)
        if not block:
            self.progressBarLabel.setText(const.PROGRESSBAR_LABEL_DEFAULT)
        else:
            self.progressBarLabel.setText(const.PROGRESSBAR_LABEL_DOWNLOAD)
            self.ApplyBlockStyle()

    def ResetProgress(self):
        self.progressBar.setValue(0)
        self.progressBar.setFormat(const.PROGRESSBAR_LABEL_DEFAULT)
        self.BlockUI(False)

    def SwitchUser(self, clearall, ondonecallback=None):
        self.web.AddCookieFilterCallbackOnURL(const.UDEMY_MAIN_COURSE_OVERVIEW, const.UDEMY_ACCESS_TOKEN_NAME,
                                              self.OnTokenFound)
        self.web.ConnectOnUrlChanged(self.OnURLChanged)
        self.web.ClearCookiesOnURL(const.UDEMY_MAIN_LOGON_URL, ondonecallback, clearall)

    def OnSwitchUserDone(self, html):
        self.close()

    def LoadAll(self):
        script = (
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

    def OnCoursePageReloaded(self, html):
        self.ThreadCancelTrigger = None
        self.ApplyStyleChanges()

    def ApplyStyleChanges(self):
        script = (
            "var sheet = document.createElement('style');\n"
            f"sheet.innerHTML = {const.MAIN_STYLE} ;\n"
            "document.body.appendChild(sheet);"
        )
        log.info(f"Script:\n{script}")
        self.web.RunJavaScript(script)

    def ApplyBlockStyle(self):
        script = (
            "var sheet = document.createElement('style');\n"
            f"sheet.innerHTML = {const.BLOCK_STYLE} ;\n"
            "document.body.appendChild(sheet);"
        )
        log.info(f"Script blockstyle:\n{script}")
        self.web.RunJavaScript(script)

    # Page states
    def OnURLChanged(self, url):
        log.info(f"URL has been changed : '{url}' - apply style changes.")
        if "my-courses" in url.toString():
            self.ApplyStyleChanges()
        elif "login" in url.toString():
            self.BlockUI(False)

    def OnTokenFound(self, TokenName, TokenValue):
        self.access_token_value = TokenValue
        self.access_token = TokenName + "=" + self.access_token_value
        log.info(f"Got access_token : {self.access_token}")
        self.OnActionJump2MyCourses()


if __name__ == '__main__':
    # Activate auto detection of high dpi screens:
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    app = QApplication(sys.argv)
    app.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)
    ex = UDemyWebCrawler()
    sys.exit(app.exec_())
