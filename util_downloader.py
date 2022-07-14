import glob
import json
import os
import pickle
import re
import shlex
import subprocess
import traceback
import webbrowser
import m3u8
import config
import util_logging as log
import time
import datetime as dt
import zipfile
from typing import Union
from urllib.parse import urlparse, parse_qs
from PySide2.QtCore import QThread, Signal
from urllib.request import Request, urlopen
from pprint import pformat
from PySide2.QtWidgets import QMessageBox

class DownloaderThread(QThread):
    _signal_progress_parts: Union[Signal, Signal] = Signal(int, int, int)
    _signal_progress: Union[Signal, Signal] = Signal(int, int, int, str, str)
    _signal_progress_resume_download: Union[Signal, Signal] = Signal()
    _signal_error: Union[Signal, Signal] = Signal(str)
    _signal_done: Union[Signal, Signal] = Signal(int, str)
    _signal_canceled: Union[Signal, Signal] = Signal()

    def __init__(self, mw, courseurl, accesstokenvalue):
        super(DownloaderThread, self).__init__(mw)
        self.canceled = False
        self.course_url = courseurl
        self.access_token_value = accesstokenvalue
        self.cfg = config.UserConfig()
        self.overview = Overview(accesstokenvalue)
        self.downloader = Downloader(accesstokenvalue)

    def RequestHeaders(self):
        HEADERS = config.HEADER_DEFAULT
        HEADERS.update({config.HEADER_COOKIE_NAME : config.HEADER_COOKIE_ACCESS_TOKEN.format(access_token_value=self.access_token_value)})
        return HEADERS

    def calcProcessTime(self, starttime, cur_iter, max_iter):
        telapsed = time.time() - starttime
        testimated = (telapsed / cur_iter) * (max_iter)
        finishtime = starttime + testimated
        finishtime = dt.datetime.fromtimestamp(finishtime).strftime("%H:%M:%S")  # in time
        return finishtime

    def TriggerCancelDownload(self):
        self.DeleteCancelFile()
        self.canceled = True

    def CanceledFileName(self):
        return self.CoursePath + os.sep +config.COURSE_CANCELED_STATE_FILE_NAME

    def DeleteCancelFile(self):
        if os.path.exists(self.CanceledFileName()):
            os.remove(self.CanceledFileName())

    def SaveJSONCanceledState(self, data):
        with open(self.CanceledFileName(), 'w') as json_file:
            json.dump(data, json_file)

    def LoadJSONCanceledState(self):
        data = None
        if os.path.exists(self.CanceledFileName()):
            with open(self.CanceledFileName()) as json_file:
                data = json.load(json_file)
        return data

    def run(self):
        try:
            # Parse url
            parsed_url = urlparse(self.course_url)
            self.CourseId = parse_qs(parsed_url.query)[config.UDEMY_API_FIELD_COURSE_ID][0]
            # Prepare course path
            self.CoursePath = self.PrepareCourseDownload(self.CourseId)
            # Prepare playlist
            self.PlaylistFileName = self.CoursePath + os.sep + config.COURSE_PLAYLIST
            if os.path.exists(self.PlaylistFileName):
                os.remove(self.PlaylistFileName)
            with open(self.PlaylistFileName, "a") as playlist:
                playlist.write("#EXTM3U\n")
            # Process all courses
            self.ProcessCourse()
            # Delete file cause no longer needed if not canceled by user
            if not self.canceled:
                if os.path.exists(self.CanceledFileName()):
                    self.DeleteCancelFile()
        except Exception as error:
            log.error(f"An error has been occured on Course with url {self.course_url}:")
            log.error(traceback.format_exc())
            # Try to make an canceled file depending on what has been canceled:
            if self.LastSegmentIdx == -1:
                self.ChapterCanceled()
            else:
                self.SegmentCanceled()
            # Show error to user
            self._signal_error.emit(repr(error))
        else:
            # Download has been finished or canceled:
            if self.canceled:
                self._signal_canceled.emit()
            else:
                self._signal_done.emit(int(self.CourseId), self.CourseTitle)

    def ProcessCourse(self):
        start = time.time()
        # Load canceled file if available to resume:
        self.canceled_file = self.LoadJSONCanceledState()
        # Get all course chapters
        LecturesList = self.LoadAllCourseLectures(self.CourseId)
        # Load all chapter videos
        LecturesCount = len(LecturesList)
        self._signal_progress.emit(0, 0, LecturesCount, self.CourseTitle, "'calculating...'")
        self.LastLectureIdx = -1
        self.LastSegmentIdx = -1
        self.CurrentLectureIdx = -1
        for LectureIdx in range(LecturesCount):
            # Reset last segment index
            self.LastSegmentIdx = -1
            self.CurrentLectureIdx = LectureIdx+1
            # Download chapter
            self.DownloadVideoChapter(self.CurrentLectureIdx, LecturesList[LectureIdx])
            processed = int((self.CurrentLectureIdx) / LecturesCount * 100)
            prstime = self.calcProcessTime(start, self.CurrentLectureIdx, LecturesCount)
            self._signal_progress.emit(processed, self.CurrentLectureIdx, LecturesCount, self.CourseTitle, prstime)
            # Store last processed lecture index
            self.LastLectureIdx = self.CurrentLectureIdx
            # User has been canceled ?
            if self.canceled:
                if not os.path.exists(self.CanceledFileName()):
                    self.ChapterCanceled()
                break

    def PrepareCourseDownload(self, CourseId):
        url = config.UDEMY_API_URL_COURSE_DETAILS.format(CourseId=CourseId)
        log.info(f"Getting course detail information for course with id '{CourseId}'")
        log.info(f" Course url is: '{url}'")
        # Get more information on course:
        req = Request(url, headers=self.RequestHeaders())
        res = urlopen(req).read()
        # Convert to json
        CourseInfo = json.loads(res.decode("utf-8"))
        log.debug(pformat(CourseInfo))
        Title = CourseInfo[config.UDEMY_API_FIELD_COURSE_TITLE]
        log.info(f"Title:\n{Title}")
        Description = CourseInfo[config.UDEMY_API_FIELD_COURSE_DESCRIPTION]
        log.info(f"Description:\n{Description}")
        Image = CourseInfo[config.UDEMY_API_FIELD_COURSE_IMAGE]
        log.info(f"Image:\n{Image}")
        # Build course path, prepare preview image and store description
        return self.BuildCoursePathInfo(CourseId, Title, Description, Image)

    def BuildCoursePathInfo(self, CourseId, Title, Description, Image):
        log.info(f"Preparing download for course with id '{CourseId}', '{Title}'")
        # Create path
        DownloadPath = self.cfg.DownloadPath
        self.CourseTitle = re.sub('[^0-9a-zA-Z]+', '_', Title)
        CoursePath = DownloadPath + os.sep + self.CourseTitle + f"-#{CourseId}#"
        if not os.path.exists((CoursePath)):
            os.makedirs(CoursePath)
        # Download image
        self.downloader.DownloadFileFast(Image, CoursePath + os.sep + config.COURSE_PREVIEW_IMAGE_NAME)
        # Create description
        desc = open(CoursePath + os.sep + config.COURSE_DESCRIPTION_FILE_NAME, "w", encoding="utf-8")
        desc.write(Description)
        desc.close()
        # Build course info file
        self.overview.BuildOrGetCourseInfo(CoursePath, CourseId)
        # Return path created
        return CoursePath

    def GetVideoWithHighestResolution(self, Videos):
        # Default use first video
        if "file" in Videos[0]:
            url = Videos[0]["file"]
        MaxRes = 0
        for Video in Videos:
            if "label" in Video:
                VideoRes = Video["label"]
                if VideoRes.isnumeric():
                    CurrentVideoRes = int(VideoRes)
                    if CurrentVideoRes >= MaxRes:
                        if "file" in Video:
                            MaxRes = CurrentVideoRes
                            url = Video["file"]
        return url

    def GetMediaVideoWithHighestResolution(self, mediasources):
        url = ""
        MaxRes = 0
        for mediasource in mediasources:
            if "type" in mediasource and "src" in mediasource and "label" in mediasource:
                MediaType = mediasource["type"]
                MediaURL = mediasource["src"]
                MediaRes = mediasource["label"]
                if MediaType in ["video/mp4"]:
                    if MediaRes.isnumeric():
                        CurrentVideoRes = int(MediaRes)
                        if CurrentVideoRes >= MaxRes:
                            MaxRes = CurrentVideoRes
                            url = MediaURL
        return url

    def GetPlaylistwithhighestResolution(self, variantplaylist):
        MaxResPlayList = None
        MaxRes = 0
        for playlist in variantplaylist:
            Resolution = playlist.stream_info.resolution
            if not Resolution is None:
                CurrentVideoRes = Resolution[0]
                if CurrentVideoRes >= MaxRes:
                    MaxRes = CurrentVideoRes
                    MaxResPlayList = playlist
            else:
                log.warn(f"Ignoring unknown video resolution")
        return MaxResPlayList

    def InitCurrentChapter(self):
        self.Chapter_Title = ""
        self.Chapter_Index = 0

    def ParseChapter(self, CourseObject):
        self.Chapter_Title = CourseObject["title"]
        self.Chapter_Index = CourseObject["object_index"]

    def InitCurrentLecture(self):
        self.Lecture_FileName = ""
        self.Lecture_Download_URL = ""
        self.Lecture_Download_TYP = ""

    def ParseLecture(self, CourseObject):
        if "asset" in CourseObject:
            assets = CourseObject["asset"]
            if "filename" in assets:
                self.Lecture_FileName = assets["filename"]
            if "download_urls" in assets or "stream_urls" in assets:
                # Search for downloads
                downloads = assets["download_urls"]
                if not downloads is None:
                    if "Video" in downloads:
                        if len(downloads["Video"]) > 0:
                            self.Lecture_Download_TYP = "DOWNLOAD"
                            self.Lecture_Download_URL = self.GetVideoWithHighestResolution(downloads["Video"])
                # Search for streams
                streams = assets["stream_urls"]
                if not streams is None:
                    if "Video" in streams:
                        if len(streams["Video"]) > 0:
                            self.Lecture_Download_TYP = "STREAM"
                            self.Lecture_Download_URL = self.GetVideoWithHighestResolution(streams["Video"])
            # Special case - m3u8 media streams
            if "media_sources" in assets:
                # Search for mediasource
                mediasources = assets["media_sources"]
                if not mediasources is None:
                    MediaFound = False
                    for mediasource in mediasources:
                        if "type" in mediasource and "src" in mediasource:
                            MediaType = mediasource["type"]
                            MediaURL = mediasource["src"]
                            if MediaType in ["video/mp4"]:
                                self.Lecture_Download_TYP = "MEDIA"
                                self.Lecture_Download_URL = self.GetMediaVideoWithHighestResolution(mediasources)
                                MediaFound  = True
                            elif MediaType in ["application/x-mpegURL"]:
                                self.Lecture_Download_TYP = "MEDIA"
                                self.Lecture_Download_URL = MediaURL
                                MediaFound = True
                            elif MediaType in ["application/dash+xml"]: # Types to ignore
                                pass
                            else:
                                log.warn(f"Unknown media type '{MediaType}' with url {MediaURL}")
                        if MediaFound:
                            break
            # Check if url has been found - otherwise log warning
            if self.Lecture_Download_URL == "":
                asset_type = CourseObject["asset"]["asset_type"]
                # Raise an error if type is not in:
                if not asset_type in ["Article"]:
                    errormessage = f"No video url found for '{self.Lecture_FileName}' / {asset_type}"
                    log.error(errormessage)
                    # raise Exception(errormessage)

    def LoadAllCourseLectures(self, CourseId):
        url = config.UDEMY_API_URL_COURSE_CHAPTERS.format(CourseId=CourseId)
        log.info(f"Getting course chapters information for course with id '{CourseId}'")
        log.info(f" Course chapter url is: '{url}'")
        # Get more information on course:
        req = Request(url, headers=self.RequestHeaders())
        res = urlopen(req).read()
        # Convert to json
        CourseDetailsJSON = json.loads(res.decode("utf-8"))
        # output readable
        log.info("--- JSON CourseDetails:")
        log.info(pformat(CourseDetailsJSON))
        # Parse and prepare video list:
        self.InitCurrentChapter()
        self.InitCurrentLecture()
        cnt = 0
        VideosList = []
        if "results" in CourseDetailsJSON:
            for CourseObject in CourseDetailsJSON["results"]:
                CourseObjectType = CourseObject["_class"]
                if "chapter" in CourseObjectType:
                    self.InitCurrentChapter()
                    self.ParseChapter(CourseObject)
                elif "lecture" in CourseObjectType:
                    self.InitCurrentLecture()
                    self.ParseLecture(CourseObject)
                    if not self.Lecture_Download_URL == "":
                        cnt = cnt + 1
                        VideosList.append(
                            {"cnt" : cnt,
                             "Chapter_Index" : self.Chapter_Index,
                             "Chapter_Title" : self.Chapter_Title,
                             "Lecture_FileName" : self.Lecture_FileName,
                             "Lecture_Download_URL" : self.Lecture_Download_URL,
                             "Lecture_Download_TYP" : self.Lecture_Download_TYP
                             }
                        )
                else:
                    log.warn(f"Unknown course type '{CourseObjectType}'")
        return VideosList

    def ReplaceSpecialChars(self, str):
        for char in config.COURSE_NAME_SPECIAL_CHARS_REPLACE:
            str = str.replace(char, config.COURSE_NAME_SPECIAL_CHARS_REPLACE[char])
        return str

    def DoDownloadVideo(self, type, url, downloadvideoname):
        log.info(f"Try to download video (type={type}) '{downloadvideoname}' from '{url}' ")
        if not url == "":
            self.downloader.DownloadFileFast(url, self.CoursePath + os.sep + downloadvideoname)
            # Append video to playlist
            with open(self.PlaylistFileName, "a") as playlist:
                playlist.write(f"#EXTINF:-1,{downloadvideoname}\n")
                playlist.write(f"{downloadvideoname}\n")
        else:
            log.info(f"Ignore no downloadable chapter (information only) !")

    def ChapterCanceled(self):
        CanceledInfo = {}
        CanceledInfo.update({"CancelType": config.COURSE_CANCEL_TYPE_CHAPTER})
        CanceledInfo.update({"LectureIdx": self.LastLectureIdx})
        CanceledInfo.update({"SegmentIdx": -1})
        self.SaveJSONCanceledState(CanceledInfo)

    def SegmentCanceled(self):
        CanceledInfo = {}
        CanceledInfo.update({"CancelType": config.COURSE_CANCEL_TYPE_SEGMENT})
        CanceledInfo.update({"LectureIdx": self.LastLectureIdx})
        CanceledInfo.update({"SegmentIdx": self.LastSegmentIdx})
        self.SaveJSONCanceledState(CanceledInfo)

    def IgnoreDownloadFileChapterSectionCauseOfResume(self, cnt, LectureIdx, Chapter_Index, SegmentIdx = -1):
        Ignore = False
        if not self.canceled_file is None:
            self.ResumeOnLastDownload = True
            CancelType = self.canceled_file["CancelType"]
            CanceledLectureIdx = self.canceled_file["LectureIdx"]
            CanceledSegmentIdx = self.canceled_file["SegmentIdx"]
            if "Chapter" in CancelType:
                if LectureIdx <= CanceledLectureIdx:
                    Ignore = True
                else:
                    self.ResumeOnLastDownload = False
            elif "Segment" in CancelType:
                if LectureIdx < CanceledLectureIdx:
                    Ignore = True
                elif LectureIdx == CanceledLectureIdx and SegmentIdx <= CanceledSegmentIdx:
                    Ignore = True
                else:
                    self.ResumeOnLastDownload = False
        else:
            self.ResumeOnLastDownload = False
        return Ignore
    def DownloadVideoParts(self, Lecture_Download_URL, LectureIdx, Chapter, cnt, Chapter_Index, Chapter_Title, Lecture_FileName, Lecture_Download_TYP):
        # Get m3u8 file list
        m3u8list = m3u8.load(Lecture_Download_URL)
        # If playlist contains other playlists with different resolutions get highest
        if m3u8list.is_variant:
            bestresplaylisturl = self.GetPlaylistwithhighestResolution(m3u8list.playlists).uri
            m3u8list = m3u8.load(bestresplaylisturl)
        # Get all segments and download it:
        segments = m3u8list.segments
        if not segments is None:
            # Download all segments
            segmentscount = len(m3u8list.segments)
            segmentid = 0
            for segment in m3u8list.segments:
                segmentid = segmentid + 1
                Lecture_Download_URL = segment.uri
                DownloadVideoFileExt = self.ExtractDownloadExtFromUri(Lecture_Download_URL)
                DownloadVideoName = f"{self.CurrentLectureIdx:04d}-{segmentid:04d}-{self.CourseTitle}-{Chapter_Title}{DownloadVideoFileExt}"
                # Download splitted video part
                if not self.IgnoreDownloadFileChapterSectionCauseOfResume(cnt, LectureIdx, Chapter_Index, segmentid):
                    self.DoDownloadVideo(Lecture_Download_TYP, Lecture_Download_URL, DownloadVideoName)
                if self.ResumeOnLastDownload:
                    self._signal_progress_resume_download.emit()
                else:
                    self._signal_progress_parts.emit(self.CurrentLectureIdx, segmentid, segmentscount)
                # Store last segment downloaded
                self.LastLectureIdx = self.CurrentLectureIdx
                self.LastSegmentIdx = segmentid
                # User has been canceled ?
                if self.canceled:
                    self.SegmentCanceled()
                    break

    def DownloadVideoChapter(self, LectureIdx, Chapter):
        cnt = Chapter["cnt"]
        Chapter_Index = Chapter["Chapter_Index"]
        Chapter_Title = self.ReplaceSpecialChars(Chapter["Chapter_Title"])
        Chapter_Title = re.sub('[^0-9a-zA-Z]+', '_', Chapter_Title)
        Lecture_FileName = Chapter["Lecture_FileName"]
        Lecture_Download_URL = Chapter["Lecture_Download_URL"]
        Lecture_Download_TYP = Chapter["Lecture_Download_TYP"]
        self.ResumeOnLastDownload = False
        # Build name for downloading
        filename, DownloadVideoFileExt = os.path.splitext(Lecture_FileName)
        DownloadVideoName = f"{self.CurrentLectureIdx:04d}-0000-{self.CourseTitle}-{Chapter_Title}{DownloadVideoFileExt}"
        # Download video by type
        if "MEDIA" in Lecture_Download_TYP and ".m3u8" in Lecture_Download_URL:
            self.DownloadVideoParts(Lecture_Download_URL, LectureIdx, Chapter, cnt, Chapter_Index, Chapter_Title,
                                    Lecture_FileName, Lecture_Download_TYP)
        else:
            if not self.IgnoreDownloadFileChapterSectionCauseOfResume(cnt, LectureIdx, Chapter_Index):
                self.DoDownloadVideo(Lecture_Download_TYP, Lecture_Download_URL, DownloadVideoName)
            if self.ResumeOnLastDownload:
                self._signal_progress_resume_download.emit()
            else:
                self._signal_progress_parts.emit(self.CurrentLectureIdx, 1, 1)

    def ExtractDownloadExtFromUri(self, Lecture_Download_URL):
        DownloadExt = ""
        if ".ts" in Lecture_Download_URL:
            DownloadExt = ".ts"
        elif ".mp4" in Lecture_Download_URL:
            DownloadExt = ".mp4"
        return DownloadExt

