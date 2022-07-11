import os, logging, config


def InitLogging():
    if os.path.exists(config.APP_LOGFILE_NAME):
        os.remove(config.APP_LOGFILE_NAME)
    logging.basicConfig(filename=config.APP_LOGFILE_NAME, encoding='utf-8', level=logging.INFO, format='%(asctime)s %(levelname)-8s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')


def info(msg):
    logging.info(msg)
    print(msg) # Also output to console !

def debug(msg):
    logging.debug(msg)
    print(msg) # Also output to console !

def error(msg):
    logging.error(msg)
    print(msg)

def warn(msg):
    logging.warning(msg)
    print(msg)
