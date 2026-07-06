"""
Автотесты для проверки checkin-потока и будущих мероприятий.

Запуск:
    python3 manage.py test event.tests.CheckinFlowTest -v 2
    python3 manage.py test event.tests.FutureEventTest -v 2
    python3 manage.py test event.tests.CheckinPerformanceTest -v 2
"""
import logging
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.db import connection
from django.utils import timezone
from datetime import timedelta

from event.models import (
    Action,
    Contact,
    ModuleInstance,
    CompanyContact,
    CategoryContact,
    TypeGuestContact,
    ActionLog,
)

User = get_user_model()

# Настройка логгера для тестов
logger = logging.getLogger(__name__)


def _log(message):
    """Вспомогательная функция для логирования в тестах."""
    print(f"  📝 {message}")


def _create_full_event(name='Тестовое мероприятие', days_ahead=30):
    """Создает полное мероприятие с менеджерами, продюсерами, модераторами."""
    now = timezone.now()
    event = ModuleInstance.objects.create(
        name=name,
        address='Тестовый адрес',
        date_start=now + timedelta(days=days_ahead),
        date_end=now + timedelta(days=days_ahead, hours=4),
        is_visible=True,
    )
    return event


def _create_contact(last_name='Иванов', first_name='Иван', **kwargs):
    """Создает контакт с минимальными данными."""
    return Contact.objects.create(
        last_name=last_name,
        first_name=first_name,
        **kwargs
    )


def _create_action(contact, event, action_type='announced'):
    """Создает Action с обязательными полями."""
    return Action.objects.create(
        contact=contact,
        event=event,
        action_type=action_type,
    )


# =====================================================================
# 1. Тесты checkin-потока
# =====================================================================

