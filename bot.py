import os
import logging
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Загрузка переменных окружения
API_TOKEN = os.getenv("BOT_TOKEN")
MOD_CHAT_ID = int(os.getenv("MOD_CHAT_ID"))
TARGET_CHANNEL = int(os.getenv("TARGET_CHANNEL"))
WATCHED_CHANNELS = [int(cid) for cid in os.getenv("WATCHED_CHANNELS", "-1009999999999").split(",")]
ADMINS = [int(uid) for uid in os.getenv("ADMINS", "").split(",")]

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN, parse_mode=types.ParseMode.HTML)
dp = Dispatcher(bot)


# Временная функция — получить ID канала через пересылку
@dp.message_handler(content_types=types.ContentTypes.ANY)
async def get_channel_id(msg: types.Message):
    if msg.forward_from_chat:
        await msg.answer(f"ID канала: <code>{msg.forward_from_chat.id}</code>")
    else:
        await msg.answer("Это не пересланное сообщение из канала")


# Генерация кнопок модерации
def get_moderation_keyboard(original_chat_id, original_msg_id):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("✅ Пост", callback_data=f"post:{original_chat_id}:{original_msg_id}"),
        InlineKeyboardButton("❌ Пропустить", callback_data=f"skip:{original_chat_id}:{original_msg_id}")
    )
    return keyboard


# Обработка новых сообщений из отслеживаемых каналов
@dp.channel_post_handler(lambda message: message.chat.id in WATCHED_CHANNELS)
async def handle_channel_post(message: types.Message):
    await bot.copy_message(
        chat_id=MOD_CHAT_ID,
        from_chat_id=message.chat.id,
        message_id=message.message_id,
        reply_markup=get_moderation_keyboard(message.chat.id, message.message_id)
    )


# Обработка кнопок модерации
@dp.callback_query_handler(lambda c: c.data.startswith("post") or c.data.startswith("skip"))
async def handle_callback(callback: types.CallbackQuery):
    action, channel_id, msg_id = callback.data.split(":")
    channel_id = int(channel_id)
    msg_id = int(msg_id)

    if action == "post":
        try:
            await bot.copy_message(
                chat_id=TARGET_CHANNEL,
                from_chat_id=channel_id,
                message_id=msg_id
            )
            await callback.message.edit_text("✅ Опубликовано")
        except Exception as e:
            await callback.message.edit_text(f"Ошибка: {e}")
    elif action == "skip":
        await callback.message.edit_text("❌ Пропущено")

    await callback.answer()


if __name__ == '__main__':
    print("Бот запущен...")
    executor.start_polling(dp, skip_updates=True)
