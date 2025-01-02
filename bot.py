import os
import json
import logging
import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import BotCommand, Message
from dotenv import load_dotenv
import pytz
from typing import Optional
from io import TextIOWrapper, BytesIO
from PIL import Image, ImageDraw, ImageFont
import random



# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(funcName)s:%(lineno)d - %(message)s'
)
logger = logging.getLogger(__name__)

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)
ADMINS_FILE = os.path.join(DATA_DIR, "admins.json")

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
CHANNEL_ID = int(os.getenv('CHANNEL_ID'))
MAIN_ADMIN_ID = int(os.getenv('MAIN_ADMIN_ID'))
TIMEZONE = pytz.timezone(os.getenv('TIMEZONE', 'UTC'))

MAIN_ADMIN_COMMANDS = [
    BotCommand(command="add_admin", description="Add new administrator"),
    BotCommand(command="remove_admin", description="Remove administrator"),
    BotCommand(command="list_admins", description="Show list of authorized administrators"),
    BotCommand(command="last_post", description="Check when the last post was made"),
    BotCommand(command="help", description="Show help message")
]

REGULAR_ADMIN_COMMANDS = [
    BotCommand(command="last_post", description="Check when the last post was made"),
    BotCommand(command="help", description="Show help message")
]

ALLOWED_MEDIA_TYPES = [
    types.ContentType.PHOTO,
    types.ContentType.AUDIO,
    types.ContentType.VIDEO,
    types.ContentType.ANIMATION,
    types.ContentType.DOCUMENT,
    types.ContentType.VOICE,
    types.ContentType.VIDEO_NOTE,
]


# Initialize bot and dispatcher
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


class PostTracker:
    def __init__(self):
        self.last_post_time: Optional[datetime] = None

    def update_last_post_time(self, time: datetime):
        """Update the time of last post"""
        self.last_post_time = time


async def add_watermark_to_bytes(image_bytes, watermark_text, opacity=50, text_width_ratio=0.33, shadow_offset=3,
                                 shadow_opacity=40):
    """
    Async function to add watermark to image bytes and return result as bytes.

    Args:
        image_bytes (bytes): Input image as bytes
        watermark_text (str): Text to use as watermark
        opacity (int): Opacity of main text (0-255)
        text_width_ratio (float): Width of text relative to image width
        shadow_offset (int): Shadow offset in pixels
        shadow_opacity (int): Shadow opacity (0-255)

    Returns:
        BytesIO: Watermarked image as BytesIO object
    """
    try:
        # Run PIL operations in a thread pool since they're CPU-bound
        return await asyncio.get_event_loop().run_in_executor(
            None,
            process_image,
            image_bytes,
            watermark_text,
            opacity,
            text_width_ratio,
            shadow_offset,
            shadow_opacity
        )
    except Exception as e:
        print(f"Error in add_watermark_to_bytes: {str(e)}")
        raise e