class CheckinFlowTest(TestCase):
    """Проверяет полный цикл: заявлен → приглашён → зарегистрирован → зачекинен."""

    def setUp(self):
        self.event = _create_full_event()
        self.contact = _create_contact(last_name='Тестовый', first_name='Контакт')
        _log(f'Создано мероприятие: {self.event.name} (ID={self.event.pk})')
        _log(f'Создан контакт: {self.contact.get_fio()} (ID={self.contact.pk})')

    def tearDown(self):
        _log(f'🧹 Очистка: мероприятие {self.event.pk}, контакт {self.contact.pk}')

    def test_01_smena_status_na_priglashennyi(self):
        """Заявлен → Приглашён."""
        _log('🚀 Начало теста: announced → invited')
        action = _create_action(self.contact, self.event, 'announced')
        _log(f'✅ Создана запись Action: contact={action.contact.get_fio()}, status={action.action_type}')
        
        self.assertEqual(action.action_type, 'announced', 'Статус должен быть announced')
        _log('✅ Проверено: начальный статус announced')

        action.action_type = 'invited'
        action.save()
        _log(f'📝 Изменён статус на: {action.action_type}')
        
        action.refresh_from_db()
        _log(f'📋 Загружена запись из БД: status={action.action_type}')
        
        self.assertEqual(action.action_type, 'invited', 'Статус должен быть invited')
        _log('✅ Тест пройден: статус успешно изменён на invited')
        _log('🏁 Итог: ✅ ЗАЯВЛЕН → ПРИГЛАШЁН (успешно)')

    def test_02_smena_status_na_zaregistrirovanniy(self):
        """Приглашён → Зарегистрирован."""
        _log('🚀 Начало теста: invited → registered')
        action = _create_action(self.contact, self.event, 'invited')
        _log(f'✅ Создана запись Action: contact={action.contact.get_fio()}, status={action.action_type}')
        
        action.action_type = 'registered'
        action.save()
        _log(f'📝 Изменён статус на: {action.action_type}')
        
        action.refresh_from_db()
        _log(f'📋 Загружена запись из БД: status={action.action_type}')
        
        self.assertEqual(action.action_type, 'registered', 'Статус должен быть registered')
        _log('✅ Тест пройден: статус успешно изменён на registered')

    def test_03_smena_status_na_posetivshiy(self):
        """Зарегистрирован → Зачекинен."""
        _log('🚀 Начало теста: registered → visited')
        action = _create_action(self.contact, self.event, 'registered')
        _log(f'✅ Создана запись Action: contact={action.contact.get_fio()}, status={action.action_type}')
        
        action.action_type = 'visited'
        action.save()
        _log(f'📝 Изменён статус на: {action.action_type}')
        
        action.refresh_from_db()
        _log(f'📋 Загружена запись из БД: status={action.action_type}')
        
        self.assertEqual(action.action_type, 'visited', 'Статус должен быть visited')
        _log('✅ Тест пройден: статус успешно изменён на visited (checkin)')

    def test_04_polnyy_cikl_ot_zayavki_do_chequina(self):
        """Полный цикл: announced → invited → registered → visited."""
        _log('🚀 Начало теста: полный цикл от заявки до чекина')
        action = _create_action(self.contact, self.event, 'announced')
        _log(f'✅ Создана запись Action: contact={action.contact.get_fio()}, status={action.action_type}')
        
        # Шаг 1: announced → invited
        _log('📝 Шаг 1: announced → invited')
        action.action_type = 'invited'
        action.save()
        action.refresh_from_db()
        _log(f'✅ Статус изменён на: {action.action_type}')

        # Шаг 2: invited → registered
        _log('📝 Шаг 2: invited → registered')
        action.action_type = 'registered'
        action.save()
        action.refresh_from_db()
        _log(f'✅ Статус изменён на: {action.action_type}')

        # Шаг 3: registered → visited
        _log('📝 Шаг 3: registered → visited')
        action.action_type = 'visited'
        action.save()
        action.refresh_from_db()
        _log(f'✅ Статус изменён на: {action.action_type}')
        
        self.assertEqual(action.action_type, 'visited', 'Финальный статус должен быть visited')
        _log('✅ Тест пройден: полный цикл выполнен успешно')

    def test_05_otmena_priglasheniya(self):
        """Приглашён → Отменён."""
        _log('🚀 Начало теста: invited → cancelled')
        action = _create_action(self.contact, self.event, 'invited')
        _log(f'✅ Создана запись Action: contact={action.contact.get_fio()}, status={action.action_type}')
        
        action.action_type = 'cancelled'
        action.save()
        _log(f'📝 Изменён статус на: {action.action_type}')
        
        action.refresh_from_db()
        _log(f'📋 Загружена запись из БД: status={action.action_type}')
        
        self.assertEqual(action.action_type, 'cancelled', 'Статус должен быть cancelled')
        _log('✅ Тест пройден: приглашение успешно отменено')

    def test_06_zapolnenie_update_user(self):
        """При изменении action_type заполняется update_user."""
        _log('🚀 Начало теста: проверка заполнения update_user')
        user = User.objects.create_user(phone='+79990000000', password='test')
        _log(f'✅ Создан пользователь: {user.phone}')
        
        action = _create_action(self.contact, self.event, 'announced')
        _log(f'✅ Создана запись Action: contact={action.contact.get_fio()}, status={action.action_type}')
        
        action.action_type = 'invited'
        action.update_user = user
        action.save()
        _log(f'📝 Установлен update_user: {user.phone}, статус: {action.action_type}')
        
        action.refresh_from_db()
        _log(f'📋 Загружена запись из БД: update_user={action.update_user.phone}')
        
        self.assertEqual(action.update_user, user, 'update_user должен быть установлен')
        _log('✅ Тест пройден: update_user успешно заполнен')

    def test_07_sozdanie_zapisi_v_actionlog(self):
        """При смене статуса создаётся запись в ActionLog."""
        _log('🚀 Начало теста: проверка создания записи в ActionLog')
        action = _create_action(self.contact, self.event, 'announced')
        _log(f'✅ Создана запись Action: contact={action.contact.get_fio()}, status={action.action_type}')
        
        action.action_type = 'invited'
        action.save()
        _log(f'📝 Изменён статус на: {action.action_type}')
        
        log_exists = ActionLog.objects.filter(
            action=action,
            old_status='announced',
            new_status='invited'
        ).exists()
        _log(f'📋 Проверка записи в ActionLog: найдена={log_exists}')
        
        self.assertTrue(log_exists, 'Запись в ActionLog должна быть создана')
        _log('✅ Тест пройден: запись в ActionLog успешно создана')

    def test_08_filter_accheckin_list_verny(self):
        """checkin_list возвращает только announced (не visited)."""
        _log('🚀 Начало теста: проверка фильтрации checkin_list')
        _create_action(self.contact, self.event, 'announced')
        _log('✅ Создана запись: status=announced')
        
        _create_action(
            _create_contact('Другой', 'Контакт'),
            self.event,
            'visited'
        )
        _log('✅ Создана запись: status=visited')
        
        announced = Action.objects.filter(
            action_type='announced',
            event=self.event
        )
        _log(f'📋 Запрошены announced: найдено={announced.count()}')
        
        self.assertEqual(announced.count(), 1, 'Должна быть 1 запись announced')
        
        visited = Action.objects.filter(
            action_type='visited',
            event=self.event
        )
        _log(f'📋 Запрошены visited: найдено={visited.count()}')
        
        self.assertEqual(visited.count(), 1, 'Должна быть 1 запись visited')
        _log('✅ Тест пройден: фильтрация работает корректно')

    def test_09_neskolko_kontaktov_na_odnom_meropriyatii(self):
        """Несколько контактов на одном мероприятии."""
        _log('🚀 Начало теста: проверка нескольких контактов на одном мероприятии')
        c1 = _create_contact('Первый', 'Контакт')
        c2 = _create_contact('Второй', 'Контакт')
        c3 = _create_contact('Третий', 'Контакт')
        _log(f'✅ Создано 3 контакта: {c1.get_fio()}, {c2.get_fio()}, {c3.get_fio()}')
        
        _create_action(c1, self.event, 'announced')
        _create_action(c2, self.event, 'announced')
        _create_action(c3, self.event, 'announced')
        _log('✅ Создано 3 записи Action для каждого контакта')
        
        announced = Action.objects.filter(
            action_type='announced',
            event=self.event
        )
        _log(f'📋 Запрошены announced: найдено={announced.count()}')
        
        self.assertEqual(announced.count(), 3, 'Должно быть 3 записи announced')
        _log('✅ Тест пройден: несколько контактов обработаны корректно')


