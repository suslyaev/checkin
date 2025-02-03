from django.apps import AppConfig
from django.core.management import call_command
import threading

from telegram_bot.management.commands.services.logging_config import logger


class TelegramBotConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'telegram_bot'
