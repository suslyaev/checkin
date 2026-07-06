# 📋 README: Автотесты проекта Attendly

## 📍 Расположение тестов
Файл: `event/tests.py`

## 🚀 Как запустить тесты

### 1. Подключение к серверу
```bash
# Подключитесь через PuTTY к серверу
# Перейдите в папку проекта
cd /home/developer/attendly

# Активируйте виртуальное окружение
source env/bin/activate
```

### 2. Запуск ВСЕХ тестов
```bash
python3 manage.py test event.tests -v 2
```

### 3. Запуск конкретного класса тестов

**Тесты checkin-потока (9 тестов):**
```bash
python3 manage.py test event.tests.CheckinFlowTest -v 2
```

**Тесты будущих мероприятий (8 тестов):**
```bash
python3 manage.py test event.tests.FutureEventTest -v 2
```

**Тесты производительности (6 тестов):**
```bash
python3 manage.py test event.tests.CheckinPerformanceTest -v 2
```

**Интеграционные тесты (3 теста):**
```bash
python3 manage.py test event.tests.IntegrationTest -v 2
```

### 4. Запуск одного конкретного теста
```bash
python3 manage.py test event.tests.CheckinFlowTest.test_01_smena_status_na_priglashennyi -v 2
```

---

## 📖 Описание всех тестов

### 🔵 Класс 1: `CheckinFlowTest` (9 тестов)
**Цель:** Проверить, что правильный статус присваивается при каждом действии.

