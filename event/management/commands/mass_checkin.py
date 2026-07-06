"""
Management command для массового checkin всех приглашённых мероприятия.

Использование:
    python3 manage.py mass_checkin --dry-run          # Проверка без изменений
    python3 manage.py mass_checkin --event "Название"  # Выполнить
    python3 manage.py mass_checkin --all                # Все мероприятия с приглашёнными

Цепочка статусов:
    invited → registered → visited

Пример:
    python3 manage.py mass_checkin --event "Активность 11.06.2026"
"""
from django.core.management.base import BaseCommand, CommandError
from event.models import Action, ModuleInstance


class Command(BaseCommand):
    help = 'Массовый checkin всех приглашённых мероприятия'

    def add_arguments(self, parser):
        parser.add_argument(
            '--event',
            type=str,
            help='Название мероприятия для checkin',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Checkin всех мероприятий с приглашёнными',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Только показать что будет сделано, без изменений',
        )
        parser.add_argument(
            '--skip-registered',
            action='store_true',
            help='Пропустить этап registered (invited → visited)',
        )

    def handle(self, *args, **options):
        event_name = options['event']
        all_events = options['all']
        dry_run = options['dry_run']
        skip_registered = options['skip_registered']

        # Находим мероприятия
        if event_name:
            events = ModuleInstance.objects.filter(name__icontains=event_name)
            if not events.exists():
                raise CommandError(f'Мероприятие "{event_name}" не найдено')
        elif all_events:
            events = ModuleInstance.objects.all()
        else:
            raise CommandError(
                'Укажите --event "Название" или --all для всех мероприятий'
            )

        total_processed = 0
        total_skipped = 0
        total_errors = 0

        for event in events:
            self.stdout.write(f'\n{"="*60}')
            self.stdout.write(f'Мероприятие: {event.name} (ID={event.pk})')
            self.stdout.write(f'{"="*60}')

            # Находим всех приглашённых
            invited_actions = Action.objects.filter(
                event=event,
                action_type='invited'
            ).select_related('contact').order_by('contact__last_name', 'contact__first_name')

            if not invited_actions.exists():
                self.stdout.write(self.style.WARNING('Нет приглашённых для этого мероприятия'))
                continue

            self.stdout.write(f'Найдено приглашённых: {invited_actions.count()}')

            # Показываем список
            if dry_run:
                self.stdout.write('\nСписок для обработки:')
                for action in invited_actions:
                    self.stdout.write(f'  - {action.contact} (ID={action.contact.pk})')

            if dry_run:
                self.stdout.write(self.style.SUCCESS(f'\n[DRY RUN] Всего будет обработано: {invited_actions.count()} человек'))
                total_processed += invited_actions.count()
                continue

            # Этап 1: invited → registered
            if not skip_registered:
                self.stdout.write('\nЭтап 1: invited → registered (подтверждение)...')
                registered_count = 0
                for action in invited_actions:
                    try:
                        if action.action_type == 'invited':
                            action.action_type = 'registered'
                            action.save(update_fields=['action_type', 'update_date'])
                            registered_count += 1
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'  Ошибка для {action.contact}: {e}'))
                        total_errors += 1

                self.stdout.write(
                    self.style.SUCCESS(f'  Подтверждено: {registered_count}/{invited_actions.count()}')
                )
                total_processed += registered_count

                # Обновляем queryset для следующего этапа
                invited_actions = Action.objects.filter(
                    event=event,
                    action_type='registered'
                ).select_related('contact')

            # Этап 2: registered → visited (checkin)
            self.stdout.write('\nЭтап 2: registered → visited (checkin)...')
            checkin_count = 0
            for action in invited_actions:
                try:
                    if action.action_type == 'registered':
                        action.action_type = 'visited'
                        action.save(update_fields=['action_type', 'update_date'])
                        checkin_count += 1
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'  Ошибка для {action.contact}: {e}'))
                    total_errors += 1

            self.stdout.write(
                self.style.SUCCESS(f'  Зачекинены: {checkin_count}/{invited_actions.count()}')
            )
            total_processed += checkin_count

            # Финальная проверка
            final_invited = Action.objects.filter(event=event, action_type='invited').count()
            final_registered = Action.objects.filter(event=event, action_type='registered').count()
            final_visited = Action.objects.filter(event=event, action_type='visited').count()

            self.stdout.write(f'\n{"="*60}')
            self.stdout.write(f'Итог для "{event.name}":')
            self.stdout.write(f'  Приглашённых: {final_invited}')
            self.stdout.write(f'  Подтверждённых: {final_registered}')
            self.stdout.write(f'  Посетивших: {final_visited}')
            self.stdout.write(f'{"="*60}')

        # Общий итог
        self.stdout.write(f'\n{"="*60}')
        self.stdout.write(self.style.SUCCESS(f'ОБЩИЙ ИТОГ:'))
        self.stdout.write(f'  Обработано: {total_processed}')
        self.stdout.write(f'  Ошибок: {total_errors}')
        self.stdout.write(f'{"="*60}')

        if total_errors > 0:
            raise CommandError(f'Завершено с {total_errors} ошибками')
