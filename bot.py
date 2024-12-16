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
from io import TextIOWrapper


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
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


# Initialize bot and dispatcher
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


class PostTracker:
    def __init__(self):
        self.last_post_time: Optional[datetime] = None

    def update_last_post_time(self, time: datetime):
        """Update the time of last post"""
        self.last_post_time = time


# Initialize post tracker
post_tracker = PostTracker()


def load_admins() -> dict[int, str]:
    """Load admins with their usernames, migrate from old format if needed"""
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
    except FileNotFoundError:
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
    else:
        await message.reply("Please send a photo, video, or GIF.")
        return

    try:
        # Create user info dict for notification
        user_info = {
            'id': message.from_user.id,
            'username': message.from_user.username or f"User_{message.from_user.id}"
        }

        # Post immediately
        if media_type == "photo":
            await bot.send_photo(chat_id=CHANNEL_ID, photo=media.file_id)
        elif media_type == "video":
            await bot.send_video(chat_id=CHANNEL_ID, video=media.file_id)
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
