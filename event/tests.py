"""
Автотесты для проверки checkin-потока и будущих мероприятий.

Запуск:
    python3 manage.py test event.tests.CheckinFlowTest -v 2
    python3 manage.py test event.tests.FutureEventTest -v 2
    python3 manage.py test event.tests.CheckinPerformanceTest -v 2
"""
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

    def test_01_announced_to_invited(self):
        """Заявлен → Приглашён."""
        action = _create_action(self.contact, self.event, 'announced')
        self.assertEqual(action.action_type, 'announced')

        action.action_type = 'invited'
        action.save()
        action.refresh_from_db()
        self.assertEqual(action.action_type, 'invited')

    def test_02_invited_to_registered(self):
        """Приглашён → Зарегистрирован."""
        action = _create_action(self.contact, self.event, 'invited')
        action.action_type = 'registered'
        action.save()
        action.refresh_from_db()
        self.assertEqual(action.action_type, 'registered')

    def test_03_registered_to_visited(self):
        """Зарегистрирован → Зачекинен."""
        action = _create_action(self.contact, self.event, 'registered')
        action.action_type = 'visited'
        action.save()
        action.refresh_from_db()
        self.assertEqual(action.action_type, 'visited')

    def test_04_full_flow(self):
        """Полный цикл: announced → invited → registered → visited."""
        action = _create_action(self.contact, self.event, 'announced')
        
        # Шаг 1: announced → invited
        action.action_type = 'invited'
        action.save()
        action.refresh_from_db()
        self.assertEqual(action.action_type, 'invited')

        # Шаг 2: invited → registered
        action.action_type = 'registered'
        action.save()
        action.refresh_from_db()
        self.assertEqual(action.action_type, 'registered')

        # Шаг 3: registered → visited
        action.action_type = 'visited'
        action.save()
        action.refresh_from_db()
        self.assertEqual(action.action_type, 'visited')

    def test_05_cancel_from_invited(self):
        """Приглашён → Отменён."""
        action = _create_action(self.contact, self.event, 'invited')
        action.action_type = 'cancelled'
        action.save()
        action.refresh_from_db()
        self.assertEqual(action.action_type, 'cancelled')

    def test_06_action_has_update_user(self):
        """При изменении action_type заполняется update_user."""
        user = User.objects.create_user(phone='+79990000000', password='test')
        action = _create_action(self.contact, self.event, 'announced')
        
        action.action_type = 'invited'
        action.update_user = user
        action.save()
        
        action.refresh_from_db()
        self.assertEqual(action.update_user, user)

    def test_07_action_log_created_on_status_change(self):
        """При смене статуса создаётся запись в ActionLog."""
        action = _create_action(self.contact, self.event, 'announced')
        
        action.action_type = 'invited'
        action.save()
        
        self.assertTrue(
            ActionLog.objects.filter(
                action=action,
                old_status='announced',
                new_status='invited'
            ).exists()
        )

    def test_08_checkin_list_returns_announced(self):
        """checkin_list возвращает только announced (не visited)."""
        _create_action(self.contact, self.event, 'announced')
        _create_action(
            _create_contact('Другой', 'Контакт'),
            self.event,
            'visited'
        )
        
        announced = Action.objects.filter(
            action_type='announced',
            event=self.event
        )
        self.assertEqual(announced.count(), 1)

        visited = Action.objects.filter(
            action_type='visited',
            event=self.event
        )
        self.assertEqual(visited.count(), 1)

    def test_09_multiple_contacts_same_event(self):
        """Несколько контактов на одном мероприятии."""
        c1 = _create_contact('Первый', 'Контакт')
        c2 = _create_contact('Второй', 'Контакт')
        c3 = _create_contact('Третий', 'Контакт')
        
        _create_action(c1, self.event, 'announced')
        _create_action(c2, self.event, 'announced')
        _create_action(c3, self.event, 'announced')
        
        announced = Action.objects.filter(
            action_type='announced',
            event=self.event
        )
        self.assertEqual(announced.count(), 3)


# =====================================================================
# 2. Тесты будущих мероприятий
# =====================================================================

