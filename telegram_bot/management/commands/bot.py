import asyncio

from aiogram.utils.keyboard import ReplyKeyboardBuilder
from django.core.management.base import BaseCommand
from aiogram import Dispatcher, Bot, Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.utils import markdown
from aiogram.types import Message, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, \
    ReplyKeyboardMarkup
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from asgiref.sync import sync_to_async

from config.settings import TELEGRAM_BOT_TOKEN, BASE_URL
from event.models import CustomUser
from telegram_bot.management.commands.services.DjangoStorage import DjangoStorage
from telegram_bot.management.commands.services.logging_config import logger
from telegram_bot.management.commands.states.user import Menu

storage = DjangoStorage()


class Command(BaseCommand):
    help = "Telegram bot commands"

    def handle(self, *args, **options):

        router = Router(name=__name__)

        @router.message(CommandStart())
        async def start(message: Message, state: FSMContext) -> None:
            try:
                # Создаем клавиатуру с кнопкой контакта заранее
                builder_contact = ReplyKeyboardBuilder()
                builder_contact.button(text="Отправить контакт", request_contact=True)

                try:
                    user = await sync_to_async(CustomUser.objects.get)(ext_id=str(message.from_user.id))
                    token = await sync_to_async(user.generate_auth_token)()
                    auth_url = f"{BASE_URL}/event/telegram-auth/?token={token}"

                    await state.set_state(Menu.start)
                    text = markdown.text(
                        markdown.hbold(
                            f'Здравствуй, {message.from_user.first_name} {message.from_user.last_name if message.from_user.last_name else ""}'),
                        'Attendly — простой и удобный инструмент для управления гостями на ваших мероприятиях.',
                        'Ниже нажми на кнопку, чтобы открыть Attendly',
                        sep='\n'
                    )
                    keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(
                            text="Открыть Attendly",
                            web_app=WebAppInfo(url=auth_url)
                        )]
                    ])

                    message_id = await message.answer(text=text, reply_markup=keyboard)
                    await state.update_data(data={'last_message_id': message_id.message_id})
                    
                except CustomUser.DoesNotExist:
                    await message.answer(
                        "У вас нет доступа.\n\nОтправьте свой контакт, чтобы я проверил есть ли вы в базе.",
                        reply_markup=builder_contact.as_markup(resize_keyboard=True))

            except Exception as e:
                logger.exception(e)

            @router.message(F.contact)
            async def contact_handler(message: Message, state: FSMContext) -> None:
                try:
                    # Форматируем номер телефона в нужный формат (+7XXXXXXXXXX)
                    phone = str(message.contact.phone_number)
                    if phone.startswith('8'):
                        phone = '+7' + phone[1:]
                    elif phone.startswith('7'):
                        phone = '+' + phone
                    elif not phone.startswith('+7'):
                        phone = '+7' + phone

                    try:
                        # Проверяем существование пользователя с таким телефоном
                        user = await sync_to_async(CustomUser.objects.get)(phone=phone)
                        
                        # Обновляем ext_id пользователя
                        user.ext_id = str(message.from_user.id)
                        await sync_to_async(user.save)(update_fields=['ext_id'])
                        
                        # Генерируем токен для авторизации
                        token = await sync_to_async(user.generate_auth_token)()
                        auth_url = f"{BASE_URL}/event/telegram-auth/?token={token}"

                        # Отправляем сообщение с кнопкой для открытия веб-приложения
                        text = markdown.text(
                            markdown.hbold(f'Здравствуйте, {message.from_user.first_name}!'),
                            'Вы успешно авторизованы.',
                            'Нажмите кнопку ниже, чтобы открыть Attendly',
                            sep='\n'
                        )
                        
                        keyboard = InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(
                                text="Открыть Attendly",
                                web_app=WebAppInfo(url=auth_url)
                            )]
                        ])
                        
                        await message.answer(
                            text=text,
                            reply_markup=keyboard
                        )

                    except CustomUser.DoesNotExist:
                        await message.answer(
                            "К сожалению, ваш номер телефона не найден в базе. Пожалуйста, обратитесь к администратору."
                        )

                except Exception as e:
                    logger.exception(e)
                    await message.answer("Произошла ошибка при обработке контакта. Пожалуйста, попробуйте позже.")

        async def main() -> None:
            bot = Bot(token=TELEGRAM_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
            dp = Dispatcher(storage=storage)
            dp.include_router(router=router)

            await dp.start_polling(bot)

            logger.info('Bot starting')

        asyncio.run(main())
