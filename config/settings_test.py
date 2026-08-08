import os


os.environ.setdefault('SECRET_KEY', 'selenium-tests-only-secret-key')
os.environ.setdefault('TELEGRAM_BOT_TOKEN', 'selenium-tests-only-token')
os.environ.setdefault('BASE_URL', 'http://localhost')

from .settings import *  # noqa: F401,F403,E402


DEBUG = True
ROOT_URLCONF = 'config.urls_test'
INSTALLED_APPS = [
    app for app in INSTALLED_APPS
    if app != 'django.contrib.admin'
]
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