class Overview():
    def __init__(self, accesstokenvalue):
        self.cfg = config.UserConfig()
        self.access_token_value = accesstokenvalue

    def RequestHeaders(self):
        HEADERS = config.HEADER_DEFAULT
        HEADERS.update({config.HEADER_COOKIE_NAME : config.HEADER_COOKIE_ACCESS_TOKEN.format(access_token_value=self.access_token_value)})
        return HEADERS

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

    def BuildOrGetCourseInfo(self, CourseFolder, CourseId):
        CourseInfo = {
            "Id" : 0,
            "Title" : "",
            "Path" : ""
        }
        CourseInfoFile = CourseFolder + os.sep + config.COURSE_ID_FILE_NAME
        if os.path.exists(CourseInfoFile):
            CourseInfo = self.LoadCourseInfoFile(CourseInfoFile)
        else:
            CourseInfo["Id"] = int(CourseId)
            CourseInfo["Title"] = self.GetTitleFromCourseId(CourseInfo["Id"])
            CourseInfo["Path"] = CourseFolder
            self.GenerateCourseInfoFile(CourseInfoFile, CourseInfo)
        return CourseInfo

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
            # Get course id from hashtag in pathname:
            try:
                CourseId = re.findall(r'#(.+?)#', CourseFolder)[0]
                CourseInfo = self.BuildOrGetCourseInfo(CourseFolder, CourseId)
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
            ret = QMessageBox.question(None, 'Finished',
                                       f"Overview has been generated.\nDo you want to view it ?",
                                       QMessageBox.Yes | QMessageBox.No)
            if not ret == QMessageBox.Yes:
                openit = False
        if openit:
            overviewfilename = overviewfilename.replace("\\", "/")
            OverviewFile = f"file:///{overviewfilename}"
            webbrowser.open(OverviewFile, new=0, autoraise=True)

