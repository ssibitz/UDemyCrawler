import datetime as dt, glob, os, shlex, subprocess, time, traceback, zipfile, util_logging as log, \
    util_constants as const, util_downloader as downloader, util_overview as overview, util_settings as settings
from typing import Union
from PySide2.QtCore import QThread, Signal


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

    def __init__(self, mw, accesstokenvalue):
        super(FFMPEGThread, self).__init__(mw)
        self.canceled = False
        self.cfg = settings.Settings()
        self.overview = overview.Overview(accesstokenvalue)
        self.ffmpegutil = FFMPEGUtil()

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
        CombinedFileName = f"0000-0000-0000-{CourseTitle}"+const.COURSE_COMBINE_FILENAME_EXT
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
        try:
            start = time.time()
            # Build a list with all courses by path's in download path
            self._signal_info.emit("Building list of all downloaded courses ...")
            Courses = self.overview.BuildCourseInfos()
            if Courses:
                CoursesCount = len(Courses)
                for CourseIdx in range(CoursesCount):
                    # Current course info
                    Course = Courses[CourseIdx]
                    CourseTitle = Course["Title"]
                    CoursePath = Course["Path"]
                    # Combine videos in course path
                    self._signal_info.emit(f"Start combining videos of course '{CourseTitle}' ...")
                    self.CombineVideos(CourseTitle, CoursePath)
                    # Update processed videos
                    processed = int(CourseIdx / CoursesCount * 100)
                    prstime = self.calcProcessTime(start, CourseIdx + 1, CoursesCount)
                    self._signal_progress.emit(processed, CourseIdx + 1, CoursesCount, CourseTitle, prstime)
                    # Break if user canceled
                    if self.canceled:
                        log.warn(f"User has canceled progress !")
                        break
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