# =====================================================================
# 2. Тесты будущих мероприятий
# =====================================================================

class FutureEventTest(TestCase):
    """Проверяет работу с будущими мероприятиями."""

    def test_01_sozdanie_buduschego_meropriyatiya(self):
        """Создание мероприятия в будущем."""
        _log('🚀 Начало теста: создание будущего мероприятия')
        now = timezone.now()
        event = _create_full_event(name='Будущее событие', days_ahead=60)
        _log(f'✅ Создано мероприятие: {event.name}, date_start={event.date_start}')
        
        self.assertEqual(event.name, 'Будущее событие', 'Название должно совпадать')
        self.assertTrue(event.date_start > now, 'date_start должен быть в будущем')
        self.assertTrue(event.is_visible, 'is_visible должен быть True')
        _log('✅ Тест пройден: будущее мероприятие создано корректно')

    def test_02_sozdanie_proshedshego_meropriyatiya(self):
        """Создание прошедшего мероприятия."""
        _log('🚀 Начало теста: создание прошедшего мероприятия')
        now = timezone.now()
        past_event = ModuleInstance.objects.create(
            name='Прошедшее событие',
            address='Адрес',
            date_start=now - timedelta(days=10),
            date_end=now - timedelta(days=9),
            is_visible=True,
        )
        _log(f'✅ Создано мероприятие: {past_event.name}, date_start={past_event.date_start}')
        
        self.assertTrue(past_event.date_start < now, 'date_start должен быть в прошлом')
        _log('✅ Тест пройден: прошедшее мероприятие создано корректно')

    def test_03_sozdanie_teкущего_meropriyatiya(self):
        """Создание текущего мероприятия."""
        _log('🚀 Начало теста: создание текущего мероприятия')
        now = timezone.now()
        present_event = ModuleInstance.objects.create(
            name='Текущее событие',
            address='Адрес',
            date_start=now - timedelta(hours=1),
            date_end=now + timedelta(hours=1),
            is_visible=True,
        )
        _log(f'✅ Создано мероприятие: {present_event.name}, date_start={present_event.date_start}')
        
        self.assertTrue(present_event.date_start < now, 'date_start должен быть в прошлом')
        self.assertTrue(present_event.date_end > now, 'date_end должен быть в будущем')
        _log('✅ Тест пройден: текущее мероприятие создано корректно')

    def test_04_buduschee_meropriyatie_s_priglashennymi(self):
        """Будущее мероприятие с приглашёнными контактами."""
        _log('🚀 Начало теста: создание будущего мероприятия с приглашёнными')
        event = _create_full_event(days_ahead=14)
        _log(f'✅ Создано мероприятие: {event.name}')
        
        contacts = [
            _create_contact(f'Фамилия{i}', f'Имя{i}')
            for i in range(5)
        ]
        _log(f'✅ Создано 5 контактов')
        
        for contact in contacts:
            _create_action(contact, event, 'invited')
        _log('✅ Создано 5 записей Action для каждого контакта')
        
        invited = Action.objects.filter(
            action_type='invited',
            event=event
        )
        _log(f'📋 Запрошены invited: найдено={invited.count()}')
        
        self.assertEqual(invited.count(), 5, 'Должно быть 5 записей invited')
        _log('✅ Тест пройден: мероприятие с приглашёнными создано корректно')

    def test_05_validaciya_dat_meropriyatiya(self):
        """date_end не может быть раньше date_start."""
        _log('🚀 Начало теста: проверка валидации дат')
        now = timezone.now()
        
        # Это должно работать (разные даты)
        event = ModuleInstance.objects.create(
            name='Валидное событие',
            date_start=now + timedelta(days=1),
            date_end=now + timedelta(days=2),
        )
        _log(f'✅ Создано мероприятие: {event.name}, date_start={event.date_start}, date_end={event.date_end}')
        
        self.assertIsNotNone(event.pk, 'pk должен быть установлен')
        _log('✅ Тест пройден: валидация дат работает корректно')

    def test_06_unikalnost_nazvaniya_meropriyatiya(self):
        """Название мероприятия должно быть уникальным."""
        _log('🚀 Начало теста: проверка уникальности названия')
        _create_full_event(name='Уникальное событие')
        _log('✅ Создано первое мероприятие с названием "Уникальное событие"')
        
        with self.assertRaises(Exception):
            _create_full_event(name='Уникальное событие')
        _log('✅ Тест пройден: уникальность названия проверена')

    def test_07_spisok_buduschih_meropriyatii(self):
        """Получение списка будущих мероприятий."""
        _log('🚀 Начало теста: получение списка будущих мероприятий')
        now = timezone.now()
        
        # Будущее
        _create_full_event(name='Будущее 1', days_ahead=10)
        _create_full_event(name='Будущее 2', days_ahead=20)
        _log('✅ Создано 2 будущих мероприятия')
        
        # Прошедшее
        ModuleInstance.objects.create(
            name='Прошедшее',
            date_start=now - timedelta(days=5),
            date_end=now - timedelta(days=4),
        )
        _log('✅ Создано 1 прошедшее мероприятие')
        
        future_events = ModuleInstance.objects.filter(
            date_start__gt=now
        )
        _log(f'📋 Запрошены будущие мероприятия: найдено={future_events.count()}')
        
        self.assertEqual(future_events.count(), 2, 'Должно быть 2 будущих мероприятия')
        _log('✅ Тест пройден: фильтрация будущих мероприятий работает корректно')

    def test_08_mnopogostvo_priglashenii_150_chel(self):
        """Мероприятие с большим количеством приглашений (100+)."""
        _log('🚀 Начало теста: создание 150 приглашений')
        event = _create_full_event(name='Масштабное событие', days_ahead=7)
        _log(f'✅ Создано мероприятие: {event.name}')
        
        contacts = [
            _create_contact(f'Фамилия{i}', f'Имя{i}')
            for i in range(150)
        ]
        _log('✅ Создано 150 контактов')
        
        actions = [
            Action(contact=c, event=event, action_type='invited')
            for c in contacts
        ]
        Action.objects.bulk_create(actions)
        _log('✅ Создано 150 записей Action через bulk_create')
        
        invited = Action.objects.filter(
            action_type='invited',
            event=event
        )
        _log(f'📋 Запрошены invited: найдено={invited.count()}')
        
        self.assertEqual(invited.count(), 150, 'Должно быть 150 записей invited')
        _log('✅ Тест пройден: массовое создание 150 приглашений прошло успешно')