class Downloader():
    def __init__(self, accesstokenvalue):
        self.cfg = config.UserConfig()
        self.access_token_value = accesstokenvalue

    def DownloadFileAgainFromURL(self, url, filename):
        # Always download course video again
        if self.cfg.DownloadCourseVideoAgain:
            return True
        filename = filename.replace("\\", "/")
        # If video does not exists download
        if not os.path.exists(filename):
            return True
        # File exists but no need to check file size activated
        if not self.cfg.DownloadCourseVideoCheckFileSize:
            log.info(f"No need to redownload file '{filename}' cause file exists and file size should not be checked again url and disk !")
            return False
        # Check if video exists and in the right download size
        log.info(f"Checking filesize of downloaded '{filename}' again from '{url}' ?")
        contentlen = -1
        try:
            obj_info = urlopen(url)
            contentlen = int(obj_info.getheader('Content-Length'))
            log.info(f"FileSize of video from url content disk is: {contentlen}")
        except Exception as error:
            contentlen = -1
            log.error(f"Can not get content length of file from url '{url}'")
            log.error(traceback.format_exc())
        # Re-download if content length not found
        if contentlen == -1:
            return True
        #
        filelen = -1
        try:
            filelen = os.stat(filename).st_size
            log.info(f"FileSize of video on disk is: {filelen}")
        except Exception as error:
            filelen = -1
            log.error(f"Can not get file length of file '{filename}'")
            log.error(traceback.format_exc())
        # Re-download if file length not found
        if filelen == -1:
            return True
        # Check if sizes identically
        if filelen == contentlen:
            log.info(f"No need to redownload file '{filename}' because identical !")
            return False
        else:
            return True

    def DownloadFileFast(self, url, filename):
        if self.DownloadFileAgainFromURL(url, filename):
            resp = urlopen(url)
            respHtml = resp.read()
            binfile = open(filename, "wb")
            binfile.write(respHtml)
            binfile.close()