def process_image(image_bytes, watermark_text, opacity, text_width_ratio, shadow_offset, shadow_opacity):
    """
    Synchronous image processing function to be run in thread pool
    """
    # Open image from bytes
    img = Image.open(BytesIO(image_bytes))

    # Create copies to work with
    img_copy = img.copy()
    if img_copy.mode != 'RGBA':
        img_copy = img_copy.convert('RGBA')

    # Create a transparent overlay for watermark
    watermark = Image.new('RGBA', img_copy.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(watermark)

    # Calculate desired width of text
    desired_text_width = int(img_copy.width * text_width_ratio)

    # Test available fonts
    available_font = None
    font_paths = [
        'arial.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/System/Library/Fonts/Helvetica.ttc',  # macOS
        'C:\\Windows\\Fonts\\arial.ttf',  # Windows
        '/usr/share/fonts/TTF/DejaVuSans.ttf'  # Linux
    ]

    # Find first available font
    for font_path in font_paths:
        try:
            test_font = ImageFont.truetype(font_path, size=20)
            available_font = font_path
            break
        except:
            continue

    if not available_font:
        default_font = ImageFont.load_default()
        bbox = draw.textbbox((0, 0), watermark_text, font=default_font)
        text_width = bbox[2] - bbox[0]
        scale_factor = desired_text_width / text_width
        font = default_font
    else:
        # Start with a reasonable size and measure
        test_size = 100
        font = ImageFont.truetype(available_font, size=test_size)
        bbox = draw.textbbox((0, 0), watermark_text, font=font)
        test_width = bbox[2] - bbox[0]

        # Calculate the required scale factor
        scale_factor = desired_text_width / test_width
        final_size = int(test_size * scale_factor)

        # Create font with final size
        font = ImageFont.truetype(available_font, size=final_size)

    # Get final measurements
    bbox = draw.textbbox((0, 0), watermark_text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    # Calculate random position
    padding = 10
    max_x = img_copy.width - text_width - padding
    max_y = img_copy.height - text_height - padding

    if max_x < padding: max_x = padding
    if max_y < padding: max_y = padding

    x = random.randint(padding, max_x)
    y = random.randint(padding, max_y)

    # Draw the shadow
    draw.text((x + shadow_offset, y + shadow_offset),
              watermark_text,
              font=font,
              fill=(0, 0, 0, shadow_opacity))

    # Draw the main text
    draw.text((x, y),
              watermark_text,
              font=font,
              fill=(255, 255, 255, opacity))

    # Combine the original image with the watermark
    watermarked = Image.alpha_composite(img_copy, watermark)

    # Convert back to RGB
    watermarked = watermarked.convert('RGB')

    # Save to BytesIO object
    output = BytesIO()
    watermarked.save(output, format='JPEG', quality=95)
    output.seek(0)

    return output


# Initialize post tracker
post_tracker = PostTracker()


def load_admins() -> dict[int, str]:
    """Load admins with their usernames, migrate from old format if needed"""
    os.makedirs(DATA_DIR, exist_ok=True)

    if not os.path.exists(ADMINS_FILE):
        # Create default empty admins file
        f: TextIOWrapper
        with open(ADMINS_FILE, 'w', encoding='utf-8') as f:
            json.dump({'authorized_users': {}}, f, ensure_ascii=False)
        return {}

    try:
        with open(ADMINS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)

            # Handle old format (list of ids)
            if isinstance(data.get('authorized_users', []), list):
                old_admins = data.get('authorized_users', [])
                # Convert to new format
                new_admins = {int(admin_id): f"User_{admin_id}" for admin_id in old_admins}
                # Save in new format
                save_admins(new_admins)
                return new_admins

            # Handle new format (dict with usernames)
            return {int(id_): username for id_, username in data.get('authorized_users', {}).items()}
    except Exception as e:
        logger.error(f"Error loading admins: {e}")
        return {}


def save_admins(admins: dict[int, str]) -> None:
    """Save admins with their usernames"""
    os.makedirs(DATA_DIR, exist_ok=True)
    f: TextIOWrapper
    with open(ADMINS_FILE, 'w', encoding='utf-8') as f:
        json_data = {'authorized_users': {str(k): v for k, v in admins.items()}}
        json.dump(json_data, f, ensure_ascii=False)


def is_authorized(user_id: int) -> bool:
    """Check if user is authorized"""
    admins = load_admins()
    return user_id == MAIN_ADMIN_ID or user_id in admins.keys()

async def set_commands_for_user(user_id: int):
    """Set appropriate commands list based on user type"""
    try:
        # First try to check if we can access the chat
        try:
            await bot.get_chat(user_id)
        except:
            logger.info(f"Cannot access chat for user {user_id} yet - waiting for first interaction")
            return False

        if user_id == MAIN_ADMIN_ID:
            await bot.set_my_commands(
                commands=MAIN_ADMIN_COMMANDS,
                scope=types.BotCommandScopeChat(chat_id=user_id)
            )
        elif user_id in load_admins():
            await bot.set_my_commands(
                commands=REGULAR_ADMIN_COMMANDS,
                scope=types.BotCommandScopeChat(chat_id=user_id)
            )
        return True
    except Exception as e:
        logger.warning(f"Error setting commands for user {user_id}: {e}")
        return False


async def notify_main_admin(user_info: dict, action: str, scheduled_time: Optional[datetime] = None):
    """Notify main admin about admin actions"""
    try:
        if user_info['id'] != MAIN_ADMIN_ID:  # Don't notify about own actions
            message = f"Admin {user_info.get('username', 'Unknown')} ({user_info['id']}) {action}"
            if scheduled_time:
                message += f"\nScheduled for: {scheduled_time.strftime('%Y-%m-%d %H:%M:%S %Z')}"
            await bot.send_message(MAIN_ADMIN_ID, message)
    except Exception as e:
        logger.error(f"Failed to notify main admin: {e}")


@dp.message(Command("add_admin"))
async def add_admin(message: Message):
    if message.from_user.id != MAIN_ADMIN_ID:
        await message.reply("Only the main admin can add new admins.")
        return

    try:
        # Get user ID from command
        new_admin_id = int(message.text.split()[1])

        # Try to get username for the new admin
        try:
            chat_member = await bot.get_chat_member(message.chat.id, new_admin_id)
            username = chat_member.user.username or f"User_{new_admin_id}"
            has_access = True
        except:
            username = f"User_{new_admin_id}"
            has_access = False

        # Load current admins and add new one
        admins = load_admins()
        admins[new_admin_id] = username
        save_admins(admins)

        # Try to set commands, but don't fail if we can't
        try:
            if has_access:
                await set_commands_for_user(new_admin_id)
                await message.reply(
                    f"Admin {username} ({new_admin_id}) added successfully.\n"
                    f"Commands are set up and ready to use."
                )
            else:
                await message.reply(
                    f"Admin {username} ({new_admin_id}) added successfully.\n\n"
                    f"⚠️ Note: The user hasn't interacted with the bot yet.\n"
                    f"Please ask them to:\n"
                    f"1. Start the bot by opening @{(await bot.get_me()).username}\n"
                    f"2. Send any message to the bot\n"
                    f"After that, they will get access to all admin commands."
                )
        except Exception as e:
            logger.error(f"Error setting up commands for new admin: {e}")
            await message.reply(
                f"Admin {username} ({new_admin_id}) added successfully.\n\n"
                f"⚠️ Note: There was an issue setting up commands.\n"
                f"Please ask them to:\n"
                f"1. Start the bot by opening @{(await bot.get_me()).username}\n"
                f"2. Send any message to the bot\n"
                f"After that, they will get access to all admin commands."
            )

    except (IndexError, ValueError):
        await message.reply("Please provide a valid user ID: /add_admin USER_ID")
    except Exception as e:
        logger.error(f"Error adding admin: {e}")
        await message.reply("Error adding admin. Please try again later.")


@dp.message(Command("remove_admin"))
async def remove_admin(message: Message):
    if message.from_user.id != MAIN_ADMIN_ID:
        await message.reply("Only the main admin can remove admins.")
        return

    try:
        admin_id = int(message.text.split()[1])
        admins = load_admins()
        if admin_id in admins:
            username = admins[admin_id]
            del admins[admin_id]
            save_admins(admins)
            # Remove commands for the removed admin
            try:
                await bot.delete_my_commands(scope=types.BotCommandScopeChat(chat_id=admin_id))
            except Exception as e:
                logger.error(f"Error removing commands for user {admin_id}: {e}")
            await message.reply(f"Admin {username} ({admin_id}) removed successfully.")
        else:
            await message.reply("This user is not an admin.")
    except (IndexError, ValueError):
        await message.reply("Please provide a valid user ID: /remove_admin USER_ID")


@dp.message(Command("list_admins"))
async def list_admins(message: Message):
    if not is_authorized(message.from_user.id):
        await message.reply("You are not authorized to use this command.")
        return

    admins = load_admins()

    # Try to get main admin's username
    try:
        main_admin = await bot.get_chat_member(MAIN_ADMIN_ID, MAIN_ADMIN_ID)
        main_username = main_admin.user.username or f"User_{MAIN_ADMIN_ID}"
    except:
        main_username = f"User_{MAIN_ADMIN_ID}"

    admins_list = [
        f"👑 Main admin: {main_username} ({MAIN_ADMIN_ID})",
        "\n👥 Other admins:"
    ]

    for admin_id, username in admins.items():
        admins_list.append(f"- {username} ({admin_id})")

    await message.reply("\n".join(admins_list) if len(admins) > 0 else "No other admins.")


@dp.message(Command("last_post"))
async def check_last_post(message: Message):
    if not is_authorized(message.from_user.id):
        await message.reply("You are not authorized to use this command.")
        return

    if post_tracker.last_post_time is None:
        await message.reply("No posts have been made yet.")
    else:
        await message.reply(f"Last post was at: {post_tracker.last_post_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")


@dp.message(Command("help"))
async def show_help(message: Message):
    if not is_authorized(message.from_user.id):
        await message.reply("You are not authorized to use this bot.")
        return

    help_text = """
Available commands:
/add_admin USER_ID - Add new administrator (main admin only)
/remove_admin USER_ID - Remove administrator (main admin only)
/list_admins - Show list of authorized administrators
/last_post - Check when the last post was made
/help - Show this help message

To use the bot, simply forward or send media (photo, video, GIF) to be posted in the channel.
"""
    await message.reply(help_text)


@dp.message()
async def handle_media(message: Message):
    if not is_authorized(message.from_user.id):
        await message.reply("You are not authorized to use this bot.")
        return

    # Try to set commands for user if they haven't been set
    await set_commands_for_user(message.from_user.id)

    # If it's a command or not media, ignore
    if message.text and message.text.startswith('/'):
        return

    # Check if message contains media
    media = None
    media_type = None
    if message.photo:
        media = message.photo[-1]
        media_type = "photo"
    elif message.video:
        media = message.video
        media_type = "video"
    elif message.animation:
        media = message.animation
        media_type = "animation"
    elif message.video:
        media = message.video
        media_type = "video"
    elif message.video_note:
        media = message.video_note
        media_type = "video_note"
    elif message.audio:
        media = message.audio
        media_type = "audio"
    elif message.voice:
        media = message.voice
        media_type = "voice"
    elif message.document:
        media = message.document
        media_type = "document"
    else:
        await message.reply(f"Please send a message of following types: {ALLOWED_MEDIA_TYPES}")
        return

    try:
        # Create user info dict for notification
        user_info = {
            'id': message.from_user.id,
            'username': message.from_user.username or f"User_{message.from_user.id}"
        }

        # Post immediately
        if media_type == "photo":
            try:
                # Download the photo
                file = await bot.get_file(media.file_id)
                photo_io = await bot.download_file(file.file_path)  # Changed from file.file_id to file.file_path
                # Convert BinaryIO to bytes
                photo_bytes = photo_io.read()

                # Add watermark
                watermarked = await add_watermark_to_bytes(
                    photo_bytes,
                    watermark_text="@TOOLOCAL",  # Change this to your watermark text
                    opacity=128,
                    text_width_ratio=0.33,
                    shadow_offset=3,
                    shadow_opacity=40
                )

                # Send watermarked photo using input_file
                await bot.send_photo(
                    chat_id=CHANNEL_ID,
                    photo=types.BufferedInputFile(
                        watermarked.getvalue(),
                        filename="watermarked.jpg"
                    ),
                    caption=message.caption if message.caption else None
                )
            except Exception as e:
                logger.error(f"Error processing photo watermark: {e}")
                # Fallback to sending original photo if watermarking fails
                await bot.send_photo(chat_id=CHANNEL_ID, photo=media.file_id)

        elif media_type == "video":
            await bot.send_video(chat_id=CHANNEL_ID, video=media.file_id)
        elif media_type == "animation":
            await bot.send_animation(chat_id=CHANNEL_ID, animation=media.file_id)
        elif media_type == "video_note":
            await bot.send_video_note(chat_id=CHANNEL_ID, video_note=media.file_id)
        elif media_type == "voice":
            await bot.send_voice(chat_id=CHANNEL_ID, voice=media.file_id)
        elif media_type == "audio":
            await bot.send_audio(chat_id=CHANNEL_ID, audio=media.file_id)
        elif media_type == "document":
            await bot.send_document(chat_id=CHANNEL_ID, document=media.file_id)
        elif media_type == "animation":
            await bot.send_animation(chat_id=CHANNEL_ID, animation=media.file_id)

        post_tracker.update_last_post_time(datetime.now(TIMEZONE))
        await message.reply("Message posted successfully.")
        await notify_main_admin(
            user_info,
            f"posted a {media_type}"
        )

    except Exception as e:
        logger.error(f"Error processing message: {e}")
        await message.reply(f"Error processing your message: {str(e)}")

@dp.message()
async def handle_message(message: Message):
    # Try to set commands for user if they haven't been set
    await set_commands_for_user(message.from_user.id)

    # If it's not a command, handle as media
    if not message.text or not message.text.startswith('/'):
        await handle_media(message)


async def main():
    try:
        # Set default commands (empty) for all users
        try:
            await bot.delete_my_commands()
        except Exception as e:
            logger.warning(f"Error deleting default commands: {e}")

        # Set commands for main admin
        await set_commands_for_user(MAIN_ADMIN_ID)

        # Set commands for existing admins
        admins = load_admins()
        for admin_id in admins:
            await set_commands_for_user(admin_id)

        # Start polling
        await dp.start_polling(bot)

    except Exception as e:
        logger.error(f"Error in main: {e}")

if __name__ == '__main__':
    asyncio.run(main())