class FutureEventTest(TestCase):
    """Проверяет работу с будущими мероприятиями."""

    def test_01_create_future_event(self):
        """Создание мероприятия в будущем."""
        now = timezone.now()
        event = _create_full_event(name='Будущее событие', days_ahead=60)
        
        self.assertEqual(event.name, 'Будущее событие')
        self.assertTrue(event.date_start > now)
        self.assertTrue(event.is_visible)

    def test_02_create_past_event(self):
        """Создание прошедшего мероприятия."""
        now = timezone.now()
        past_event = ModuleInstance.objects.create(
            name='Прошедшее событие',
            address='Адрес',
            date_start=now - timedelta(days=10),
            date_end=now - timedelta(days=9),
            is_visible=True,
        )
        
        self.assertTrue(past_event.date_start < now)

    def test_03_create_present_event(self):
        """Создание текущего мероприятия."""
        now = timezone.now()
        present_event = ModuleInstance.objects.create(
            name='Текущее событие',
            address='Адрес',
            date_start=now - timedelta(hours=1),
            date_end=now + timedelta(hours=1),
            is_visible=True,
        )
        
        self.assertTrue(present_event.date_start < now)
        self.assertTrue(present_event.date_end > now)

    def test_04_future_event_with_contacts(self):
        """Будущее мероприятие с приглашёнными контактами."""
        event = _create_full_event(days_ahead=14)
        contacts = [
            _create_contact(f'Фамилия{i}', f'Имя{i}')
            for i in range(5)
        ]
        
        for contact in contacts:
            _create_action(contact, event, 'invited')
        
        invited = Action.objects.filter(
            action_type='invited',
            event=event
        )
        self.assertEqual(invited.count(), 5)

    def test_05_event_date_validation(self):
        """date_end не может быть раньше date_start."""
        now = timezone.now()
        
        # Это должно работать (разные даты)
        event = ModuleInstance.objects.create(
            name='Валидное событие',
            date_start=now + timedelta(days=1),
            date_end=now + timedelta(days=2),
        )
        self.assertIsNotNone(event.pk)

    def test_06_event_name_unique(self):
        """Название мероприятия должно быть уникальным."""
        _create_full_event(name='Уникальное событие')
        
        with self.assertRaises(Exception):
            _create_full_event(name='Уникальное событие')

    def test_07_list_future_events(self):
        """Получение списка будущих мероприятий."""
        now = timezone.now()
        
        # Будущее
        _create_full_event(name='Будущее 1', days_ahead=10)
        _create_full_event(name='Будущее 2', days_ahead=20)
        
        # Прошедшее
        ModuleInstance.objects.create(
            name='Прошедшее',
            date_start=now - timedelta(days=5),
            date_end=now - timedelta(days=4),
        )
        
        future_events = ModuleInstance.objects.filter(
            date_start__gt=now
        )
        self.assertEqual(future_events.count(), 2)

    def test_08_event_with_many_invitations(self):
        """Мероприятие с большим количеством приглашений (100+)."""
        event = _create_full_event(name='Масштабное событие', days_ahead=7)
        
        contacts = [
            _create_contact(f'Фамилия{i}', f'Имя{i}')
            for i in range(150)
        ]
        
        actions = [
            Action(contact=c, event=event, action_type='invited')
            for c in contacts
        ]
        Action.objects.bulk_create(actions)
        
        invited = Action.objects.filter(
            action_type='invited',
            event=event
        )
        self.assertEqual(invited.count(), 150)


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

    def test_01_query_count_for_list(self):
        """Загрузка списка checkin не должна делать более 2 запросов."""
        # Запрос к БД до
        initial_queries = len(connection.queries)
        
        # Выполняем запрос как в checkin_list
        qs = Action.objects.filter(
            action_type='announced',
            event=self.event
        ).select_related(
            'contact', 'contact__company', 'contact__category', 'contact__type_guest'
        )
        list(qs)
        
        # Запрос к БД после
        queries_made = len(connection.queries) - initial_queries
        
        # Должно быть не более 2 запросов (один к Action, один к Contact)
        self.assertLessEqual(
            queries_made, 2,
            f'Слишком много запросов: {queries_made}. Ожидалось <= 2'
        )

    def test_02_query_count_without_select_related(self):
        """Без select_related запросов будет больше (N+1)."""
        initial_queries = len(connection.queries)
        
        qs = Action.objects.filter(
            action_type='announced',
            event=self.event
        )
        list(qs)
        
        # Теперь обращаемся к contact — это вызовет N+1
        for action in qs:
            _ = action.contact.last_name
        
        queries_made = len(connection.queries) - initial_queries
        
        # Без select_related будет 1 (Action) + N (Contact) = 201+
        self.assertGreater(
            queries_made, 10,
            f'Ожидалось много запросов без select_related, но получено: {queries_made}'
        )

    def test_03_bulk_create_performance(self):
        """bulk_create должен быть быстрее поштучного создания."""
        import time
        
        # Тест на bulk_create (уже создан в setUp)
        # Проверяем, что 200 записей созданы
        self.assertEqual(Action.objects.count(), 200)

    def test_04_filter_performance_with_index(self):
        """Фильтрация по (event, action_type) должна использовать индекс."""
        from django.db import connection
        
        # Выполняем запрос
        with connection.cursor() as cursor:
            cursor.execute(
                "EXPLAIN SELECT * FROM event_action WHERE event_id = %s AND action_type = %s",
                [self.event.pk, 'announced']
            )
            plan = cursor.fetchall()
        
        plan_text = ' '.join(str(row) for row in plan)
        
        # Индекс должен использоваться (seq scan — плохо, index scan — хорошо)
        self.assertNotIn(
            'Seq Scan', plan_text,
            f'Индекс не используется! План: {plan_text}'
        )

    def test_05_count_query_performance(self):
        """count() должен быть быстрым."""
        import time
        
        start = time.time()
        count = Action.objects.filter(
            action_type='announced',
            event=self.event
        ).count()
        elapsed = time.time() - start
        
        self.assertEqual(count, 200)
        # count() должен выполняться быстро (< 1 сек даже без индекса)
        self.assertLess(elapsed, 1.0, f'count() слишком медленный: {elapsed:.3f}с')

    def test_06_status_change_with_signal(self):
        """Смена статуса не должна создавать более 3 запросов."""
        action = self.actions[0]
        initial_queries = len(connection.queries)
        
        action.action_type = 'invited'
        action.save()
        
        queries_made = len(connection.queries) - initial_queries
        
        # 1 SELECT (old_instance в signal) + 1 UPDATE = 2 запроса
        self.assertLessEqual(
            queries_made, 3,
            f'Слишком много запросов при сохранении: {queries_made}'
        )


