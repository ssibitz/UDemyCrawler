import os, logging as log, util_constants as const


def InitLogging():
    # Remove old log file on startup
    if os.path.exists(const.APP_LOGFILE_NAME):
        os.remove(const.APP_LOGFILE_NAME)
    log.basicConfig(filename=const.APP_LOGFILE_NAME, encoding='utf-8', level=log.DEBUG,
                    format='%(asctime)s %(levelname)-8s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')


def dolog(msg, type="info"):
    if type == "info":
        log.info(msg)
    elif type == "debug":
        log.debug(msg)
    elif type == "error":
        log.error(msg)
    elif type == "warn":
        log.warning(msg)
    print(msg)  # Also output to console !


def info(msg):
    dolog(msg, "info")


def debug(msg):
    dolog(msg, "debug")


def error(msg):
    dolog(msg, "error")


def warn(msg):
    dolog(msg, "warn")
