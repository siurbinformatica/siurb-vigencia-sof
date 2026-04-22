from datetime import date
from config.settings import LOG_PATH
import logging
import os


def get_logger(name: str) -> logging.Logger:

    logger = logging.getLogger(name)
    path_log = os.path.join("/root/SiurbAutoSOF/logs/app.log")

    if logger.handlers:
        return logger
    
    logger.setLevel(logging.DEBUG)

    stream_formatter = logging.Formatter(
        fmt="%(name)s - %(levelname)s - %(message)s",
    )

    file_formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    os.makedirs("/root/SiurbAutoSOF/logs",exist_ok=True)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(stream_formatter)
    stream_handler.setLevel(logging.DEBUG)

    file_handler = logging.FileHandler(path_log)
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.INFO)

    logger.addHandler(stream_handler)
    logger.addHandler(file_handler)

    return logger

def get_logger_save_archive():

    today = date.today().strftime("%Y-%m-%d")
    logger = logging.getLogger("app.archive")
    path_log = os.path.join(LOG_PATH, f"log-archive-{today}.log")

    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False

    file_formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    os.makedirs(LOG_PATH,exist_ok=True)

    file_handler = logging.FileHandler(path_log)
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.INFO)

    logger.addHandler(file_handler)

    return logger
