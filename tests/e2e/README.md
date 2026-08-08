# UI-автотесты

UI-тесты запускаются только для постоянного окружения `testAnis`:

```text
http://62.113.111.146:8001
```

Защита в тестах запрещает запуск на другом сервере или порту. Тесты через UI
создают события, контакты и регистрации в постоянной базе `testAnis`.
Созданные записи после завершения тестов не удаляются.

Новые записи получают последовательные имена:

```text
Selenium Event 0001
Selenium Event 0002
Selenium Guest 0001
Selenium Guest 0002
```

Старые записи не изменяются. Тест находит максимальный существующий номер и
использует следующий. Запускайте тесты последовательно, без `pytest-xdist`,
чтобы два теста не выбрали одинаковый номер.

## Подготовка учётных данных

В текущем окне PowerShell укажите телефон суперпользователя `testAnis`:

```powershell
$env:E2E_PHONE="+79879631518"
```

Введите пароль скрыто. Пароль не добавляется в Git и не сохраняется в README:

```powershell
$secure = Read-Host -Prompt "Password" -AsSecureString
$env:E2E_PASSWORD = [Net.NetworkCredential]::new("", $secure).Password
```

## Запуск всех тестов

Запуск без отображения браузера:

```powershell
$env:E2E_HEADLESS="1"
$env:E2E_SLOWMO="0"
python -m pytest tests\e2e -v
```

Запуск с видимым браузером и паузой две секунды между поддерживаемыми
действиями:

```powershell
$env:E2E_HEADLESS="0"
$env:E2E_SLOWMO="2"
python -m pytest tests\e2e -v
```

Значение `E2E_SLOWMO` задаёт длительность учебной паузы в секундах. Для
обычного быстрого запуска используйте `0`.

## Запуск отдельных сценариев

Создание события через Django Admin:

```powershell
python -m pytest tests\e2e\test_event.py -v
```

Поиск гостя в созданном событии:

```powershell
python -m pytest tests\e2e\test_checkin.py::test_checker_can_find_guest_by_last_name -v
```

Подтверждение check-in гостя:

```powershell
python -m pytest tests\e2e\test_checkin.py::test_checker_can_confirm_guest -v
```

Проверка успешного входа:

```powershell
python -m pytest tests\e2e\test_auth.py::test_user_can_log_in -v
```

## Завершение работы

После тестов удалите логин и пароль из текущей сессии PowerShell:

```powershell
Remove-Item Env:E2E_PHONE -ErrorAction SilentlyContinue
Remove-Item Env:E2E_PASSWORD -ErrorAction SilentlyContinue
```

Сообщения Chrome про GPU, USB или GCM обычно не связаны с результатом теста.
Ориентируйтесь на итоговый статус pytest: `PASSED`, `FAILED` или `ERROR`.
