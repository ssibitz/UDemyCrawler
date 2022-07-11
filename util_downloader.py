import json
import os
import re
import traceback
import m3u8
import config
import util_logging as log
import time
import datetime as dt
from typing import Union
from urllib.parse import urlparse, parse_qs
from PySide2.QtCore import QThread, Signal
from urllib.request import Request, urlopen
from pprint import pformat

class DownloaderThread(QThread):
    _signal_progress_parts: Union[Signal, Signal] = Signal(int, int, int)
    _signal_progress: Union[Signal, Signal] = Signal(int, int, int, str, str)
    _signal_done: Union[Signal, Signal] = Signal(int, str)
    _signal_error: Union[Signal, Signal] = Signal(str)

    def __init__(self, mw, courseurl, accesstokenvalue):
        super(DownloaderThread, self).__init__(mw)
        self.canceled = False
        self.cfg = config.UserConfig()
        self.course_url = courseurl
        self.access_token_value = accesstokenvalue

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
        self.canceled = True

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
        except Exception as error:
            log.error(f"An error has been occured on Course with url {self.course_url}:")
            log.error(traceback.format_exc())
            self._signal_error.emit(repr(error))
        else:
            # Download has been finished !
            self._signal_done.emit(int(self.CourseId), self.CourseTitle)

    def ProcessCourse(self):
        start = time.time()
        # Get all course chapters
        VideosList = self.LoadAllCourseChapters(self.CourseId)
        # Load all chapter videos
        VideosCount = len(VideosList)
        self._signal_progress.emit(0, 0, VideosCount, self.CourseTitle, "'calculating...'")
        for VideoIdx in range(VideosCount):
            if self.canceled:
                break
            self.DownloadVideoChapter(VideosList[VideoIdx])
            processed = int((VideoIdx + 1) / VideosCount * 100)
            prstime = self.calcProcessTime(start, VideoIdx + 1, VideosCount)
            self._signal_progress.emit(processed, VideoIdx + 1, VideosCount, self.CourseTitle, prstime)

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
        log.info(f"Image:\n{Description}")
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
        self.DownloadCourseVideoAgain(Image, CoursePath + os.sep + config.COURSE_PREVIEW_IMAGE_NAME)
        # Create description
        desc = open(CoursePath + os.sep + config.COURSE_DESCRIPTION_FILE_NAME, "w", encoding="utf-8")
        desc.write(Description)
        desc.close()
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

    def LoadAllCourseChapters(self, CourseId):
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

    def DownloadCourseVideoAgain(self, url, filename):
        # Always download course video again
        if self.cfg.DownloadCourseVideoAgain:
            return True
        # If video does not exists download
        if not os.path.exists(filename):
            return True
        # Check if video exists and in the right download size
        log.info(f"Checking download video '{filename}' again from '{url}' ?")
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

    def DownloadVideoFast(self, url, filename):
        if self.DownloadCourseVideoAgain(url, filename):
            resp = urlopen(url)
            respHtml = resp.read()
            binfile = open(filename, "wb")
            binfile.write(respHtml)
            binfile.close()

    def DoDownloadVideo(self, type, url, downloadvideoname):
        log.info(f"Try to download video (type={type}) '{downloadvideoname}' from '{url}' ")
        if not url == "":
            self.DownloadVideoFast(url, self.CoursePath + os.sep + downloadvideoname)
            # urllib.request.urlretrieve(url, self.CoursePath + os.sep + downloadvideoname)
            # Append video to playlist
            with open(self.PlaylistFileName, "a") as playlist:
                playlist.write(f"#EXTINF:-1,{downloadvideoname}\n")
                playlist.write(f"{downloadvideoname}\n")
        else:
            log.info(f"Ignore no downloadable chapter (information only) !")

    def DownloadVideoChapter(self, Video):
        cnt = Video["cnt"]
        Chapter_Index = Video["Chapter_Index"]
        Chapter_Title = self.ReplaceSpecialChars(Video["Chapter_Title"])
        Chapter_Title = re.sub('[^0-9a-zA-Z]+', '_', Chapter_Title)
        Lecture_FileName = Video["Lecture_FileName"]
        Lecture_Download_URL = Video["Lecture_Download_URL"]
        Lecture_Download_TYP = Video["Lecture_Download_TYP"]
        try:
            DownloadVideoName = f"{cnt:04d}-{Chapter_Index:02d}-{Chapter_Title}-{Lecture_FileName}"
        except Exception as error:
            DownloadVideoName = f"{cnt:04d}-00-{Chapter_Title}-{Lecture_FileName}"
        # Download video by type
        if "MEDIA" in Lecture_Download_TYP:
            if ".mp4" in Lecture_Download_URL:
                self.DoDownloadVideo(Lecture_Download_TYP, Lecture_Download_URL, DownloadVideoName)
            elif ".m3u8" in Lecture_Download_URL:
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
                        if self.canceled:
                            break
                        segmentid = segmentid + 1
                        Lecture_Download_URL = segment.uri
                        DownloadExt = self.ExtractDownloadExtFromUri(Lecture_Download_URL)
                        DownloadVideoNameSplitted = f"{cnt:04d}-{segmentid:04d}-{Chapter_Index:02d}-{Chapter_Title}-{Lecture_FileName}{DownloadExt}"
                        # Download splitted video part
                        self.DoDownloadVideo(Lecture_Download_TYP, Lecture_Download_URL, DownloadVideoNameSplitted)
                        self._signal_progress_parts.emit(Chapter_Index, segmentid, segmentscount)
        else:
            self.DoDownloadVideo(Lecture_Download_TYP, Lecture_Download_URL, DownloadVideoName)

    def ExtractDownloadExtFromUri(self, Lecture_Download_URL):
        DownloadExt = ""
        if ".ts" in Lecture_Download_URL:
            DownloadExt = ".ts"
        elif ".mp4" in Lecture_Download_URL:
            DownloadExt = ".mp4"
        return DownloadExt




