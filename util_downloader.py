import json, os, re, traceback, m3u8, time, datetime as dt, fastdl, util_logging as log, util_constants as const, util_settings, \
    util_overview as overview, util_uncrypt as encrypt
from typing import Union
from urllib.parse import urlparse, parse_qs
import requests
from PySide2.QtCore import QThread, Signal
from urllib.request import Request, urlopen
from pprint import pformat
from Crypto.Cipher import AES


class DownloaderThread(QThread):
    _signal_progress_parts: Union[Signal, Signal] = Signal(int, int, int, int)
    _signal_progress: Union[Signal, Signal] = Signal(int, int, int, str, str)
    _signal_info: Union[Signal, Signal] = Signal(str)
    _signal_error: Union[Signal, Signal] = Signal(str)
    _signal_done: Union[Signal, Signal] = Signal(int, str)
    _signal_canceled: Union[Signal, Signal] = Signal()

    def __init__(self, mw, courseurl, accesstokenvalue):
        super(DownloaderThread, self).__init__(mw)
        self.canceled = False
        self.course_url = courseurl
        self.access_token_value = accesstokenvalue
        self.LastLectureIdx = -1
        self.LastSegmentIdx = -1
        self.cfg = util_settings.Settings()
        self.overview = overview.Overview(accesstokenvalue)
        self.downloader = Downloader(accesstokenvalue)

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
        return self.CoursePath + os.sep + const.COURSE_CANCELED_STATE_FILE_NAME

    def DeleteCancelFile(self):
        if os.path.exists(self.CanceledFileName()):
            os.remove(self.CanceledFileName())

    def SaveJSON(self, file, data):
        with open(file, 'w') as json_file:
            json.dump(data, json_file)

    def SaveJSONCanceledState(self, data):
        self.SaveJSON(self.CanceledFileName(), data)

    def LoadJSONCanceledState(self):
        data = None
        if os.path.exists(self.CanceledFileName()):
            with open(self.CanceledFileName()) as json_file:
                data = json.load(json_file)
        return data

    def IsCourseProtected(self):
        # Result
        Protected = False
        # Parse url
        parsed_url = urlparse(self.course_url)
        self.CourseId = parse_qs(parsed_url.query)[const.UDEMY_API_FIELD_COURSE_ID][0]
        # Prepare course path
        self.CoursePath = self.PrepareCourseDownload(self.CourseId)
        # Load a list of all lectures of the current course
        LecturesList = self.LoadAllCourseLectures(self.CourseId)
        # Load all chapter videos
        LecturesCount = len(LecturesList)
        for LectureIdx in range(LecturesCount):
            Chapter = LecturesList[LectureIdx]
            if "Lecture_Protected" in Chapter:
                if Chapter["Lecture_Protected"]:
                    Protected = True
                    break
        return Protected

    def run(self):
        try:
            # Parse url
            parsed_url = urlparse(self.course_url)
            self.CourseId = parse_qs(parsed_url.query)[const.UDEMY_API_FIELD_COURSE_ID][0]
            # Prepare course path
            self.CoursePath = self.PrepareCourseDownload(self.CourseId)
            # Prepare playlist
            self.PlaylistFileName = self.CoursePath + os.sep + const.COURSE_PLAYLIST
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
            try:
                if self.LastSegmentIdx == -1:
                    self.ChapterCanceled()
                else:
                    self.SegmentCanceled()
            except Exception as othererror:
                log.error(f"An error has been occured on ChapterCanceled/SegmentCanceled")
                log.error(traceback.format_exc())
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
            self.CurrentLectureIdx = LectureIdx + 1
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
        url = const.UDEMY_API_URL_COURSE_DETAILS.format(CourseId=CourseId)
        log.info(f"Getting course detail information for course with id '{CourseId}'")
        log.info(f" Course url is: '{url}'")
        # Get more information on course:
        req = Request(url, headers=const.RequestHeaders(self.access_token_value))
        res = urlopen(req).read()
        # Convert to json
        CourseInfo = json.loads(res.decode("utf-8"))
        Title = CourseInfo[const.UDEMY_API_FIELD_COURSE_TITLE]
        log.info(f"Title:\n{Title}")
        Description = CourseInfo[const.UDEMY_API_FIELD_COURSE_DESCRIPTION]
        log.info(f"Description:\n{Description}")
        Image = CourseInfo[const.UDEMY_API_FIELD_COURSE_IMAGE]
        log.info(f"Image:\n{Image}")
        # Build course path, prepare preview image and store description
        CoursePath = self.BuildCoursePathInfo(CourseId, Title, Description, Image).replace("\\", "/")
        # Save course JSON info (full)
        log.debug("--- JSON CourseInfo:")
        log.debug(pformat(CourseInfo))
        self.SaveJSON(CoursePath + '/' + const.APP_REST_COURSE_INFO_FILE_NAME, CourseInfo)
        # Return Course path
        return CoursePath

    def BuildCoursePathInfo(self, CourseId, Title, Description, Image):
        log.info(f"Preparing download for course with id '{CourseId}', '{Title}'")
        # Create path
        DownloadPath = self.cfg.DownloadPath
        self.CourseTitle = const.ReplaceSpecialChars(Title)
        CoursePath = DownloadPath + os.sep + self.CourseTitle + f"-#{CourseId}#"
        if not os.path.exists((CoursePath)):
            os.makedirs(CoursePath)
        # Download image
        self.downloader.DownloadFileFast(Image, CoursePath + os.sep + const.COURSE_PREVIEW_IMAGE_NAME)
        # Create description
        desc = open(CoursePath + os.sep + const.COURSE_DESCRIPTION_FILE_NAME, "w", encoding="utf-8")
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
        self.Lecture_Title = ""
        self.Lecture_Index = 0
        self.Lecture_FileName = ""
        self.Lecture_Download_URL = ""
        self.Lecture_Download_TYP = ""
        self.Lecture_Media_License_Token = ""

    def SaveArticle(self, CourseObject):
        if not CourseObject is None:
            Lecture_Title = const.ReplaceSpecialChars(CourseObject["title"])
            Lecture_Index = CourseObject["object_index"]
            Chapter_Title = const.ReplaceSpecialChars(self.Chapter_Title)
            if "asset" in CourseObject:
                asset = CourseObject["asset"]
                if "body" in asset:
                    ArticleFileName = f"{self.Chapter_Index:04d}-{Lecture_Index:04d}-0000__{self.CourseTitle}__{Chapter_Title}__{Lecture_Title}.html"
                    ArticleFileNameFull = self.CoursePath + "/" + ArticleFileName
                    body = CourseObject["asset"]["body"]
                    with open(ArticleFileNameFull, "w", encoding="utf-8") as article:
                        article.write(body)

    def ParseLecture(self, CourseObject):
        self.Lecture_Title = CourseObject["title"]
        self.Lecture_Index = CourseObject["object_index"]
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
                                MediaFound = True
                            elif MediaType in ["application/dash+xml"]:
                                self.Lecture_Download_TYP = "MEDIA"
                                self.Lecture_Download_URL = MediaURL
                                if "media_license_token" in assets:
                                    self.Lecture_Media_License_Token = assets["media_license_token"]
                                MediaFound = True
                            else:
                                log.warn(f"Unknown media type '{MediaType}' with url {MediaURL}")
                        if MediaFound:
                            break
            # Check if url has been found - otherwise log warning
            if self.Lecture_Download_URL == "":
                asset_type = CourseObject["asset"]["asset_type"]
                # If asset type is article only store content in an html file, but don't download any content
                if asset_type in ["Article"]:
                    self.SaveArticle(CourseObject)
                else:
                    errormessage = f"No video url found for '{self.Lecture_FileName}' / {asset_type}"
                    log.error(errormessage)

    def LoadAllCourseLectures(self, CourseId):
        url = const.UDEMY_API_URL_COURSE_CHAPTERS.format(CourseId=CourseId)
        log.info(f"Getting course chapters information for course with id '{CourseId}'")
        log.info(f" Course chapter url is: '{url}'")
        # Get more information on course:
        req = Request(url, headers=const.RequestHeaders(self.access_token_value))
        res = urlopen(req).read()
        # Convert to json
        CourseDetailsJSON = json.loads(res.decode("utf-8"))
        # output readable
        log.debug("--- JSON CourseDetails:")
        log.debug(pformat(CourseDetailsJSON))
        self.SaveJSON(self.CoursePath + '/' + const.APP_REST_COURSE_DETAILS_FILE_NAME, CourseDetailsJSON)
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
                        Lecture_Protected = False
                        if "MEDIA" in self.Lecture_Download_TYP and ".mpd" in self.Lecture_Download_URL:
                            Lecture_Protected = True
                        VideosList.append(
                            {"cnt": cnt,
                             "Chapter_Index": self.Chapter_Index,
                             "Chapter_Title": const.ReplaceSpecialChars(self.Chapter_Title),
                             "Lecture_Index": self.Lecture_Index,
                             "Lecture_Title": const.ReplaceSpecialChars(self.Lecture_Title),
                             "Lecture_FileName": self.Lecture_FileName,
                             "Lecture_Download_URL": self.Lecture_Download_URL,
                             "Lecture_Download_TYP": self.Lecture_Download_TYP,
                             "Lecture_Media_License_Token" : self.Lecture_Media_License_Token,
                             "Lecture_Protected" : Lecture_Protected
                             }
                        )
                else:
                    log.warn(f"Unknown course type '{CourseObjectType}'")
        return VideosList

    def DoDownloadVideo(self, type, url, downloadvideoname):
        log.info(f"Try to download video (type={type}) '{downloadvideoname}' from '{url}' ")
        if not url == "":
            self.downloader.DownloadFileFast(url, self.CoursePath + os.sep + downloadvideoname)
            # Append video to playlist if filetype is video:
            if self.ExtractDownloadExtFromUri(url) in [".mp4", ".mov"]:
                with open(self.PlaylistFileName, "a") as playlist:
                    playlist.write(f"#EXTINF:-1,{downloadvideoname}\n")
                    playlist.write(f"{downloadvideoname}\n")
        else:
            log.info(f"Ignore no downloadable chapter (information only) !")

    def ChapterCanceled(self):
        CanceledInfo = {}
        CanceledInfo.update({"CancelType": const.COURSE_CANCEL_TYPE_CHAPTER})
        CanceledInfo.update({"LectureIdx": self.LastLectureIdx})
        CanceledInfo.update({"SegmentIdx": -1})
        self.SaveJSONCanceledState(CanceledInfo)

    def SegmentCanceled(self):
        CanceledInfo = {}
        CanceledInfo.update({"CancelType": const.COURSE_CANCEL_TYPE_SEGMENT})
        CanceledInfo.update({"LectureIdx": self.LastLectureIdx})
        CanceledInfo.update({"SegmentIdx": self.LastSegmentIdx})
        self.SaveJSONCanceledState(CanceledInfo)

    def IgnoreDownloadFileChapterSectionCauseOfResume(self, cnt, LectureIdx, Chapter_Index, SegmentIdx=-1):
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

    # TODO: Encrypt video parts
    def DownloadVideoPartsBug(self, Lecture_Download_URL, LectureIdx, Chapter, cnt, Chapter_Index, Chapter_Title,
                           Lecture_FileName, Lecture_Download_TYP, Lecture_Index, Lecture_Title):
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
                DownloadVideoName = f"{Chapter_Index:04d}-{Lecture_Index:04d}-{segmentid:04d}__{self.CourseTitle}__{Chapter_Title}__{Lecture_Title}{DownloadVideoFileExt}"
                # Download splitted video part
                if not self.IgnoreDownloadFileChapterSectionCauseOfResume(cnt, LectureIdx, Chapter_Index, segmentid):
                    self.DoDownloadVideo(Lecture_Download_TYP, Lecture_Download_URL, DownloadVideoName)
                if self.ResumeOnLastDownload:
                    self._signal_info.emit(const.PROGRESSBAR_LABEL_DOWNLOAD_RESUME)
                else:
                    self._signal_progress_parts.emit(Chapter_Index, Lecture_Index, segmentid, segmentscount)
                # Store last segment downloaded
                self.LastLectureIdx = self.CurrentLectureIdx
                self.LastSegmentIdx = segmentid
                # User has been canceled ?
                if self.canceled:
                    self.SegmentCanceled()
                    break

    # TODO: Keep currently
    def DownloadVideoPartsBuggy(self, Lecture_Download_URL, LectureIdx, Chapter, cnt, Chapter_Index, Chapter_Title,
                           Lecture_FileName, Lecture_Download_TYP, Lecture_Index, Lecture_Title, Lecture_Media_License_Token):
        ReqHeaders = const.RequestHeaders(self.access_token_value)
        with requests.session() as req:
            # Get m3u8 file list
            m3u8list = m3u8.load(Lecture_Download_URL, headers=ReqHeaders)
            # If playlist contains other playlists with different resolutions get highest
            if m3u8list.is_variant:
                bestresplaylisturl = self.GetPlaylistwithhighestResolution(m3u8list.playlists).uri
                m3u8list = m3u8.load(bestresplaylisturl, headers=ReqHeaders)
            # Get keys
            key_url = m3u8list.keys[0].absolute_uri
            key = []
            # req = Request(url=key_url, headers=ReqHeaders)
            # res = urlopen(req).read()
            # for chunk in res:
            # #for chunk in requests.get(url=key_url, stream=True, headers=ReqHeaders, method="get"):
            #     key.append(chunk)
            # Prepare crypto
            lines = str(m3u8list.segments[0]).split('\n')
            IVAsString = lines[0].split("IV=")[1]
            # convert into bytes and remove the first 2 chars
            IVAsString = IVAsString.replace("0x", "").split(",")[0]
            IV = bytes.fromhex(IVAsString)
            #cipher = AES.new(key[0], AES.MODE_CBC, IV=IV)
            # Init crypto
            cipher = AES.new(Lecture_Media_License_Token, AES.MODE_CBC, IV = IV)
            # Get each segment of m3u8-file
            for single_segment in m3u8list.segments:
                # Get correct URL for ts-file
                download_url = single_segment.absolute_uri
                # Counter 1..n
                num = 1
                # Write bytes into a file
                with open(self.CoursePath + '/Filename.part' + str(num) + '.ts', 'wb') as seg_ts:
                    # Get all chunks of current part-file
                    for chunk in requests.request(url=download_url, stream=True, headers=ReqHeaders, method="get"):
                        # decrypt it and write it into the file
                        seg_ts.write(cipher.decrypt(chunk))
                    # Counter increase for the next part number
                    num += 1

    # TODO: Download encrypted
    def DownloadVideoParts(self, Lecture_Download_URL, LectureIdx, Chapter, cnt, Chapter_Index, Chapter_Title,
                           Lecture_FileName, Lecture_Download_TYP, Lecture_Index, Lecture_Title, Lecture_Media_License_Token):
        # Currently not possible to download crypted video's, so download mpl-file instead until encryption is possible/supported!
        DownloadVideoName = f"{Chapter_Index:04d}-{Lecture_Index:04d}-0000__{self.CourseTitle}__{Chapter_Title}__{Lecture_Title}.mpd"
        # Download splitted video part
        self.DoDownloadVideo(Lecture_Download_TYP, Lecture_Download_URL, DownloadVideoName)
        # Update progress
        self._signal_progress_parts.emit(Chapter_Index, Lecture_Index, 1, 1)

    def DownloadVideoChapter(self, LectureIdx, Chapter):
        cnt = Chapter["cnt"]
        Chapter_Index = Chapter["Chapter_Index"]
        Chapter_Title = const.ReplaceSpecialChars(Chapter["Chapter_Title"])
        Chapter_Title = re.sub('[^0-9a-zA-Z]+', '_', Chapter_Title)
        Lecture_Index = Chapter["Lecture_Index"]
        Lecture_Title = Chapter["Lecture_Title"]
        Lecture_FileName = Chapter["Lecture_FileName"]
        Lecture_Download_URL = Chapter["Lecture_Download_URL"]
        Lecture_Download_TYP = Chapter["Lecture_Download_TYP"]
        Lecture_Media_License_Token = Chapter["Lecture_Media_License_Token"]
        self.ResumeOnLastDownload = False
        # Build name for downloading
        filename, DownloadVideoFileExt = os.path.splitext(Lecture_FileName)
        DownloadVideoName = f"{Chapter_Index:04d}-{Lecture_Index:04d}-0000__{self.CourseTitle}__{Chapter_Title}__{Lecture_Title}{DownloadVideoFileExt}"
        # Download video by type
        if "MEDIA" in Lecture_Download_TYP and ".mpd" in Lecture_Download_URL:
            self.DownloadVideoParts(Lecture_Download_URL, LectureIdx, Chapter, cnt, Chapter_Index, Chapter_Title,
                                    Lecture_FileName, Lecture_Download_TYP, Lecture_Index, Lecture_Title, Lecture_Media_License_Token)
        else:
            if not self.IgnoreDownloadFileChapterSectionCauseOfResume(cnt, LectureIdx, Chapter_Index):
                self.DoDownloadVideo(Lecture_Download_TYP, Lecture_Download_URL, DownloadVideoName)
            if self.ResumeOnLastDownload:
                self._signal_info.emit(const.PROGRESSBAR_LABEL_DOWNLOAD_RESUME)
            else:
                self._signal_progress_parts.emit(Chapter_Index, Lecture_Index, 1, 1)

    def ExtractDownloadExtFromUri(self, Lecture_Download_URL):
        DownloadExt = ""
        if ".ts" in Lecture_Download_URL:
            DownloadExt = ".ts"
        elif ".mp4" in Lecture_Download_URL:
            DownloadExt = ".mp4"
        elif ".mov" in Lecture_Download_URL:
            DownloadExt = ".mov"
        return DownloadExt


class Downloader():
    def __init__(self, accesstokenvalue):
        self.cfg = util_settings.Settings()
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
            log.info(
                f"No need to redownload file '{filename}' cause file exists and file size should not be checked again url and disk !")
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
            # Extract dest filename and path
            DownloadFileName = os.path.basename(filename)
            DownloadFilePath = os.path.dirname(filename)
            log.debug(f"Start downloading '{DownloadFileName}' file with fastdl")
            file_path = fastdl.download(url, fname=DownloadFileName, dir_prefix=DownloadFilePath, force_download=True)
            log.debug(f"Finished downloading file '{DownloadFileName}' to '{DownloadFilePath}' [{file_path}]")
