import os
import logging
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher.filters import Text

API_TOKEN = os.getenv("BOT_TOKEN")
TARGET_CHANNEL = int(os.getenv("TARGET_CHANNEL"))
ADMINS = [int(uid) for uid in os.getenv("ADMINS", "").split(",") if uid]

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN, parse_mode=types.ParseMode.HTML)
dp = Dispatcher(bot)

# ✨ Удаляет последнюю строку, если там есть ссылка или хэштег

def clean_signature(text: str) -> str:
    lines = text.strip().split('\n')
    if len(lines) < 2:
        return text

    last = lines[-1].strip()
    if any(x in last for x in ['http', 't.me/', '@', '#']):
        return '\n'.join(lines[:-1])
    return text

# 📌 Кнопки

def get_manual_keyboard(message_id):
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("✅ Пост", callback_data=f"post_manual:{message_id}"),
        InlineKeyboardButton("❌ Пропустить", callback_data=f"skip_manual:{message_id}")
    )
    return kb

# 📩 Приём сообщений от Telethon
@dp.message_handler(content_types=types.ContentTypes.ANY)
async def handle_telethon_message(msg: types.Message):
    await msg.reply("Сообщение от Telethon:", reply_markup=get_manual_keyboard(msg.message_id))

# ✅ Побликация
@dp.callback_query_handler(Text(startswith="post_manual"))
async def post_message(callback: types.CallbackQuery):
    msg_id = int(callback.data.split(":")[1])

    try:
        original = callback.message.reply_to_message
        content = original.text or original.caption
        clean = clean_signature(content) if content else None

        if clean:
            await bot.send_message(chat_id=TARGET_CHANNEL, text=clean)
        elif original.content_type == "photo":
            await bot.send_photo(TARGET_CHANNEL, original.photo[-1].file_id, caption=original.caption)
        elif original.content_type == "video":
            await bot.send_video(TARGET_CHANNEL, original.video.file_id, caption=original.caption)
        elif original.content_type == "document":
            await bot.send_document(TARGET_CHANNEL, original.document.file_id, caption=original.caption)
        else:
            await original.copy_to(TARGET_CHANNEL)

        await callback.message.edit_text("✅ Опубликовано")
    except Exception as e:
        await callback.message.edit_text(f"Ошибка: {e}")

    await callback.answer()

# ❌ Пропуск
@dp.callback_query_handler(Text(startswith="skip_manual"))
async def skip_post(callback: types.CallbackQuery):
    await callback.message.edit_text("❌ Пропущено")
    await callback.answer()

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
