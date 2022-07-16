import os
import re
from os import path

# User setting names and default values
USR_CONFIG_START_ON_MONITOR = "StartOnMonitorNumber"
USR_CONFIG_START_ON_MONITOR_DEFAULT = -1
USR_CONFIG_DOWNLOAD_PATH = "DownloadPath"
USR_CONFIG_DOWNLOAD_PATH_DEFAULT = ""
USR_CONFIG_TEMP_PATH = "TempPath"
USR_CONFIG_TEMP_PATH_DEFAULT = ""
USR_CONFIG_DOWNLOAD_COURSE_AGAIN = "DownloadCourseVideoAgain"
USR_CONFIG_DOWNLOAD_COURSE_AGAIN_DEFAULT = False
USR_CONFIG_DOWNLOAD_CHECK_FILESIZE = "CheckFileSize"
USR_CONFIG_DOWNLOAD_CHECK_FILESIZE_DEFAULT = False
USR_CONFIG_FFMPEG_PATH = "FFMPEGPath"
USR_CONFIG_FFMPEG_PATH_DEFAULT = ""
USR_CONFIG_STATUSBAR_DEFAULT_LABEL_INSTALLED = "FFMPEG is installed"
USR_CONFIG_STATUSBAR_DEFAULT_LABEL_NOT_FOUND = "FFMPEG path is not set !"

# FFMPEG specific
FFMPEG_DOWNLOAD_FILENAME = "ffmpeg-master-latest-win64-gpl.zip"
FFMPEG_DOWNLOAD_LATEST_VERSION_URL = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
FFMPEG_TOOL_PATH = "\\ffmpeg-master-latest-win64-gpl\\bin"
FFMPEG_TOOL_FILENAME = "ffmpeg.exe"
FFMPEG_PLAYLIST_NAME = "playlist.txt"
COURSE_COMBINE_FILENAME_EXT = ".mp4"
FFMPEG_COMBINE_PARAMS = FFMPEG_TOOL_FILENAME + " -f concat -safe 0 -i " + FFMPEG_PLAYLIST_NAME + " -c copy {output}"

# Application
APP_NAME = "UDemyCrawler"
APP_VERSION = "1.6.0"
APP_TITLE = f"UDemy course crawler V{APP_VERSION} - Copyright(c) 2022 by Stefan Sibitz"
APP_LOGFILE_NAME = f"{APP_NAME}.log"
APP_INIFILE_NAME = f"{APP_NAME}.ini"
APP_ICON_NAME = f"res\\{APP_NAME}.ico"
APP_REST_COURSE_DETAILS_FILE_NAME = f"{APP_NAME}_CourseDetails.json"
APP_REST_COURSE_INFO_FILE_NAME = f"{APP_NAME}_CourseInfo.json"
PROGRESSBAR_LABEL_DEFAULT = "Click on a course to download."
PROGRESSBAR_LABEL_DOWNLOAD = "Course will be downloaded. Please wait!"
PROGRESSBAR_LABEL_DOWNLOAD_PARTS = "Course section {Section_Index:02d}/{Lecture_Index:02d}. will be downloaded: Part {segmentid:04d} of {segmentscount:04d} [{percentdone}%]"
PROGRESSBAR_LABEL_DOWNLOAD_RESUME = "Course download will be continued after canceling/error ..."

# Download course details
COURSE_PREVIEW_IMAGE_NAME = "cover.jpg"
COURSE_DESCRIPTION_FILE_NAME = "description.html"
COURSE_PLAYLIST = "playlist.m3u"
COURSE_ID_FILE_NAME = "courseinfo.pickle"
COURSE_OVERVIEW_FILE_NAME = "index.html"
COURSE_CANCELED_STATE_FILE_NAME = "canceled.json"
COURSE_CANCEL_TYPE_CHAPTER = "Chapter"
COURSE_CANCEL_TYPE_SEGMENT = "Segment"
COURSE_COMPLETE_SCAN_FOR_FILETYPES = ["*.ts", "*.mp4", "*.mov"]
# Special chars in chapter, ...
COURSE_NAME_SPECIAL_CHARS_REPLACE = {
    'ä': 'ae',
    'Ä': 'Ae',
    'ö': 'oe',
    'Ö': 'Oe',
    'ü': 'ue',
    'Ü': 'Ue',
    'ß': 'ss'
}

