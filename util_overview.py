import json
import os
import pickle
import re
import traceback
import webbrowser
import util_constants as const
import util_logging as log
import util_settings
from pprint import pformat
from urllib.request import Request, urlopen
from PySide2.QtWidgets import QMessageBox




class Overview():
    def __init__(self, accesstokenvalue):
        self.cfg = util_settings.GlobalSettings()
        self.access_token_value = accesstokenvalue

    def GetTitleFromCourseId(self, CourseId):
        url = const.UDEMY_API_COURSE_TITLE.format(CourseId=CourseId)
        log.info(f"Getting course title for course with id '{CourseId}'")
        log.info(f" Course url is: '{url}'")
        # Get more information on course:
        req = Request(url, headers=const.RequestHeaders(self.access_token_value))
        res = urlopen(req).read()
        # Convert to json
        CourseInfo = json.loads(res.decode("utf-8"))
        log.debug(pformat(CourseInfo))
        Title = CourseInfo[const.UDEMY_API_FIELD_COURSE_TITLE]
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
            "Id": 0,
            "Title": "",
            "Path": ""
        }
        CourseInfoFile = CourseFolder + os.sep + const.COURSE_ID_FILE_NAME
        CourseInfo["Id"] = int(CourseId)
        CourseInfo["Title"] = self.GetTitleFromCourseId(CourseInfo["Id"])
        CourseInfo["Path"] = CourseFolder
        self.GenerateCourseInfoFile(CourseInfoFile, CourseInfo)
        return CourseInfo

    def BuildCourseInfos(self):
        self.cfg.InitSettings(True)
        self.cfg.LoadConfigs()
        CourseFolders = [f.path for f in os.scandir(self.cfg.DownloadPath) if f.is_dir()]
        Courses = []
        for CourseFolder in CourseFolders:
            CourseFolder = CourseFolder.replace("\\", "/")
            # Check if course in in folder exists
            CourseInfo = {
                "Id": 0,
                "Title": "",
                "Path": ""
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
        CoursePathPrepared = CoursePath.replace("\\", "/").replace("#", "%23")
        CoursePathURL = f"file:///{CoursePathPrepared}/"
        CourseImage = f"{CoursePathURL}/{const.COURSE_PREVIEW_IMAGE_NAME}"
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
        overviewfilename = self.cfg.DownloadPath + os.sep + const.COURSE_OVERVIEW_FILE_NAME
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
                HTML = const.HTML_HEADER + HTML + const.HTML_FOOTER
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
