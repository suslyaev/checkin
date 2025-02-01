import logging
from loguru import logger


class InterceptHandler(logging.Handler):
    def emit(self, record):
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


# Intercepting log messages from third-party libs (e.g. Telebot) that have level INFO (20) or higher
logging.basicConfig(handlers=[InterceptHandler()], level=20)
logger.add("debug.log", format="{time} {level: <8} [{thread.name: <16}] {message}", level="DEBUG",
           rotation="10 MB",
           compression="zip")
