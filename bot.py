import os
import logging
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, InputMediaVideo
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

# Временное хранилище медиа-групп
media_groups = {}

# 📩 Приём сообщений от Telethon
@dp.message_handler(content_types=types.ContentTypes.ANY)
async def handle_telethon_message(msg: types.Message):
    print(f"➡️ Получено сообщение: {msg.text or msg.caption}")
    kb = get_manual_keyboard(msg.message_id)

    # Обработка альбомов
    if msg.media_group_id:
        group = media_groups.setdefault(msg.media_group_id, [])
        group.append(msg)

        await asyncio.sleep(1.0)  # Подождать, пока соберутся все части
        if len(group) > 1:
            media = []
            for m in group:
                if m.photo:
                    media.append(InputMediaPhoto(media=m.photo[-1].file_id, caption=m.caption if len(media) == 0 else None))
                elif m.video:
                    media.append(InputMediaVideo(media=m.video.file_id, caption=m.caption if len(media) == 0 else None))
            if media:
                sent = await bot.send_media_group(chat_id=msg.chat.id, media=media)
                await bot.send_message(chat_id=msg.chat.id, text="Модерация альбома:", reply_markup=kb, reply_to_message_id=sent[0].message_id)
            media_groups.pop(msg.media_group_id, None)
        return

    # Обычные сообщения
    if msg.photo:
        await bot.send_photo(chat_id=msg.chat.id, photo=msg.photo[-1].file_id, caption=msg.caption, reply_markup=kb)
    elif msg.video:
        await bot.send_video(chat_id=msg.chat.id, video=msg.video.file_id, caption=msg.caption, reply_markup=kb)
    elif msg.document:
        await bot.send_document(chat_id=msg.chat.id, document=msg.document.file_id, caption=msg.caption, reply_markup=kb)
    elif msg.text:
        await bot.send_message(chat_id=msg.chat.id, text=msg.text, reply_markup=kb)
    else:
        await msg.reply("❌ Неподдерживаемый формат.")

# ✅ Публикация
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
    executor.start_polling(dp, skip_updates=False)
