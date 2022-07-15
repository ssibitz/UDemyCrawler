import datetime as dt
import glob
import os
import shlex
import subprocess
import time
import traceback
import util_constants as const
import util_downloader as downloader
import util_logging as log
import util_overview as overview
import util_settings as settings
import zipfile
from typing import Union
from PySide2.QtCore import QThread, Signal, QSortFilterProxyModel
from PySide2.QtGui import QIcon, Qt, QStandardItemModel, QStandardItem
from PySide2.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout, QFormLayout, QLabel, QComboBox, QCompleter, \
    QMessageBox


class ExtendedCombo(QComboBox):
    def __init__(self, parent=None):
        super(ExtendedCombo, self).__init__(parent)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setEditable(True)
        self.completer = QCompleter(self)
        # always show all completions
        self.completer.setCompletionMode(QCompleter.UnfilteredPopupCompletion)
        self.pFilterModel = QSortFilterProxyModel(self)
        self.pFilterModel.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.completer.setPopup(self.view())
        self.setCompleter(self.completer)
        self.lineEdit().textEdited.connect(self.pFilterModel.setFilterFixedString)
        self.completer.activated.connect(self.setTextIfCompleterIsClicked)

    def setModel(self, model):
        super(ExtendedCombo, self).setModel(model)
        self.pFilterModel.setSourceModel(model)
        self.completer.setModel(self.pFilterModel)

    def setModelColumn(self, column):
        self.completer.setCompletionColumn(column)
        self.pFilterModel.setFilterKeyColumn(column)
        super(ExtendedCombo, self).setModelColumn(column)

    def view(self):
        return self.completer.popup()

    def index(self):
        return self.currentIndex()

    def setTextIfCompleterIsClicked(self, text):
        if text:
            index = self.findText(text)
            self.setCurrentIndex(index)

class CourseSelection(QDialog):
    def __init__(self, accesstokenvalue):
        super().__init__()
        self.cfg = settings.Settings()
        self.ffmpeg_util = FFMPEGUtil()
        self.access_token_value = accesstokenvalue
        self.overview = overview.Overview(self.access_token_value)
        self.Selected = None
        self.initUI()

    def initUI(self):
        # Title and icon
        self.setWindowTitle("Combining videos of a course into one single video")
        self.setWindowIcon(QIcon(const.AppIcon()))
        self.setGeometry(100, 100, 600, 50)
        # Save or cancel button
        QBtn = QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        buttonBox = QDialogButtonBox(QBtn)
        buttonBox.button(QDialogButtonBox.Ok).clicked.connect(self.Ok)
        buttonBox.button(QDialogButtonBox.Cancel).clicked.connect(self.Cancel)
        layout = QVBoxLayout()
        formLayout = QFormLayout()
        # List with all available courses
        CoursesLabel = QLabel("Available courses", self)
        # Get a list with all courses
        model = QStandardItemModel()
        model.clear()
        self.CoursesList = self.overview.BuildCourseInfos()
        if self.CoursesList:
            CoursesCount = len(self.CoursesList)
            for CourseIdx in range(CoursesCount):
                # Current course info
                Course = self.CoursesList[CourseIdx]
                item = QStandardItem(Course["Title"])
                model.setItem(CourseIdx, 0, item)
        self.Courses = ExtendedCombo()
        self.Courses.setModel(model)
        self.Courses.setModelColumn(0)
        formLayout.addRow(CoursesLabel, self.Courses)
        # Add to layout
        layout.addLayout(formLayout)
        layout.addWidget(buttonBox)
        self.setLayout(layout)

    def Ok(self):
        selectionId = self.Courses.currentIndex()
        if selectionId >= 0:
            self.Selected = self.CoursesList[selectionId]
            self.accept()
        else:
            QMessageBox.critical(self, "Error occured", "Please select a course from the list!")

    def Cancel(self):
        self.reject()


class FFMPEGUtil():
    def __init__(self):
        pass

    def FFMPEGUtilFullPath(self):
        return const.FFMPEGDownloadPath() + const.FFMPEG_TOOL_PATH

    def FFMPEGUtilFullFilePath(self):
        return self.FFMPEGUtilFullPath() + os.sep + const.FFMPEG_TOOL_FILENAME

    def Available(self):
        if not os.path.exists(const.FFMPEGDownloadPath()):
            return False
        if not os.path.exists(self.FFMPEGUtilFullFilePath()):
            return False
        return True


