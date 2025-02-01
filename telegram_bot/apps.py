from django.apps import AppConfig
from django.core.management import call_command
import threading

from telegram_bot.management.commands.services.logging_config import logger

class TelegramBotConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'telegram_bot'

    def ready(self):
        if not threading.current_thread().name == 'MainThread':
            return

        try:
            call_command('bot')
        except Exception as e:
            logger.exception(e)