#    ".my-courses__course-card-grid>div { min-width: 100% !important; padding-bottom: 3rem !important; } "
#    ".enrolled-course-card--options-menu--37ZJY { z-index: -1000 !important; height: 0 !important; display: none !important; } "
#    "[data-purpose='tab-nav-buttons'] { z-index: -1000 !important; height: 0 !important; display: none !important; } "
MAIN_STYLE = (
    '"'
    ".udlite-header { z-index: -1000 !important; height: 0 !important; display: none !important; } "
    "[data-purpose='footer'] { z-index: -1000 !important; height: 0 !important; display: none !important; } "
    ".my-courses__app { padding-top: 10px !important; background: orange !important;"
    '"'
)
BLOCK_STYLE = (
    '"'
    "body { opacity: 0.4 !important; }"
    '"'
)
HTML_HEADER = """
            <!doctype html>
            <html lang=en>
               <head>
                   <meta charset=utf-8>
                   <title>Udemy courses overview</title>
                   <style>
						.myheader {
							padding-top: 10px; 
							padding-bottom: 10px; 
							color: white;
							background: orange;
							text-align: center;
						}
                        .card {
                            position: relative;
                            display: flex;
                            flex-direction: column;
                            word-wrap: break-word;
                            border: 1px solid rgba(0, 0, 0, 0.175);
                            border-radius: 0.375rem;
                            margin-bottom: 10px;
                            width: 100%;
                        }
                        .card-body {
                            flex: 1 1 auto;
                            padding: 0.1rem 0.1rem;
                        }
                        .card-title {
                            margin-top: 0;
                            margin-bottom: 0.1rem;
                        }
                        .card-img-top {
                            border-top-left-radius: 0.375rem;
                        }
                        .card-link {
                            border: 1px solid gray;
                            border-radius: 5px;
                            background-color: lightblue;
                            color: black;
                            text-decoration: none;
                            padding-left: 10px;
                            padding-right: 10px;
                        }                
                        .card-filter {
                            width: 100%;
                            font-size: 16px;
                            padding: 12px 20px 12px 40px;
                            border: 1px solid #ddd;
                            border-radius: 0.375rem;
                            margin-bottom: 12px;
                        }        
                   </style>
                   <script>
                        function doFilter() {
                          // Declare variables
                          var input, filter, cards, i, txtValue;
                          input = document.getElementById('Filter');                        
                          filter = input.value.toUpperCase();
                          cards = document.getElementsByClassName('card')
                          for (i = 0; i < cards.length; i++) {
                            txtValue = cards[i].getAttribute('data-filter');
                            if (txtValue.toUpperCase().indexOf(filter) > -1) {
                              cards[i].style.display = "";
                            } else {
                              cards[i].style.display = "none";
                            }                            
                          }
                        }
                   </script>
               </head>
               <body>
               <h1 class="myheader">Udemy courses overview</h1>
               </hr>
               <input type="text" class="card-filter" id="Filter" onkeyup="doFilter()" placeholder="Search for courses..">
            """
HTML_FOOTER = """
        </body>
    </html>
"""

# Udemy api calls
UDEMY_API_FIELD_LOCALE = "simple_english_title"
UDEMY_API_FIELD_COURSE_ID = "course_id"
UDEMY_API_FIELD_COURSE_TITLE = "title"
UDEMY_API_FIELD_COURSE_DESCRIPTION = "description"
UDEMY_API_FIELD_COURSE_IMAGE = "image_240x135"