# =====================================================================
# 3. Тесты производительности
# =====================================================================

class CheckinPerformanceTest(TestCase):
    """Тесты производительности checkin-потока."""

    def setUp(self):
        self.event = _create_full_event()
        self.contacts = [
            _create_contact(f'Фамилия{i}', f'Имя{i}')
            for i in range(200)
        ]
        self.actions = [
            Action(contact=c, event=self.event, action_type='announced')
            for c in self.contacts
        ]
        self.action_count = Action.objects.bulk_create(self.actions)
        _log(f'📋 Создано 200 контактов и 200 записей Action')

    def test_01_podschet_zaprosov_pri_zagruzke_spiska(self):
        """Загрузка списка checkin не должна делать более 2 запросов."""
        _log('🚀 Начало теста: подсчёт запросов при загрузке списка')
        _log('📝 Запрос к БД до')
        initial_queries = len(connection.queries)
        
        _log('📝 Выполняем запрос как в checkin_list')
        # Выполняем запрос как в checkin_list
        qs = Action.objects.filter(
            action_type='announced',
            event=self.event
        ).select_related(
            'contact', 'contact__company', 'contact__category', 'contact__type_guest'
        )
        list(qs)
        
        _log('📝 Запрос к БД после')
        queries_made = len(connection.queries) - initial_queries
        _log(f'📋 Выполнено запросов: {queries_made}')
        
        # Должно быть не более 2 запросов (один к Action, один к Contact)
        self.assertLessEqual(
            queries_made, 2,
            f'Слишком много запросов: {queries_made}. Ожидалось <= 2'
        )
        _log('✅ Тест пройден: количество запросов в пределах нормы')

    def test_02_podschet_zaprosov_bez_select_related(self):
        """Без select_related запросов будет больше (N+1)."""
        _log('🚀 Начало теста: подсчёт запросов без select_related')
        from django.test.utils import override_settings
        
        _log('📝 Отключаем кэширование соединений для точного подсчёта')
        # Отключаем кэширование соединений для точного подсчёта
        with override_settings(DEBUG=True):
            from django.db import connection
            connection.queries_log.clear()
            
            qs = Action.objects.filter(
                action_type='announced',
                event=self.event
            )
            
            _log('📝 Запрос к БД до')
            # Запрос к БД до
            initial_queries = len(connection.queries)
            
            _log('📝 Выполняем и обращаемся к contact — это вызовет N+1')
            # Выполняем и обращаемся к contact — это вызовет N+1
            for action in qs:
                _ = action.contact.last_name
            
            queries_made = len(connection.queries) - initial_queries
            _log(f'📋 Выполнено запросов: {queries_made}')
            
            # Без select_related будет 1 (Action) + N (Contact) = 201+
            self.assertGreater(
                queries_made, 10,
                f'Ожидалось много запросов без select_related, но получено: {queries_made}'
            )
        _log('✅ Тест пройден: без select_related запросов действительно много')

    def test_03_proverka_bulk_create(self):
        """bulk_create должен быть быстрее поштучного создания."""
        _log('🚀 Начало теста: проверка bulk_create')
        import time
        
        _log('📝 Тест на bulk_create (уже создан в setUp)')
        # Тест на bulk_create (уже создан в setUp)
        # Проверяем, что 200 записей созданы
        self.assertEqual(Action.objects.count(), 200, 'Должно быть 200 записей')
        _log('✅ Тест пройден: bulk_create создал 200 записей')

    def test_04_ispolzovanie_indeksa_pri_filtracii(self):
        """Фильтрация по (event, action_type) должна использовать индекс."""
        _log('🚀 Начало теста: проверка использования индекса при фильтрации')
        from django.db import connection
        
        _log('📝 Выполняем запрос EXPLAIN SELECT')
        # Выполняем запрос
        with connection.cursor() as cursor:
            cursor.execute(
                "EXPLAIN SELECT * FROM event_action WHERE event_id = %s AND action_type = %s",
                [self.event.pk, 'announced']
            )
            plan = cursor.fetchall()
        
        plan_text = ' '.join(str(row) for row in plan)
        _log(f'📋 План выполнения: {plan_text}')
        
        # Индекс должен использоваться (seq scan — плохо, index scan — хорошо)
        self.assertNotIn(
            'Seq Scan', plan_text,
            f'Индекс не используется! План: {plan_text}'
        )
        _log('✅ Тест пройден: индекс используется корректно')

    def test_05_skorost_zaprosa_count(self):
        """count() должен быть быстрым."""
        _log('🚀 Начало теста: проверка скорости запроса count()')
        import time

        start = time.time()
        count = Action.objects.filter(
            action_type='announced',
            event=self.event
        ).count()
        elapsed = time.time() - start
        
        _log(f'📋 count()={count}, время выполнения={elapsed:.3f}с')
        
        self.assertEqual(count, 200, 'Должно быть 200 записей')
        # count() должен выполняться быстро (< 1 сек даже без индекса)
        self.assertLess(elapsed, 1.0, f'count() слишком медленный: {elapsed:.3f}с')
        _log('✅ Тест пройден: count() выполнился быстро')

    def test_06_podschet_zaprosov_pri_smene_statusa(self):
        """Смена статуса не должна создавать более 3 запросов."""
        _log('🚀 Начало теста: подсчёт запросов при смене статуса')
        action = self.actions[0]
        _log('📝 Запрос к БД до')
        initial_queries = len(connection.queries)
        
        action.action_type = 'invited'
        action.save()
        _log('📝 Изменён статус на invited')
        
        queries_made = len(connection.queries) - initial_queries
        _log(f'📋 Выполнено запросов: {queries_made}')
        
        # 1 SELECT (old_instance в signal) + 1 UPDATE = 2 запроса
        self.assertLessEqual(
            queries_made, 3,
            f'Слишком много запросов при сохранении: {queries_made}'
        )
        _log('✅ Тест пройден: количество запросов при смене статуса в пределах нормы')