class FFMPEGUtil():
    def __init__(self, accesstokenvalue):
        self.cfg = config.UserConfig()
        self.downloader = Downloader(accesstokenvalue)

    def FFMPEGUtilFullPath(self):
        return config.FFMPEGDownloadPath()+os.sep+config.FFMPEG_TOOL_PATH

    def FFMPEGUtilFullFilePath(self):
        return self.FFMPEGUtilFullPath()+os.sep+config.FFMPEG_TOOL_FILENAME

    def Available(self):
        if not os.path.exists(config.FFMPEGDownloadPath()):
            return False
        if os.path.exists(self.FFMPEGUtilFullFilePath()):
            return False
        return True

    def DownloadAndInstall(self):
        # Create ffmpeg download path if not existing
        if not os.path.exists(config.FFMPEGDownloadPath()):
            os.makedirs(config.FFMPEGDownloadPath())
        # Delete old downloaded file to be sure that using always latest version:
        FFMPEGFileNameFull = config.FFMPEGDownloadPath()+os.sep+config.FFMPEG_DOWNLOAD_FILENAME
        if os.path.exists(FFMPEGFileNameFull):
            os.remove(FFMPEGFileNameFull)
        # Download latest version of ffmpeg
        self.downloader.DownloadFileFast(config.FFMPEG_DOWNLOAD_LATEST_VERSION_URL, FFMPEGFileNameFull)
        # Unzip file intoto current directory
        zip_ref = zipfile.ZipFile(FFMPEGFileNameFull)
        zip_ref.extractall(config.FFMPEGDownloadPath()) # extract file to dir
        zip_ref.close() # close file

