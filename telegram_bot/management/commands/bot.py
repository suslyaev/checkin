import asyncio

from django.core.management.base import BaseCommand
from aiogram import Dispatcher, Bot, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.utils import markdown
from aiogram.types import Message, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
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

                user = await sync_to_async(CustomUser.objects.get)(ext_id=str(message.from_user.id))
                token = await sync_to_async(user.generate_auth_token)()
                auth_url = f"{BASE_URL}/telegram-auth/?token={token}"

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
                await message.answer("Доступ запрещен!")

            except Exception as e:
                logger.exception(e)

        async def main() -> None:
            bot = Bot(token=TELEGRAM_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
            dp = Dispatcher(storage=storage)
            dp.include_router(router=router)

            await dp.start_polling(bot)

            logger.info('Bot starting')

        asyncio.run(main())
