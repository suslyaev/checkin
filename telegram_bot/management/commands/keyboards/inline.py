from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Открыть Attendly", web_app=WebAppInfo(url="https://checker.sukiasyan.pro/"))]
    ]
)