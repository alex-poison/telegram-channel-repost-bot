import os
import logging
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Настройки из окружения
API_TOKEN = os.getenv("BOT_TOKEN")
TARGET_CHANNEL = int(os.getenv("TARGET_CHANNEL"))
ADMINS = [int(uid) for uid in os.getenv("ADMINS", "").split(",")]

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN, parse_mode=types.ParseMode.HTML)
dp = Dispatcher(bot)


# Генерация кнопок под каждым постом от Telethon
def get_manual_keyboard(message_id):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("✅ Пост", callback_data=f"post_manual:{message_id}"),
        InlineKeyboardButton("❌ Пропустить", callback_data=f"skip_manual:{message_id}")
    )
    return keyboard


# Хендлер: входящее сообщение от Telethon
@dp.message_handler(content_types=types.ContentTypes.ANY)
async def handle_telethon_message(message: types.Message):
    # Если пишет не админ — игнор
    if message.from_user.id not in ADMINS:
        return

    # Отвечаем на сообщение кнопками модерации
    await message.reply("Сообщение от Telethon", reply_markup=get_manual_keyboard(message.message_id))


# Хендлер: обработка кнопок ✅ ❌
@dp.callback_query_handler(lambda c: c.data.startswith("post_manual") or c.data.startswith("skip_manual"))
async def handle_manual_buttons(callback: types.CallbackQuery):
    action, msg_id = callback.data.split(":")
    msg_id = int(msg_id)

    if action == "post_manual":
        try:
            await bot.copy_message(
                chat_id=TARGET_CHANNEL,
                from_chat_id=callback.message.chat.id,
                message_id=callback.message.reply_to_message.message_id
            )
            await callback.message.edit_text("✅ Опубликовано")
        except Exception as e:
            await callback.message.edit_text(f"Ошибка: {e}")
    elif action == "skip_manual":
        await callback.message.edit_text("❌ Пропущено")

    await callback.answer()


if __name__ == '__main__':
    print("Бот запущен...")
    executor.start_polling(dp, skip_updates=True)