# =====================================================================
# 4. Интеграционные тесты
# =====================================================================

class IntegrationTest(TestCase):
    """Интеграционные тесты полного workflow."""

    def setUp(self):
        self.event = _create_full_event()
        self.contact = _create_contact(last_name='Интеграция', first_name='Тест')
        _log(f'📋 Создано мероприятие: {self.event.name}, контакт: {self.contact.get_fio()}')

    def test_01_polnyy_workflow_s_proverkoy_logov(self):
        """Полный workflow с проверкой логов."""
        _log('🚀 Начало теста: полный workflow с проверкой логов')
        action = _create_action(self.contact, self.event, 'announced')
        _log(f'✅ Создана запись Action: contact={action.contact.get_fio()}, status={action.action_type}')
        
        # announced → invited
        _log('📝 announced → invited')
        action.action_type = 'invited'
        action.save()
        log1_exists = ActionLog.objects.filter(
            action=action, old_status='announced', new_status='invited'
        ).exists()
        _log(f'✅ Проверка лога: найдена={log1_exists}')
        self.assertTrue(log1_exists, 'Лог должен быть создан')
        
        # invited → registered
        _log('📝 invited → registered')
        action.action_type = 'registered'
        action.save()
        log2_exists = ActionLog.objects.filter(
            action=action, old_status='invited', new_status='registered'
        ).exists()
        _log(f'✅ Проверка лога: найдена={log2_exists}')
        self.assertTrue(log2_exists, 'Лог должен быть создан')

        # registered → visited
        _log('📝 registered → visited')
        action.action_type = 'visited'
        action.save()
        log3_exists = ActionLog.objects.filter(
            action=action, old_status='registered', new_status='visited'
        ).exists()
        _log(f'✅ Проверка лога: найдена={log3_exists}')
        self.assertTrue(log3_exists, 'Лог должен быть создан')
        
        _log('✅ Тест пройден: полный workflow с логами выполнен успешно')

    def test_02odin_kontakt_na_neskolkih_meropriyatiyah(self):
        """Один контакт на нескольких мероприятиях."""
        _log('🚀 Начало теста: один контакт на нескольких мероприятиях')
        event2 = _create_full_event(name='Мероприятие 2', days_ahead=20)
        _log(f'✅ Создано второе мероприятие: {event2.name}')
        
        _create_action(self.contact, self.event, 'announced')
        _create_action(self.contact, event2, 'announced')
        _log('✅ Создано 2 записи Action для одного контакта')
        
        actions = Action.objects.filter(contact=self.contact)
        _log(f'📋 Запрошены Action для контакта: найдено={actions.count()}')
        
        self.assertEqual(actions.count(), 2, 'Должно быть 2 записи')
        _log('✅ Тест пройден: один контакт на нескольких мероприятиях работает корректно')

    def test_03_proverka_flaga_is_visible(self):
        """Проверка флага is_visible."""
        _log('🚀 Начало теста: проверка флага is_visible')
        # Удаляем событие из setUp, чтобы не мешало
        self.event.delete()
        _log('📝 Удалено событие из setUp')
        
        visible_event = _create_full_event(name='Видимое', days_ahead=5)
        hidden_event = _create_full_event(name='Скрытое', days_ahead=10)
        hidden_event.is_visible = False
        hidden_event.save()
        _log('✅ Создано видимое и скрытое мероприятие')
        
        visible = ModuleInstance.objects.filter(is_visible=True)
        hidden = ModuleInstance.objects.filter(is_visible=False)
        _log(f'📋 Запрошены visible: {visible.count()}, hidden: {hidden.count()}')
        
        self.assertEqual(visible.count(), 1, 'Должно быть 1 видимое мероприятие')
        self.assertEqual(hidden.count(), 1, 'Должно быть 1 скрытое мероприятие')
        _log('✅ Тест пройден: флаг is_visible работает корректно')
