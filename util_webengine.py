import util_logging as log, util_constants as const
from PySide2.QtCore import QObject, QUrl
from PySide2.QtNetwork import QNetworkCookie
from PySide2.QtWebEngineWidgets import QWebEnginePage, QWebEngineProfile, QWebEngineView


# Web page with logging included
class WebEnginePage(QWebEnginePage):
    def __init__(self, profile: QWebEngineProfile, parent: QObject = None, onclickfct=None):
        QWebEnginePage.__init__(self, profile, parent)
        self.OnLinkClickCallback = onclickfct

    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        log.info(f"[JavaScript console message]:\n{level} : {sourceID}\n{lineNumber} : {message}")

    def acceptNavigationRequest(self, url, navtype, mainframe):
        if navtype == QWebEnginePage.NavigationTypeLinkClicked:
            fullUrl = url.toString()
            if const.UDEMY_MAIN_COURSE_REDIRECT in fullUrl:
                if not self.OnLinkClickCallback is None:
                    self.OnLinkClickCallback(fullUrl)
                return False
        return super(WebEnginePage, self).acceptNavigationRequest(url, navtype, mainframe)


# Web view with advanced features
class QWebEngineViewPlus(QWebEngineView):
    def __init__(self):
        QWebEngineView.__init__(self)

    def RunJavaScript(self, script, callback=None):
        if callback is None:
            self.page().runJavaScript(script)
        else:
            self.page().runJavaScript(script, 0, callback)

    def ConnectOnLoadFinished(self, fct):
        self.loadFinished.connect(fct)

    def ConnectOnUrlChanged(self, fct):
        self.urlChanged.connect(fct)

    def DisconnectOnUrlChanged(self):
        self.urlChanged.disconnect()

    def ConnectOnLoadFinishedRecall(self, fct):
        self.fctLoaded = fct
        self.ConnectOnLoadFinished(self.OnLoadFinishedRecall)

    def OnLoadFinishedRecall(self):
        if self.fctLoaded:
            self.page().toHtml(self.fctLoaded)
            self.fctLoaded = None

    def href(self, url, recall=None, onclick=None):
        profile = QWebEngineProfile.defaultProfile()
        webpage = WebEnginePage(profile, self, onclick)
        self.setPage(webpage)
        self.load(QUrl(url))
        if recall is not None:
            self.ConnectOnLoadFinishedRecall(recall)

    def ClearCookiesOnURL(self, url, fct, clearall):
        log.info(f"Clearing {clearall} all cookies on url {url}")
        if clearall:
            profile = QWebEngineProfile.defaultProfile()
            profile.clearHttpCache()
            cookie_store = profile.cookieStore()
            cookie_store.deleteAllCookies()
        self.href(url, fct, None)

    def AddCookieFilterCallbackOnURL(self, url, filter, callbackfct):
        log.info(f"Adding cookie filter on url '{url}' and wait until cookie '{filter}' has been found.")
        self.CookieFound = False
        self.CookieFilter = filter
        self.CookieFilterCallback = callbackfct
        profile = QWebEngineProfile.defaultProfile()
        cookie_store = profile.cookieStore()
        cookie_store.cookieAdded.connect(self.onCookieAdded)
        self.href(url)

    def onCookieAdded(self, cookie):
        if self.CookieFound:
            return
        c = QNetworkCookie(cookie)
        CookieNam = bytearray(c.name()).decode()
        CookieVal = bytearray(c.value()).decode()
        if self.CookieFilter in CookieNam:
            log.info(f"Cookie '{self.CookieFilter}' has been found! Turning off filter.")
            self.CookieFound = True
            profile = QWebEngineProfile.defaultProfile()
            cookie_store = profile.cookieStore()
            cookie_store.cookieAdded.disconnect()
            if self.CookieFilterCallback:
                self.CookieFilterCallback(CookieNam, CookieVal)
