# Инструкция по развертыванию проекта
Эта инструкция описывает, как развернуть проект на локальной машине.

---
## 1. Установка зависимостей
### Необходимые программы:
1. **Python 3.8 или выше** (обязательно установить)
2. **Git** (для клонирования репозитория)
3. **Virtualenv** (рекомендуется для создания изолированной среды)
Убедитесь, что все необходимые программы установлены.
---
## 2. Клонирование репозитория
Клонируйте проект с GitHub в локальную директорию:
```bash
git clone https://github.com/<логин>/<название-репозитория>.git
cd <название-репозитория>
```
---
## 3. Настройка виртуального окружения
### Создание и активация виртуального окружения
```bash
python3 -m venv env
```
### Активация виртуального окружения
Для macOS/Linux:
```bash
source env/bin/activate
```
Для Windows:
```bash
env\Scripts\activate
```
---
## 4. Установка зависимостей
Установите все необходимые пакеты:
```bash
pip install -r requirements.txt
```
---
## 5. Настройка файла .env
### Создание файла .env
Создайте файл .env в корневой папке проекта и добавьте в него следующие переменные:
```
SECRET_KEY=ваш-секретный-ключ
DEBUG=True
TELEGRAM_BOT_TOKEN=ваш-ключ-телеграм
HOST=список-ваших-хостов,через-запятую,localhost
CSRF_COOKIE_SECURE=False
SESSION_COOKIE_SECURE=False
SECURE_SSL_REDIRECT=False
CSRF_TRUSTED_ORIGINS=https://ваш-список-доверенных-доменов,https://через-запятую
CORS_ALLOWED_ORIGINS=http://ваш-список-доменов,разрешённых-для-доступаhttps://к-приложению-через-запятую,http://localhost:3000
BASE_URL=https://ваш-базовый-адрес
```
### Генерация SECRET_KEY
Для генерации секретного ключа выполните следующую команду в Python:
```python
from django.core.management.utils import get_random_secret_key
print(get_random_secret_key())
```
Скопируйте результат и вставьте его вместо ваш-секретный-ключ в файле .env.

---
## 6. Настройка базы данных
### Примените миграции для создания таблиц в базе данных:
```bash
python manage.py makemigrations
python manage.py migrate
```
---
## 7. Создание суперпользователя
Создайте суперпользователя для доступа к админ-панели:
```bash
python manage.py createsuperuser
```
---

## 8. Создание ролевой модели
Создайте базовую ролевую модель для приложения:
```bash
python manage.py setup
```
---

## 9. Сбор статики
Соберите все статические файлы в одну папку:
```bash
python manage.py collectstatic
```
---
## 10. Запуск тестового сервера
Запустите встроенный сервер разработки:
```bash
python manage.py runserver 0.0.0.0:3000
```
### Сервер будет доступен по адресу: http://localhost:3000.
---
## 11. Доступ к админ-панели
Перейдите в админ-панель, чтобы управлять проектом:
### http://localhost:3000/admin
Войдите с помощью созданного суперпользователя.


## Восстановление бэкапа
1. Очистить текущую базу данных (DROP всех таблиц):

```
docker exec -it postgres_db psql -U admin -d main
```

Внутри psql выполнить:
```
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
GRANT ALL ON SCHEMA public TO admin;
GRANT ALL ON SCHEMA public TO public;
```
Выйти из psql:
```
\q
```

2. Запустить команду восстановления из бэкапа:
```
docker exec -i postgres_db psql -U admin -d main < ~/postgres_data/backups/db_backup_<актуальная дата файла>.sql
```