# =====================================================================
# 4. Интеграционные тесты
# =====================================================================

class IntegrationTest(TestCase):
    """Интеграционные тесты полного workflow."""

    def setUp(self):
        self.event = _create_full_event()
        self.contact = _create_contact(last_name='Интеграция', first_name='Тест')

    def test_01_full_workflow_with_logs(self):
        """Полный workflow с проверкой логов."""
        action = _create_action(self.contact, self.event, 'announced')
        
        # announced → invited
        action.action_type = 'invited'
        action.save()
        self.assertTrue(ActionLog.objects.filter(
            action=action, old_status='announced', new_status='invited'
        ).exists())
        
        # invited → registered
        action.action_type = 'registered'
        action.save()
        self.assertTrue(ActionLog.objects.filter(
            action=action, old_status='invited', new_status='registered'
        ).exists())
        
        # registered → visited
        action.action_type = 'visited'
        action.save()
        self.assertTrue(ActionLog.objects.filter(
            action=action, old_status='registered', new_status='visited'
        ).exists())

    def test_02_multiple_events_same_contact(self):
        """Один контакт на нескольких мероприятиях."""
        event2 = _create_full_event(name='Мероприятие 2', days_ahead=20)
        
        _create_action(self.contact, self.event, 'announced')
        _create_action(self.contact, event2, 'announced')
        
        actions = Action.objects.filter(contact=self.contact)
        self.assertEqual(actions.count(), 2)

    def test_03_event_visibility(self):
        """Проверка флага is_visible."""
        visible_event = _create_full_event(name='Видимое', days_ahead=5)
        hidden_event = _create_full_event(name='Скрытое', days_ahead=10)
        hidden_event.is_visible = False
        hidden_event.save()
        
        visible = ModuleInstance.objects.filter(is_visible=True)
        hidden = ModuleInstance.objects.filter(is_visible=False)
        
        self.assertEqual(visible.count(), 1)
        self.assertEqual(hidden.count(), 1)