| Название теста | Ссылка на код | Что делает | Какую проверку проводит |
|---|---|---|---|
| `test_01_smena_status_na_priglashennyi` | [Код](https://github.com/suslyaev/checkin/blob/test/event/tests.py#L84) | Меняет статус с `announced` на `invited`. | Убедится, что объект сохранил новый статус в БД. |
| `test_02_smena_status_na_zaregistrirovanniy` | [Код](https://github.com/suslyaev/checkin/blob/test/event/tests.py#L104) | Меняет статус с `invited` на `registered`. | Убедится, что переход работает корректно. |
| `test_03_smena_status_na_posetivshiy` | [Код](https://github.com/suslyaev/checkin/blob/test/event/tests.py#L120) | Меняет статус с `registered` на `visited`. | Убедится, что финальный статус (чекин) сохраняется. |
| `test_04_polnyy_cikl_ot_zayavki_do_chequina` | [Код](https://github.com/suslyaev/checkin/blob/test/event/tests.py#L136) | Запускает полный цикл: `announced` → `invited` → `registered` → `visited`. | Проверяет всю цепочку действий за один раз. |
| `test_05_otmena_priglasheniya` | [Код](https://github.com/suslyaev/checkin/blob/test/event/tests.py#L166) | Меняет статус с `invited` на `cancelled`. | Проверяет ветку отмены. |
| `test_06_zapolnenie_update_user` | [Код](https://github.com/suslyaev/checkin/blob/test/event/tests.py#L182) | При сохранении указывает `update_user`. | Проверяет, что поле `update_user` заполняется при изменении статуса. |
| `test_07_sozdanie_zapisi_v_actionlog` | [Код](https://github.com/suslyaev/checkin/blob/test/event/tests.py#L202) | Меняет статус и смотрит в таблицу `ActionLog`. | Проверяет, что сигнал (`pre_save`) создал запись в логе аудита. |
| `test_08_filter_accheckin_list_verny` | [Код](https://github.com/suslyaev/checkin/blob/test/event/tests.py#L222) | Создаёт `announced` и `visited` записи для одного события. | Проверяет, что `Action.objects.filter(action_type='announced')` возвращает только нужные. |
| `test_09_neskolko_kontaktov_na_odnom_meropriyatii` | [Код](https://github.com/suslyaev/checkin/blob/test/event/tests.py#L252) | Создаёт 3 разных контакта на одном событии. | Проверяет, что система корректно обрабатывает множественные записи. |

---

### 🟢 Класс 2: `FutureEventTest` (8 тестов)
**Цель:** Проверить работу с будущими мероприятиями, датами и массовыми операциями.

| Название теста | Ссылка на код | Что делает | Какую проверку проводит |
|---|---|---|---|
| `test_01_sozdanie_buduschego_meropriyatiya` | [Код](https://github.com/suslyaev/checkin/blob/test/event/tests.py#L282) | Создаёт событие через 60 дней. | Проверяет, что `date_start` > текущего времени. |
| `test_02_sozdanie_proshedshego_meropriyatiya` | [Код](https://github.com/suslyaev/checkin/blob/test/event/tests.py#L294) | Создаёт событие в прошлом. | Проверяет, что `date_start` < текущего времени. |
| `test_03_sozdanie_teкущего_meropriyatiya` | [Код](https://github.com/suslyaev/checkin/blob/test/event/tests.py#L310) | Создаёт событие, которое идёт прямо сейчас. | Проверяет граничное условие (началось, но не закончилось). |
| `test_04_buduschee_meropriyatie_s_priglashennymi` | [Код](https://github.com/suslyaev/checkin/blob/test/event/tests.py#L327) | Создаёт событие и добавляет 5 контактов. | Проверяет массовое добавление приглашённых. |
| `test_05_validaciya_dat_meropriyatiya` | [Код](https://github.com/suslyaev/checkin/blob/test/event/tests.py#L352) | Пытается создать событие, где `date_end` раньше `date_start`. | Проверяет валидацию дат (хотя в модели её нет, проверяем логику). |
| `test_06_unikalnost_nazvaniya_meropriyatiya` | [Код](https://github.com/suslyaev/checkin/blob/test/event/tests.py#L368) | Создаёт событие с уникальным именем дважды. | Проверяет ограничение `unique=True` на поле `name`. |
| `test_07_spisok_buduschih_meropriyatii` | [Код](https://github.com/suslyaev/checkin/blob/test/event/tests.py#L378) | Создаёт 2 будущих и 1 прошедшее событие. | Проверяет фильтрацию `date_start__gt=now`. |
| `test_08_mnopogostvo_priglashenii_150_chel` | [Код](https://github.com/suslyaev/checkin/blob/test/event/tests.py#L404) | Создаёт 150 приглашений через `bulk_create`. | Проверяет производительность массового добавления. |

---

### 🟡 Класс 3: `CheckinPerformanceTest` (6 тестов)
**Цель:** Доказать, что проблема с тормозами решена. Это самые важные тесты для оптимизации.

| Название теста | Ссылка на код | Что делает | Какую проверку проводит |
|---|---|---|---|
| `test_01_podschet_zaprosov_pri_zagruzke_spiska` | [Код](https://github.com/suslyaev/checkin/blob/test/event/tests.py#L453) | Загружает список из 200 контактов с `select_related`. | **Ключевой тест:** Считает запросы к БД. Их должно быть **≤ 2**. (Раньше было бы 201+). |
| `test_02_podschet_zaprosov_bez_select_related` | [Код](https://github.com/suslyaev/checkin/blob/test/event/tests.py#L480) | Загружает список **без** `select_related`. | **Ключевой тест:** Считает запросы к БД. Их должно быть **> 10**. (Доказывает, что без оптимизации тормоза есть). |
| `test_03_proverka_bulk_create` | [Код](https://github.com/suslyaev/checkin/blob/test/event/tests.py#L515) | Создаёт 200 записей через `bulk_create`. | Проверяет, что запись прошла успешно. |
| `test_04_ispolzovanie_indeksa_pri_filtracii` | [Код](https://github.com/suslyaev/checkin/blob/test/event/tests.py#L526) | Выполняет SQL-запрос `EXPLAIN SELECT...`. | **Ключевой тест:** Смотрит план выполнения запроса. Проверяет, что используется **Index Scan**, а не `Seq Scan` (полный перебор таблицы). |
| `test_05_skorost_zaprosa_count` | [Код](https://github.com/suslyaev/checkin/blob/test/event/tests.py#L550) | Считает количество записей через `.count()`. | Проверяет, что операция выполняется быстро (< 1 сек). |
| `test_06_podschet_zaprosov_pri_smene_statusa` | [Код](https://github.com/suslyaev/checkin/blob/test/event/tests.py#L569) | Меняет статус и считает запросы. | Проверяет, что сигнал аудита не создаёт лишних запросов (должно быть ≤ 3). |

---

### 🟣 Класс 4: `IntegrationTest` (3 теста)
**Цель:** Проверить взаимодействие разных моделей вместе.

| Название теста | Ссылка на код | Что делает | Какую проверку проводит |
|---|---|---|---|
| `test_01_polnyy_workflow_s_proverkoy_logov` | [Код](https://github.com/suslyaev/checkin/blob/test/event/tests.py#L603) | Запускает полный цикл + проверяет логи. | Проверяет, что и статусы, и логи аудита создаются корректно в связке. |
| `test_02_odin_kontakt_na_neskolkih_meropriyatiyah` | [Код](https://github.com/suslyaev/checkin/blob/test/event/tests.py#L641) | Один контакт на двух разных событиях. | Проверяет, что `Action` правильно связывает `Contact` и `Event` (многие-ко-многим). |
| `test_03_proverka_flaga_is_visible` | [Код](https://github.com/suslyaev/checkin/blob/test/event/tests.py#L657) | Создаёт видимое и невидимое событие. | Проверяет, что фильтр `is_visible=True` возвращает только нужные. |

---

## 🔧 Как проверить на другом мероприятии

### Шаг 1: Найдите мероприятие в админке
1. Зайдите в админку: `http://62.113.111.146:8000/admin/event/moduleinstance/`
2. Найдите нужное мероприятие
3. Посмотрите его ID в URL (например, `/change/15/` → ID = 15)

### Шаг 2: Проверьте текущие статусы
```bash
python3 manage.py shell
```

```python
from event.models import ModuleInstance, Action

# Замените 15 на ID вашего мероприятия
event = ModuleInstance.objects.get(pk=15)
print(f"Мероприятие: {event.name}")
print(f"Приглашённых: {Action.objects.filter(event=event, action_type='invited').count()}")
print(f"Подтверждённых: {Action.objects.filter(event=event, action_type='registered').count()}")
print(f"Посетивших: {Action.objects.filter(event=event, action_type='visited').count()}")
```

### Шаг 3: Запустите mass_checkin
```bash
# Сначала проверьте, что будет сделано (без изменений)
python3 manage.py mass_checkin --event "Название мероприятия" --dry-run

# Затем выполните
python3 manage.py mass_checkin --event "Название мероприятия"
```

### Шаг 4: Проверьте результат
```bash
python3 manage.py shell
```

```python
from event.models import ModuleInstance, Action

event = ModuleInstance.objects.get(name="Название мероприятия")
print(f"Приглашённых: {Action.objects.filter(event=event, action_type='invited').count()}")
print(f"Подтверждённых: {Action.objects.filter(event=event, action_type='registered').count()}")
print(f"Посетивших: {Action.objects.filter(event=event, action_type='visited').count()}")
```

### Шаг 5: Запустите автотесты
```bash
# Все тесты
python3 manage.py test event.tests -v 2

# Или только производительность
python3 manage.py test event.tests.CheckinPerformanceTest -v 2
```

---

## 📊 Ожидаемый результат

Если все тесты прошли успешно, вы увидите:
```
Ran 26 tests in 1.255s
OK
```

Если какие-то тесты упали, вы увидите:
```
FAILED (failures=2)
```
И подробный вывод с ошибкой.

---

## ⚠️ Важные замечания

1. **Тесты создают временную базу данных** — они не влияют на реальную базу данных.
2. **После запуска тестов** база данных автоматически удаляется.
3. **Для mass_checkin** всегда сначала делайте `--dry-run`, чтобы убедиться, что всё правильно.
4. **Никогда не мержите ветку `test` в `main`** без предварительного согласования.

---

## 🆘 Решение проблем

### Ошибка: `Command 'mass_checkin' not found`
```bash
git pull
python3 manage.py migrate
```

### Ошибка: `Conflicting migrations detected`
```bash
python3 manage.py makemigrations --merge
python3 manage.py migrate
```

### Ошибка: `ModuleNotFoundError: No module named 'django'`
```bash
source env/bin/activate
```