# Udemy login datas
UDEMY_MAIN_URL = "https://www.udemy.com"
UDEMY_MAIN_LOGON_URL = UDEMY_MAIN_URL + "/join/login-popup/?skip_suggest=1&locale=de_DE&response_type=html"
UDEMY_MAIN_COURSE_OVERVIEW = UDEMY_MAIN_URL + "/home/my-courses/"
UDEMY_MAIN_COURSE_REDIRECT = UDEMY_MAIN_URL + "/course-dashboard-redirect/"
UDEMY_API_URL_COURSE_DETAILS = UDEMY_MAIN_URL + "/api-2.0/courses/{CourseId}/" + f"?fields[course]={UDEMY_API_FIELD_COURSE_TITLE},{UDEMY_API_FIELD_COURSE_DESCRIPTION},{UDEMY_API_FIELD_COURSE_IMAGE}&fields[locale]={UDEMY_API_FIELD_LOCALE}"
UDEMY_API_URL_COURSE_CHAPTERS = UDEMY_MAIN_URL + '/api-2.0/courses/{CourseId}/cached-subscriber-curriculum-items?fields[asset]=results,external_url,time_estimation,download_urls,slide_urls,filename,asset_type,captions,stream_urls,body,media_sources,media_license_token&fields[chapter]=object_index,title,sort_order&fields[lecture]=id,title,object_index,asset,supplementary_assets,view_html&page_size=10000'
UDEMY_API_MY_COURSES = UDEMY_MAIN_URL + f"/api-2.0/users/me/subscribed-courses/?ordering=-last_accessed&fields[course]={UDEMY_API_FIELD_COURSE_TITLE},{UDEMY_API_FIELD_COURSE_DESCRIPTION},{UDEMY_API_FIELD_COURSE_IMAGE}&is_archived=false&page_size=10000"
UDEMY_API_ARCHIVE_COURSE = UDEMY_MAIN_URL + "/api-2.0/users/me/archived-courses/?fields[course]=archive_time"
UDEMY_API_COURSE_TITLE = UDEMY_MAIN_URL + "/api-2.0/courses/{CourseId}/?fields[course]=title"

# Access token
UDEMY_ACCESS_TOKEN_NAME = "access_token"

# Additional headers to send (User agent, ...)
HEADER_DEFAULT = {
    'Origin': 'www.udemy.com',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:66.0) Gecko/20100101 Firefox/66.0',
    'Referer': 'https://www.udemy.com/join/login-popup/',
    'Accept': 'application/json'
}
HEADER_COOKIE_NAME = "Cookie"
HEADER_COOKIE_ACCESS_TOKEN = "access_token={access_token_value}"


def AppResource(resource):
    return path.abspath(path.join(path.dirname(__file__), resource))


def FontAweSomeIcon(icon, type="solid"):
    return AppResource(f"icons\\svgs\\{type}\\{icon}")


def AppIcon():
    return AppResource(APP_ICON_NAME)


def FFMPEGDownloadPath():
    path = GlobalPaths().AppDataPath() + "/FFMPEG/"
    return path


def RequestHeaders(accesstokenvalue):
    HEADERS = HEADER_DEFAULT
    HEADERS.update({HEADER_COOKIE_NAME: HEADER_COOKIE_ACCESS_TOKEN.format(
        access_token_value=accesstokenvalue)})
    HEADERS.update({'Content-Type': 'application/json; charset=utf-8'})
    return HEADERS


def ReplaceSpecialChars(str):
    for char in COURSE_NAME_SPECIAL_CHARS_REPLACE:
        str = str.replace(char, COURSE_NAME_SPECIAL_CHARS_REPLACE[char])
    str = re.sub('[^0-9a-zA-Z]', '_', str)
    return str



# Start-Path as singleton:
class SingletonPaths:
    __instance = None

    @staticmethod
    def getInstance():
        """ Static access method. """
        if SingletonPaths.__instance == None:
            SingletonPaths()
        return SingletonPaths.__instance

    def __init__(self):
        """ Virtually private constructor. """
        if SingletonPaths.__instance != None:
            raise Exception("This class is a singleton!")
        else:
            SingletonPaths.__instance = self
        # Set application path to APPDATA path. If special path not exists create it:
        self.CurrentAppPath = (os.getenv('APPDATA') + '/' + APP_NAME).replace("\\", "/")
        if not os.path.exists(self.CurrentAppPath):
            os.makedirs(self.CurrentAppPath)

    def AppDataPath(self):
        return self.CurrentAppPath

# Global access paths via singleton function
def GlobalPaths():
    return SingletonPaths.getInstance()