class FFMPEGDownloadInstallThread(QThread):
    _signal_info: Union[Signal, Signal] = Signal(str)
    _signal_error: Union[Signal, Signal] = Signal(str)
    _signal_done: Union[Signal, Signal] = Signal(str)

    def __init__(self, mw, accesstokenvalue):
        super(FFMPEGDownloadInstallThread, self).__init__(mw)
        self.downloader = downloader.Downloader(accesstokenvalue)
        self.ffmpeg = FFMPEGUtil()

    def run(self):
        try:
            self._signal_info.emit("Checking if FFMPEG already exists")
            # Create ffmpeg download path if not existing
            if not os.path.exists(const.FFMPEGDownloadPath()):
                os.makedirs(const.FFMPEGDownloadPath())
            # Delete old downloaded file to be sure that using always latest version:
            FFMPEGFileNameFull = const.FFMPEGDownloadPath() + os.sep + const.FFMPEG_DOWNLOAD_FILENAME
            if os.path.exists(FFMPEGFileNameFull):
                os.remove(FFMPEGFileNameFull)
            # Download latest version of ffmpeg
            self._signal_info.emit("Downloading latest version of FFMPEG")
            self.downloader.DownloadFileFast(const.FFMPEG_DOWNLOAD_LATEST_VERSION_URL, FFMPEGFileNameFull)
            # Unzip file intoto current directory
            self._signal_info.emit("Unpacking latest version of FFMPEG")
            zip_ref = zipfile.ZipFile(FFMPEGFileNameFull)
            zip_ref.extractall(const.FFMPEGDownloadPath())  # extract file to dir
            zip_ref.close()  # close file
            self._signal_info.emit("FFMPEG is now available !")
        except Exception as error:
            log.error(f"An error has been occured on downloading/installing ffmpeg:")
            log.error(traceback.format_exc())
            # Show error to user
            self._signal_error.emit(repr(error))
        else:
            self._signal_done.emit(self.ffmpeg.FFMPEGUtilFullPath())


class FFMPEGThread(QThread):
    _signal_progress: Union[Signal, Signal] = Signal(int, int, int, str, str)
    _signal_info: Union[Signal, Signal] = Signal(str)
    _signal_error: Union[Signal, Signal] = Signal(str)
    _signal_done: Union[Signal, Signal] = Signal()
    _signal_canceled: Union[Signal, Signal] = Signal()

    def __init__(self, mw, accesstokenvalue, selectedcourse):
        super(FFMPEGThread, self).__init__(mw)
        self.canceled = False
        self.cfg = settings.Settings()
        self.overview = overview.Overview(accesstokenvalue)
        self.ffmpegutil = FFMPEGUtil()
        self.course = selectedcourse

    def calcProcessTime(self, starttime, cur_iter, max_iter):
        telapsed = time.time() - starttime
        testimated = (telapsed / cur_iter) * (max_iter)
        finishtime = starttime + testimated
        finishtime = dt.datetime.fromtimestamp(finishtime).strftime("%H:%M:%S")  # in time
        return finishtime

    def TriggerCancelDownload(self):
        self.canceled = True

    def CombineVideos(self, CourseTitle, CoursePath):
        PlaylistFileNameFFMPEG = CoursePath + "/" + const.FFMPEG_PLAYLIST_NAME
        CourseTitle = const.ReplaceSpecialChars(CourseTitle)
        CombinedFileName = f"0000-0000-0000-{CourseTitle}" + const.COURSE_COMBINE_FILENAME_EXT
        CombinedFileNameFull = CoursePath + "/" + CombinedFileName
        # Continue if already existing and config set to continue if
        if os.path.exists(CombinedFileNameFull) and not self.cfg.DownloadCourseVideoAgain:
            self._signal_info.emit(
                f"No combining because video for course already exists")
            return
        # Scan for all types of videos and build a combine list for ffmpeg:
        os.chdir(CoursePath)
        Videos = []
        for type in const.COURSE_COMPLETE_SCAN_FOR_FILETYPES:
            this_type_files = glob.glob(type)
            Videos += this_type_files
        # Sort list by name
        self._signal_info.emit(f"Sorting videos ...")
        Videos_Sorted = sorted(Videos)
        # Delete old playlist if already exists
        if os.path.exists(PlaylistFileNameFFMPEG):
            os.remove(PlaylistFileNameFFMPEG)
        # Build FFMPEG playlist
        self._signal_info.emit(f"Building playlist.txt of '{CourseTitle}'")
        with open(PlaylistFileNameFFMPEG, "a") as playlist:
            # Append all videos to FFMPEG playlist
            for Video in Videos_Sorted:
                playlist.write(f"file '{Video}'\n")
                if self.canceled:
                    return
        # Execute FFMPEG and concat all files
        VideoCount = len(Videos)
        self._signal_info.emit(
            f"Combining all videos ({VideoCount:04d}) to one - Please wait ...")
        commandlineparams = const.FFMPEG_COMBINE_PARAMS.format(output=CombinedFileName)
        ffmpeg_path = self.ffmpegutil.FFMPEGUtilFullPath()
        ffmpeg_env = os.environ.copy()
        ffmpeg_env["PATH"] = ffmpeg_path + ";" + ffmpeg_env["PATH"]
        cmd = shlex.split(commandlineparams)
        subprocess.call(cmd, env=ffmpeg_env, stdout=subprocess.PIPE, shell=True)
        self._signal_info.emit(f"Combining all videos of course '{CourseTitle}' finished!")

    def run(self):
        # Store original path
        OriginalPath = const.SingletonPath.getInstance().AppPath()
        try:
            # Get infos from course
            CourseTitle = const.ReplaceSpecialChars(self.course["Title"])
            CoursePath = self.course["Path"]
            # Combine videos in course path
            self._signal_info.emit(f"Start combining videos of course '{CourseTitle}' ...")
            self.CombineVideos(CourseTitle, CoursePath)
            # Break if user canceled
            if self.canceled:
                log.warn(f"User has canceled progress !")
        except Exception as error:
            log.error(f"An error has been occured on combining:")
            log.error(traceback.format_exc())
            # Show error to user
            self._signal_error.emit(repr(error))
        else:
            # Download has been finished or canceled:
            if self.canceled:
                self._signal_canceled.emit()
            else:
                self._signal_done.emit()
        # Re-store original path
        os.chdir(OriginalPath)