class FFMPEGThread(QThread):
    _signal_progress: Union[Signal, Signal] = Signal(int, int, int, str, str)
    _signal_info: Union[Signal, Signal] = Signal(str)
    _signal_error: Union[Signal, Signal] = Signal(str)
    _signal_done: Union[Signal, Signal] = Signal()
    _signal_canceled: Union[Signal, Signal] = Signal()

    def __init__(self, mw, accesstokenvalue):
        super(FFMPEGThread, self).__init__(mw)
        self.canceled = False
        self.access_token_value = accesstokenvalue
        self.cfg = config.UserConfig()
        self.overview = Overview(accesstokenvalue)
        self.ffmpegutil = FFMPEGUtil(accesstokenvalue)

    def calcProcessTime(self, starttime, cur_iter, max_iter):
        telapsed = time.time() - starttime
        testimated = (telapsed / cur_iter) * (max_iter)
        finishtime = starttime + testimated
        finishtime = dt.datetime.fromtimestamp(finishtime).strftime("%H:%M:%S")  # in time
        return finishtime

    def TriggerCancelDownload(self):
        self.canceled = True

    def CombineVideos(self, CourseTitle, CoursePath):
        CoursePath = CoursePath.replace("\\", "/")
        PlaylistFileNameFFMPEG = CoursePath + os.sep + config.FFMPEG_PLAYLIST_NAME
        CombinedFileName = CourseTitle + config.COURSE_COMBINE_FILENAME_EXT
        # Continue if already existing and config set to continue if
        if os.path.exists(CoursePath + os.sep + CombinedFileName) and not self.cfg.DownloadCourseVideoAgain:
            self._signal_info.emit(f"Ignore combining of video for course {CourseTitle} cause of already existing video file")
            return
        # Scan for all types of videos and build a combine list for ffmpeg:
        os.chdir(CoursePath)
        Videos = []
        for type in config.COURSE_COMPLETE_SCAN_FOR_FILETYPES:
            this_type_files = glob.glob(type)
            Videos += this_type_files
        # Build FFMPEG playlist
        self._signal_info.emit(f"Build list with all videos of course '{CourseTitle}'")
        for Video in Videos:
            # Append all videos to FFMPEG playlist
            with open(CoursePath + os.sep + PlaylistFileNameFFMPEG, "a") as playlist:
                playlist.write(f"file '{Video}'\n")
        # Execute FFMPEG and concat all files
        VideoCount = len(Videos)
        self._signal_info.emit(f"Combining all videos of course '{CourseTitle}' containing {VideoCount:04d} videos - Please wait ...")
        commandlineparams = config.FFMPEG_COMBINE_PARAMS.format(output=CombinedFileName)
        ffmpeg_env = os.environ.copy()
        ffmpeg_env["PATH"] = self.ffmpegutil.FFMPEGUtilFullPath() + ffmpeg_env["PATH"]
        cmd = shlex.split(commandlineparams)
        subprocess.call(cmd, env=ffmpeg_env)
        self._signal_info.emit(f"Combining all videos of course '{CourseTitle}' finished!")

    def run(self):
        try:
            start = time.time()
            # Install latest FFMPEG util if not available
            self._signal_info.emit("Checking if FFMPEG util ist installed ...")
            if not self.ffmpegutil.Available:
                self.ffmpegutil.DownloadAndInstall()
                self._signal_info.emit("FFMPEG was installed sucessfully !")
            else:
                self._signal_info.emit("FFMPEG is installed and ready.")
            # Load courses
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
                    prstime = self.calcProcessTime(start, CourseIdx+1, CoursesCount)
                    self._signal_progress.emit(processed, CourseIdx+1, CoursesCount, CourseTitle, prstime)
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