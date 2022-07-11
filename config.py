import os.path
from os import path

import config
from PySide2.QtCore import QSettings

# User setting names and default values
USR_CONFIG_START_ON_MONITOR = "StartOnMonitorNumber"
USR_CONFIG_START_ON_MONITOR_DEFAULT = 1
USR_CONFIG_DOWNLOAD_PATH = "DownloadPath"
USR_CONFIG_DOWNLOAD_PATH_DEFAULT = "M:\\UDEMY"
USR_CONFIG_DOWNLOAD_COURSE_AGAIN = "DownloadCourseVideoAgain"
USR_CONFIG_DOWNLOAD_COURSE_AGAIN_DEFAULT = False
# Application
APP_NAME = "UDemyCrawler"
APP_TITLE = "UDemy course crawler"
APP_LOGFILE_NAME = f"{APP_NAME}.log"
APP_INIFILE_NAME = f"{APP_NAME}.ini"
APP_ICON_NAME = f"{APP_NAME}.ico"
PROGRESSBAR_LABEL_DEFAULT = "Click on course to download."
PROGRESSBAR_LABEL_DOWNLOAD = "Course will be downloaded. Please wait!"
# Download course details
COURSE_PREVIEW_IMAGE_NAME = "cover.jpg"
COURSE_DESCRIPTION_FILE_NAME = "description.html"
COURSE_PLAYLIST = "playlist.m3u"
# Special chars in chapter, ...
COURSE_NAME_SPECIAL_CHARS_REPLACE =  {
    'ä' : 'ae',
    'Ä' : 'Ae',
    'ö' : 'oe',
    'Ö' : 'Oe',
    'ü' : 'ue',
    'Ü' : 'Ue',
    'ß' : 'ss'
}
#    ".my-courses__course-card-grid>div { min-width: 100% !important; padding-bottom: 3rem !important; } "
#    ".enrolled-course-card--options-menu--37ZJY { z-index: -1000 !important; height: 0 !important; display: none !important; } "
MAIN_STYLE = (
    '"'
    "[data-purpose='tab-nav-buttons'] { z-index: -1000 !important; height: 0 !important; display: none !important; } "
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
# Udemy api calls
UDEMY_API_FIELD_LOCALE = "simple_english_title"
UDEMY_API_FIELD_COURSE_ID = "course_id"
UDEMY_API_FIELD_COURSE_TITLE = "title"
UDEMY_API_FIELD_COURSE_DESCRIPTION = "description"
UDEMY_API_FIELD_COURSE_IMAGE = "image_240x135"
# Udemy login datas
UDEMY_MAIN_URL = "https://www.udemy.com"
UDEMY_MAIN_LOGON_URL = UDEMY_MAIN_URL+"/join/login-popup/?skip_suggest=1&locale=de_DE&response_type=html"
UDEMY_MAIN_COURSE_OVERVIEW = UDEMY_MAIN_URL+"/home/my-courses/"
UDEMY_MAIN_COURSE_REDIRECT = UDEMY_MAIN_URL+"/course-dashboard-redirect/"
UDEMY_API_URL_COURSE_DETAILS = UDEMY_MAIN_URL+"/api-2.0/courses/{CourseId}/"+f"?fields[course]={UDEMY_API_FIELD_COURSE_TITLE},{UDEMY_API_FIELD_COURSE_DESCRIPTION},{UDEMY_API_FIELD_COURSE_IMAGE}&fields[locale]={UDEMY_API_FIELD_LOCALE}"
UDEMY_API_URL_COURSE_CHAPTERS = UDEMY_MAIN_URL+ '/api-2.0/courses/{CourseId}/cached-subscriber-curriculum-items?fields[asset]=results,external_url,time_estimation,download_urls,slide_urls,filename,asset_type,captions,stream_urls,body,media_sources&fields[chapter]=object_index,title,sort_order&fields[lecture]=id,title,object_index,asset,supplementary_assets,view_html&page_size=10000'
UDEMY_API_MY_COURSES = UDEMY_MAIN_URL+ f"/api-2.0/users/me/subscribed-courses/?ordering=-last_accessed&fields[course]={UDEMY_API_FIELD_COURSE_TITLE},{UDEMY_API_FIELD_COURSE_DESCRIPTION},{UDEMY_API_FIELD_COURSE_IMAGE}&is_archived=false&page_size=10000"
UDEMY_API_ARCHIVE_COURSE = UDEMY_MAIN_URL+"/api-2.0/users/me/archived-courses/?fields[course]=archive_time"

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

def AppIcon():
    return path.abspath(path.join(path.dirname(__file__), APP_ICON_NAME))

# Resources inside pyinstaller
def resource_path(relative):
    return os.path.join(
        os.environ.get(
            "_MEIPASS2",
            os.path.abspath(".")
        ),
        relative
    )

# Ini-File
class UserConfig():
    def __init__(self):
        # Set default values
        self.StartOnMonitorNumber = USR_CONFIG_START_ON_MONITOR_DEFAULT
        self.DownloadPath = USR_CONFIG_DOWNLOAD_PATH_DEFAULT
        self.DownloadCourseVideoAgain = USR_CONFIG_DOWNLOAD_COURSE_AGAIN_DEFAULT
        # Init setting
        self.settings = None
        self.InitSettings()
        self.LoadConfigs()

    def InitSettings(self, recreate = False):
        if self.settings is None:
            self.settings = QSettings(APP_INIFILE_NAME, QSettings.IniFormat)
        else:
            if recreate:
                del self.settings
                self.settings = None
                self.InitSettings(False)

    def LoadConfigs(self):
        self.StartOnMonitorNumber = self.settings.value(USR_CONFIG_START_ON_MONITOR, USR_CONFIG_START_ON_MONITOR_DEFAULT)
        self.DownloadPath = self.settings.value(USR_CONFIG_DOWNLOAD_PATH, USR_CONFIG_DOWNLOAD_PATH_DEFAULT)
        self.DownloadCourseVideoAgain = self.valueToBool(self.settings.value(USR_CONFIG_DOWNLOAD_COURSE_AGAIN, USR_CONFIG_DOWNLOAD_COURSE_AGAIN_DEFAULT))

    def SaveConfigs(self):
        self.settings.setValue(USR_CONFIG_START_ON_MONITOR, self.StartOnMonitorNumber)
        self.settings.setValue(USR_CONFIG_DOWNLOAD_PATH, self.DownloadPath)
        self.settings.setValue(USR_CONFIG_DOWNLOAD_COURSE_AGAIN, self.DownloadCourseVideoAgain)
        self.settings.sync()
        self.InitSettings(True)

    @staticmethod
    def valueToBool(value):
        return value.lower() == 'true' if isinstance(value, str) else bool(value)