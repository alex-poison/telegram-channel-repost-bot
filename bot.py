import os
import json
import logging
import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import BotCommand, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv
import pytz
from typing import Optional, Dict, List
from io import TextIOWrapper, BytesIO
from PIL import Image, ImageDraw, ImageFont
import random
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(funcName)s:%(lineno)d - %(message)s'
)
logger = logging.getLogger(__name__)

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)
ADMINS_FILE = os.path.join(DATA_DIR, "admins.json")
PENDING_POSTS_FILE = os.path.join(DATA_DIR, "pending_posts.json")
USER_LIMITS_FILE = os.path.join(DATA_DIR, "user_limits.json")

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
CHANNEL_ID = int(os.getenv('CHANNEL_ID'))
MAIN_ADMIN_ID = int(os.getenv('MAIN_ADMIN_ID'))
TIMEZONE = pytz.timezone(os.getenv('TIMEZONE', 'UTC'))

# Flood control settings
MAX_SUGGESTIONS_PER_DAY = 20
SUGGESTION_COOLDOWN_SECONDS = 2

MAIN_ADMIN_COMMANDS = [
    BotCommand(command="add_admin", description="Add new administrator"),
    BotCommand(command="remove_admin", description="Remove administrator"),
    BotCommand(command="list_admins", description="Show list of authorized administrators"),
    BotCommand(command="last_post", description="Check when the last post was made"),
    BotCommand(command="pending", description="Show pending posts"),
    BotCommand(command="help", description="Show help message"),
    BotCommand(command="stats", description="Show suggestion statistics")
]

REGULAR_ADMIN_COMMANDS = [
    BotCommand(command="last_post", description="Check when the last post was made"),
    BotCommand(command="pending", description="Show pending posts"),
    BotCommand(command="help", description="Show help message")
]

USER_COMMANDS = [
    BotCommand(command="start", description="Start the bot"),
    BotCommand(command="help", description="Show help message"),
    BotCommand(command="status", description="Check your suggestion status")
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


# Store pending posts with their metadata
class PendingPostsManager:
    def __init__(self):
        self.pending_posts = {}
        self.load_pending_posts()

    def load_pending_posts(self):
        if os.path.exists(PENDING_POSTS_FILE):
            try:
                with open(PENDING_POSTS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.pending_posts = {int(k): v for k, v in data.items()}
            except Exception as e:
                logger.error(f"Error loading pending posts: {e}")
                self.pending_posts = {}
        else:
            self.pending_posts = {}

    def save_pending_posts(self):
        with open(PENDING_POSTS_FILE, 'w', encoding='utf-8') as f:
            json.dump({str(k): v for k, v in self.pending_posts.items()}, f, ensure_ascii=False)

    def add_pending_post(self, post_id: int, user_id: int, username: str, media_ids: List[str],
                         media_type: str, caption: Optional[str] = None,
                         media_group_id: Optional[str] = None, original_message_id: Optional[int] = None):
        """Add a new pending post"""
        self.pending_posts[post_id] = {
            "user_id": user_id,
            "username": username,
            "media_ids": media_ids,
            "media_type": media_type,
            "caption": caption,
            "timestamp": datetime.now(TIMEZONE).isoformat(),
            "media_group_id": media_group_id,
            "original_message_id": original_message_id,  # Store the original message ID
            "status": "pending"  # pending, approved, rejected
        }
        self.save_pending_posts()
        return post_id

    def get_pending_post(self, post_id: int):
        """Get a pending post by ID"""
        return self.pending_posts.get(post_id)

    def update_post_status(self, post_id: int, status: str):
        """Update post status (pending, approved, rejected)"""
        if post_id in self.pending_posts:
            self.pending_posts[post_id]["status"] = status
            self.save_pending_posts()
            return True
        return False

    def get_all_pending_posts(self):
        """Get all pending posts (status='pending')"""
        return {k: v for k, v in self.pending_posts.items() if v.get("status") == "pending"}


# Flood control for users
class UserLimitsManager:
    def __init__(self):
        self.user_limits = {}
        self.load_user_limits()

    def load_user_limits(self):
        if os.path.exists(USER_LIMITS_FILE):
            try:
                with open(USER_LIMITS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.user_limits = {int(k): v for k, v in data.items()}
            except Exception as e:
                logger.error(f"Error loading user limits: {e}")
                self.user_limits = {}
        else:
            self.user_limits = {}

    def save_user_limits(self):
        with open(USER_LIMITS_FILE, 'w', encoding='utf-8') as f:
            json.dump({str(k): v for k, v in self.user_limits.items()}, f, ensure_ascii=False)

    def record_suggestion(self, user_id: int):
        """Record a suggestion from a user and update their limits"""
        current_time = time.time()

        if user_id not in self.user_limits:
            self.user_limits[user_id] = {
                "suggestions_today": 1,
                "last_suggestion_time": current_time,
                "day_start": current_time,
                "total_suggestions": 1,
                "approved_suggestions": 0,
                "rejected_suggestions": 0
            }
        else:
            # Check if we need to reset the daily counter
            if current_time - self.user_limits[user_id]["day_start"] > 86400:  # 24 hours
                self.user_limits[user_id]["suggestions_today"] = 1
                self.user_limits[user_id]["day_start"] = current_time
            else:
                self.user_limits[user_id]["suggestions_today"] += 1

            self.user_limits[user_id]["last_suggestion_time"] = current_time
            self.user_limits[user_id]["total_suggestions"] += 1

        self.save_user_limits()

    def record_suggestion_result(self, user_id: int, approved: bool):
        """Record the result of a suggestion (approved or rejected)"""
        if user_id in self.user_limits:
            if approved:
                self.user_limits[user_id]["approved_suggestions"] = self.user_limits[user_id].get(
                    "approved_suggestions", 0) + 1
            else:
                self.user_limits[user_id]["rejected_suggestions"] = self.user_limits[user_id].get(
                    "rejected_suggestions", 0) + 1
            self.save_user_limits()

    def can_suggest(self, user_id: int) -> tuple[bool, str]:
        """Check if a user can make a suggestion based on their limits"""
        current_time = time.time()

        if user_id not in self.user_limits:
            return True, ""

        # Check daily limit
        if self.user_limits[user_id]["suggestions_today"] >= MAX_SUGGESTIONS_PER_DAY:
            # Calculate time until reset
            seconds_until_reset = 86400 - (current_time - self.user_limits[user_id]["day_start"])
            hours = int(seconds_until_reset // 3600)
            minutes = int((seconds_until_reset % 3600) // 60)
            return False, f"You've reached the daily limit of {MAX_SUGGESTIONS_PER_DAY} suggestions. Please try again in {hours}h {minutes}m."

        # Check cooldown
        if current_time - self.user_limits[user_id]["last_suggestion_time"] < SUGGESTION_COOLDOWN_SECONDS:
            # Calculate time until cooldown ends
            seconds_remaining = SUGGESTION_COOLDOWN_SECONDS - (
                        current_time - self.user_limits[user_id]["last_suggestion_time"])
            minutes = int(seconds_remaining // 60)
            seconds = int(seconds_remaining % 60)
            return False, f"Please wait {minutes}m {seconds}s before submitting another suggestion."

        return True, ""

    def get_user_stats(self, user_id: int) -> Dict:
        """Get statistics for a specific user"""
        if user_id not in self.user_limits:
            return {
                "suggestions_today": 0,
                "total_suggestions": 0,
                "approved_suggestions": 0,
                "rejected_suggestions": 0
            }

        # Calculate suggestions remaining today
        suggestions_today = self.user_limits[user_id].get("suggestions_today", 0)
        remaining = max(0, MAX_SUGGESTIONS_PER_DAY - suggestions_today)

        return {
            "suggestions_today": suggestions_today,
            "suggestions_remaining": remaining,
            "total_suggestions": self.user_limits[user_id].get("total_suggestions", 0),
            "approved_suggestions": self.user_limits[user_id].get("approved_suggestions", 0),
            "rejected_suggestions": self.user_limits[user_id].get("rejected_suggestions", 0)
        }

    def get_all_users_stats(self) -> Dict:
        """Get statistics for all users"""
        result = {
            "total_users": len(self.user_limits),
            "total_suggestions": 0,
            "approved_suggestions": 0,
            "rejected_suggestions": 0,
            "top_users": []
        }

        user_stats = []
        for user_id, stats in self.user_limits.items():
            result["total_suggestions"] += stats.get("total_suggestions", 0)
            result["approved_suggestions"] += stats.get("approved_suggestions", 0)
            result["rejected_suggestions"] += stats.get("rejected_suggestions", 0)

            user_stats.append({
                "user_id": user_id,
                "total": stats.get("total_suggestions", 0),
                "approved": stats.get("approved_suggestions", 0)
            })

        # Get top 5 users by approved suggestions
        user_stats.sort(key=lambda x: x["approved"], reverse=True)
        result["top_users"] = user_stats[:5]

        return result


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

    # Calculate base font size from image dimensions
    base_font_size = int(min(img_copy.width, img_copy.height) / 15)  # Changed this line
    logger.info(f"Base font size: {base_font_size} for image {img_copy.width}x{img_copy.height}")

    # Available fonts
    font_paths = [
        '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
    ]

    # Find first available font with proper size
    available_font = None
    font = None

    for font_path in font_paths:
        try:
            font = ImageFont.truetype(font_path, size=base_font_size)
            available_font = font_path
            logger.info(f"Using font: {font_path} with size {base_font_size}")
            break
        except Exception as e:
            logger.debug(f"Failed to load font {font_path}: {str(e)}")
            continue

    if not available_font:
        logger.warning("No TrueType fonts found, using default font")
        font = ImageFont.load_default()

    # Get text size
    bbox = draw.textbbox((0, 0), watermark_text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    logger.info(f"Text dimensions: {text_width}x{text_height} (target: {img_copy.width * text_width_ratio})")

    # Calculate position with padding
    padding = min(img_copy.width, img_copy.height) // 30  # Dynamic padding based on image size
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


# Initialize managers
post_tracker = PostTracker()
pending_posts_manager = PendingPostsManager()
user_limits_manager = UserLimitsManager()
# Dictionary to track media groups that are being collected
media_group_collector = {}


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


async def set_commands_for_user(user_id: int, is_admin: bool = False):
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
        elif is_admin:
            await bot.set_my_commands(
                commands=REGULAR_ADMIN_COMMANDS,
                scope=types.BotCommandScopeChat(chat_id=user_id)
            )
        else:
            await bot.set_my_commands(
                commands=USER_COMMANDS,
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


async def notify_admins(text: str, exclude_user_id: Optional[int] = None):
    """Send a notification to all admins"""
    admins = load_admins()

    # Always include main admin
    admin_ids = [MAIN_ADMIN_ID] + list(admins.keys())

    # Remove duplicate IDs and excluded user
    admin_ids = list(set(admin_ids))
    if exclude_user_id is not None and exclude_user_id in admin_ids:
        admin_ids.remove(exclude_user_id)

    for admin_id in admin_ids:
        try:
            await bot.send_message(admin_id, text)
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")


@dp.callback_query(lambda c: c.data.startswith(('approve_', 'reject_')))
async def process_suggestion_action(callback_query: types.CallbackQuery):
    if not is_authorized(callback_query.from_user.id):
        await callback_query.answer("You are not authorized to perform this action.", show_alert=True)
        return

    action, post_id_str = callback_query.data.split('_', 1)
    try:
        post_id = int(post_id_str)
        post_data = pending_posts_manager.get_pending_post(post_id)

        if not post_data:
            await callback_query.answer("This post no longer exists or has already been processed.", show_alert=True)
            return

        if post_data["status"] != "pending":
            await callback_query.answer(f"This post has already been {post_data['status']}.", show_alert=True)
            return

        user_id = post_data["user_id"]
        username = post_data["username"]
        media_type = post_data["media_type"]
        timestamp = datetime.fromisoformat(post_data["timestamp"])
        submission_time = timestamp.strftime("%Y-%m-%d %H:%M:%S")
        media_ids = post_data["media_ids"]
        caption = post_data["caption"]
        media_group_id = post_data.get("media_group_id")

        # Get user info for notification
        admin_info = {
            'id': callback_query.from_user.id,
            'username': callback_query.from_user.username or f"User_{callback_query.from_user.id}"
        }

        if action == "approve":
            # Update post status
            pending_posts_manager.update_post_status(post_id, "approved")

            # Record this approved suggestion
            user_limits_manager.record_suggestion_result(user_id, True)

            # Handle different media types for posting to channel
            if media_type == "photo":
                if media_group_id:  # Multiple photos in a group
                    media_group = []
                    for file_id in media_ids:
                        # Create InputMediaPhoto objects for each photo
                        media = types.InputMediaPhoto(media=file_id)
                        # Add caption only to the first media item
                        if media_ids.index(file_id) == 0 and caption:
                            media.caption = caption
                        media_group.append(media)

                    await bot.send_media_group(chat_id=CHANNEL_ID, media=media_group)
                else:  # Single photo
                    try:
                        # Download and watermark the photo
                        file = await bot.get_file(media_ids[0])
                        photo_io = await bot.download_file(file.file_path)
                        photo_bytes = photo_io.read()

                        watermarked = await add_watermark_to_bytes(
                            photo_bytes,
                            watermark_text="@TOOLOCAL",  # Change this to your watermark text
                            opacity=128,
                            text_width_ratio=0.33,
                            shadow_offset=3,
                            shadow_opacity=40
                        )

                        await bot.send_photo(
                            chat_id=CHANNEL_ID,
                            photo=types.BufferedInputFile(
                                watermarked.getvalue(),
                                filename="watermarked.jpg"
                            ),
                            caption=caption
                        )
                    except Exception as e:
                        logger.error(f"Error processing photo watermark: {e}")
                        # Fallback to sending original photo
                        await bot.send_photo(chat_id=CHANNEL_ID, photo=media_ids[0], caption=caption)

            elif media_type == "video":
                await bot.send_video(chat_id=CHANNEL_ID, video=media_ids[0], caption=caption)
            elif media_type == "animation":
                await bot.send_animation(chat_id=CHANNEL_ID, animation=media_ids[0], caption=caption)
            elif media_type == "video_note":
                await bot.send_video_note(chat_id=CHANNEL_ID, video_note=media_ids[0])
            elif media_type == "voice":
                await bot.send_voice(chat_id=CHANNEL_ID, voice=media_ids[0], caption=caption)
            elif media_type == "audio":
                await bot.send_audio(chat_id=CHANNEL_ID, audio=media_ids[0], caption=caption)
            elif media_type == "document":
                await bot.send_document(chat_id=CHANNEL_ID, document=media_ids[0], caption=caption)

            # Update last post time
            post_tracker.update_last_post_time(datetime.now(TIMEZONE))

            # Notify user that their post was approved with specific details
            try:
                user_notification = (
                    f"✅ Your {media_type} submitted on {submission_time} has been approved and published!\n\n"
                )

                if caption:
                    # Include a preview of the caption to help identify the post
                    caption_preview = caption[:50] + "..." if len(caption) > 50 else caption
                    user_notification += f"Caption: \"{caption_preview}\""

                # Find the original message ID that contained this submission
                original_message_id = post_data.get("original_message_id")
                if original_message_id:
                    # Reply to the specific message
                    await bot.send_message(
                        user_id,
                        user_notification,
                        reply_to_message_id=original_message_id
                    )
                else:
                    # Fallback if message ID not found
                    await bot.send_message(user_id, user_notification)
            except Exception as e:
                logger.error(f"Error notifying user {user_id} about approval: {e}")

            # Set action message for admin notification
            action_msg = f"approved a {media_type} from user @{username} ({user_id})"

        else:  # Reject
            # Update post status
            pending_posts_manager.update_post_status(post_id, "rejected")

            # Record this rejected suggestion
            user_limits_manager.record_suggestion_result(user_id, False)

            # Notify user that their post was rejected with specific details
            try:
                user_notification = (
                    f"❌ Your {media_type} submitted on {submission_time} was not selected for publication.\n\n"
                )

                if caption:
                    # Include a preview of the caption to help identify the post
                    caption_preview = caption[:50] + "..." if len(caption) > 50 else caption
                    user_notification += f"Caption: \"{caption_preview}\""

                # Find the original message ID that contained this submission
                original_message_id = post_data.get("original_message_id")
                if original_message_id:
                    # Reply to the specific message
                    await bot.send_message(
                        user_id,
                        user_notification,
                        reply_to_message_id=original_message_id
                    )
                else:
                    # Fallback if message ID not found
                    await bot.send_message(user_id, user_notification)
            except Exception as e:
                logger.error(f"Error notifying user {user_id} about rejection: {e}")

            # Set action message for admin notification
            action_msg = f"rejected a {media_type} from user @{username} ({user_id})"

        # Update callback message to show action taken
        await callback_query.message.edit_reply_markup(reply_markup=None)

        try:
            # Try to edit the text (works for text messages)
            original_text = callback_query.message.text or ""
            await callback_query.message.edit_text(
                original_text + f"\n\n{'✅ APPROVED' if action == 'approve' else '❌ REJECTED'} by @{admin_info['username']}",
                parse_mode="HTML"
            )
        except Exception as e:
            # For media messages, we can only edit the caption
            try:
                original_caption = callback_query.message.caption or ""
                await callback_query.message.edit_caption(
                    caption=original_caption + f"\n\n{'✅ APPROVED' if action == 'approve' else '❌ REJECTED'} by @{admin_info['username']}",
                    parse_mode="HTML"
                )
            except Exception as e2:
                # If we can't edit caption either, send a new message
                logger.warning(f"Could not edit message or caption: {e2}")
                await callback_query.message.reply(
                    f"{'✅ Post APPROVED' if action == 'approve' else '❌ Post REJECTED'} by @{admin_info['username']}"
                )

        # Notify main admin and answer callback
        await notify_main_admin(admin_info, action_msg)
        await callback_query.answer(f"Post {action}d successfully!")

    except Exception as e:
        logger.error(f"Error processing suggestion action: {e}")
        await callback_query.answer("An error occurred. Please try again.", show_alert=True)


@dp.message(Command("add_admin"))
async def add_admin(message: Message):
    if message.from_user.id != MAIN_ADMIN_ID:
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


@dp.message(Command("stats"))
async def show_stats(message: Message):
    if not is_authorized(message.from_user.id):
        await message.reply("You are not authorized to use this command.")
        return

    all_stats = user_limits_manager.get_all_users_stats()

    stats_text = (
        f"📊 *Suggestion Statistics*\n\n"
        f"Total users: {all_stats['total_users']}\n"
        f"Total suggestions: {all_stats['total_suggestions']}\n"
        f"Approved: {all_stats['approved_suggestions']}\n"
        f"Rejected: {all_stats['rejected_suggestions']}\n\n"
    )

    if all_stats['top_users']:
        stats_text += "👑 *Top contributors*:\n"
        for i, user in enumerate(all_stats['top_users'], 1):
            stats_text += f"{i}. User {user['user_id']} - {user['approved']} approved posts\n"

    await message.reply(stats_text, parse_mode="Markdown")


@dp.message(Command("pending"))
async def list_pending_posts(message: Message):
    if not is_authorized(message.from_user.id):
        await message.reply("You are not authorized to use this command.")
        return

    pending_posts = pending_posts_manager.get_all_pending_posts()

    if not pending_posts:
        await message.reply("There are no pending posts.")
        return

    response = f"📝 There are {len(pending_posts)} pending posts waiting for review.\n\n"
    response += "Use /pending_detail [post_id] to see details about a specific post."

    # Create a keyboard with buttons for each pending post
    keyboard = InlineKeyboardBuilder()

    for post_id, post_data in pending_posts.items():
        media_type = post_data["media_type"]
        username = post_data["username"]
        submission_time = datetime.fromisoformat(post_data["timestamp"]).strftime("%d/%m %H:%M")

        # Add row with button for each post
        keyboard.row(InlineKeyboardButton(
            text=f"ID {post_id}: {media_type} from @{username} ({submission_time})",
            callback_data=f"view_post_{post_id}"
        ))

    await message.reply(response, reply_markup=keyboard.as_markup())


@dp.callback_query(lambda c: c.data.startswith('view_post_'))
async def view_pending_post(callback_query: types.CallbackQuery):
    if not is_authorized(callback_query.from_user.id):
        await callback_query.answer("You are not authorized to view pending posts.", show_alert=True)
        return

    post_id = int(callback_query.data.split('_')[2])
    post_data = pending_posts_manager.get_pending_post(post_id)

    if not post_data:
        await callback_query.answer("This post no longer exists.", show_alert=True)
        return

    # Forward original message to admin
    await send_post_to_admin(callback_query.from_user.id, post_id, post_data)
    await callback_query.answer("Post details sent.")


# Function to send post to admin with approve/reject buttons
async def send_post_to_admin(admin_id: int, post_id: int, post_data: dict):
    user_id = post_data["user_id"]
    username = post_data["username"]
    media_type = post_data["media_type"]
    media_ids = post_data["media_ids"]
    caption = post_data["caption"]
    media_group_id = post_data.get("media_group_id")
    timestamp = datetime.fromisoformat(post_data["timestamp"])

    # Create info message
    info_text = (
        f"<b>📨 Suggestion from:</b> @{username} (ID: {user_id})\n"
        f"<b>Submitted:</b> {timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"<b>Media type:</b> {media_type}\n"
        f"<b>Post ID:</b> {post_id}"
    )

    # Create approval buttons
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Approve", callback_data=f"approve_{post_id}"),
            InlineKeyboardButton(text="❌ Reject", callback_data=f"reject_{post_id}")
        ]
    ])

    # Send info message first
    await bot.send_message(admin_id, info_text, parse_mode="HTML")

    # Send the actual content
    try:
        if media_type == "photo":
            if media_group_id:  # Multiple photos in a group
                media_group = []
                for file_id in media_ids:
                    media = types.InputMediaPhoto(media=file_id)
                    if media_ids.index(file_id) == 0 and caption:
                        media.caption = caption
                    media_group.append(media)

                await bot.send_media_group(chat_id=admin_id, media=media_group)
                # Send approval buttons separately since they can't be attached to a media group
                await bot.send_message(
                    admin_id,
                    "👆 Use buttons below to approve or reject this media group 👆",
                    reply_markup=keyboard
                )
            else:
                await bot.send_photo(
                    chat_id=admin_id,
                    photo=media_ids[0],
                    caption=caption,
                    reply_markup=keyboard
                )
        elif media_type == "video":
            await bot.send_video(
                chat_id=admin_id,
                video=media_ids[0],
                caption=caption,
                reply_markup=keyboard
            )
        elif media_type == "animation":
            await bot.send_animation(
                chat_id=admin_id,
                animation=media_ids[0],
                caption=caption,
                reply_markup=keyboard
            )
        elif media_type == "document":
            await bot.send_document(
                chat_id=admin_id,
                document=media_ids[0],
                caption=caption,
                reply_markup=keyboard
            )
        elif media_type == "audio":
            await bot.send_audio(
                chat_id=admin_id,
                audio=media_ids[0],
                caption=caption,
                reply_markup=keyboard
            )
        elif media_type == "voice":
            await bot.send_voice(
                chat_id=admin_id,
                voice=media_ids[0],
                caption=caption,
                reply_markup=keyboard
            )
        elif media_type == "video_note":
            await bot.send_video_note(
                chat_id=admin_id,
                video_note=media_ids[0],
                reply_markup=keyboard
            )
    except Exception as e:
        logger.error(f"Error sending media to admin: {e}")
        await bot.send_message(
            admin_id,
            f"Error sending original media. Error: {str(e)}",
            reply_markup=keyboard
        )


@dp.message(Command("help"))
async def show_help(message: Message):
    user_id = message.from_user.id
    is_admin_user = is_authorized(user_id)

    if is_admin_user:
        help_text = """
<b>🔰 Admin Commands:</b>
/add_admin USER_ID - Add new administrator (main admin only)
/remove_admin USER_ID - Remove administrator (main admin only)
/list_admins - Show list of authorized administrators
/last_post - Check when the last post was made
/pending - Show pending posts waiting for review
/stats - Show suggestion statistics
/help - Show this help message

<b>📝 Workflow:</b>
1. When users send media to the bot, it will be submitted for review
2. Admins will receive suggested posts and can approve or reject them
3. Approved posts are published to the channel
4. Users will be notified of the decision
"""
    else:
        help_text = """
<b>📱 User Commands:</b>
/start - Start the bot
/help - Show this help message
/status - Check your suggestion limits and status

<b>📝 How to submit content:</b>
1. Simply send photos, videos, documents or other media to this bot
2. Your submission will be reviewed by our admins
3. If approved, your content will be posted to our channel
4. You'll get a notification about the decision

<b>⚠️ Limits:</b>
- Maximum {max_per_day} submissions per day
- {cooldown} minute cooldown between submissions
""".format(max_per_day=MAX_SUGGESTIONS_PER_DAY, cooldown=SUGGESTION_COOLDOWN_SECONDS // 60)

    await message.reply(help_text, parse_mode="HTML")


@dp.message(Command("start"))
async def start_command(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or f"user_id: {user_id}"

    # Set commands for this user
    await set_commands_for_user(user_id, is_admin=is_authorized(user_id))

    if is_authorized(user_id):
        await message.reply(
            f"Welcome, admin! You can send media directly to be posted or use /help to see available commands."
        )
    else:
        await message.reply(
            f"👋 Welcome, {username}!\n\n"
            f"You can submit content to our channel by sending photos, videos or other media to this bot.\n"
            f"Our team will review your submission and publish it if approved.\n\n"
            f"Use /help to learn more about how to use this bot."
        )


@dp.message(Command("status"))
async def status_command(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or f"User_{user_id}"

    # Get user stats
    stats = user_limits_manager.get_user_stats(user_id)

    status_text = (
        f"📊 <b>Your Status, {username}</b>\n\n"
        f"Suggestions today: {stats.get('suggestions_today')}/{MAX_SUGGESTIONS_PER_DAY}\n"
        f"Remaining today: {stats.get('suggestions_remaining')}\n\n"
        f"Total submissions: {stats.get('total_suggestions')}\n"
        f"Approved: {stats.get('approved_suggestions')}\n"
        f"Rejected: {stats.get('rejected_suggestions')}\n\n"
    )

    # Calculate approval rate
    if stats['total_suggestions'] > 0:
        approval_rate = (stats['approved_suggestions'] / stats['total_suggestions']) * 100
        status_text += f"Approval rate: {approval_rate:.1f}%\n"

    # Add cooldown info if applicable
    can_suggest, reason = user_limits_manager.can_suggest(user_id)
    if not can_suggest:
        status_text += f"\n⏳ {reason}"
    else:
        status_text += "\n✅ You can submit content now!"

    await message.reply(status_text, parse_mode="HTML")


# Handler for media groups
async def process_media_group(user_id: int, username: str, media_group_id: str,
                              media_type: str, file_id: str, message_id: Optional[int] = None, caption: Optional[str] = None):
    """Process and collect media group items"""
    current_time = time.time()

    # Initialize the group if it doesn't exist
    if media_group_id not in media_group_collector:
        media_group_collector[media_group_id] = {
            "user_id": user_id,
            "username": username,
            "media_ids": [],
            "media_type": media_type,
            "caption": caption,
            "last_update": current_time,
            "first_message_id": message_id,
            "complete": False
        }

    # Add this media to the group
    if file_id not in media_group_collector[media_group_id]["media_ids"]:
        media_group_collector[media_group_id]["media_ids"].append(file_id)

    # Update the last activity time
    media_group_collector[media_group_id]["last_update"] = current_time

    # If there's a caption, and we don't have one yet, save it
    if caption and not media_group_collector[media_group_id]["caption"]:
        media_group_collector[media_group_id]["caption"] = caption

    # Mark the group as having an update
    return media_group_collector[media_group_id]


# Function to handle a complete media group
async def handle_complete_media_group(media_group_id: str):
    """Process a complete media group"""
    if media_group_id not in media_group_collector:
        return

    group_data = media_group_collector[media_group_id]

    # Mark as complete to prevent duplicate processing
    if group_data["complete"]:
        return

    group_data["complete"] = True

    user_id = group_data["user_id"]
    username = group_data["username"]

    # Check if this user can make a suggestion
    can_suggest, reason = user_limits_manager.can_suggest(user_id)
    if not can_suggest:
        try:
            await bot.send_message(user_id, f"⚠️ Suggestion limit reached. {reason}")
        except Exception as e:
            logger.error(f"Error notifying user about limit: {e}")
        return

    # Record the suggestion
    user_limits_manager.record_suggestion(user_id)

    # Generate a unique post ID
    post_id = int(time.time() * 1000) % 1000000000

    # Add to pending posts
    pending_posts_manager.add_pending_post(
        post_id=post_id,
        user_id=user_id,
        username=username,
        media_ids=group_data["media_ids"],
        media_type=group_data["media_type"],
        caption=group_data["caption"],
        media_group_id=media_group_id,
        original_message_id=group_data.get("first_message_id")  # Add this line
    )

    # Notify user
    try:
        await bot.send_message(
            user_id,
            "✅ Your media group has been submitted for review. "
            "You'll be notified when an admin reviews it."
        )
    except Exception as e:
        logger.error(f"Error notifying user about submission: {e}")

    # Notify admins about the new suggestion
    admins = load_admins()
    admin_ids = [MAIN_ADMIN_ID] + list(admins.keys())

    # Remove duplicates
    admin_ids = list(set(admin_ids))

    # Notify each admin
    for admin_id in admin_ids:
        await send_post_to_admin(admin_id, post_id, pending_posts_manager.get_pending_post(post_id))

    # Clean up the collector
    del media_group_collector[media_group_id]


# Background task to process complete media groups
async def media_group_cleanup_task():
    """Background task to clean up and process media groups that are complete but haven't been processed"""
    while True:
        current_time = time.time()
        groups_to_process = []

        # Find groups that haven't been updated in 2 seconds (likely complete)
        for media_group_id, group_data in media_group_collector.items():
            if not group_data["complete"] and current_time - group_data["last_update"] > 2:
                groups_to_process.append(media_group_id)

        # Process complete groups
        for media_group_id in groups_to_process:
            await handle_complete_media_group(media_group_id)

        # Sleep for a short time
        await asyncio.sleep(1)


# Main message handler for all content
@dp.message()
async def handle_message(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or f"User_{user_id}"

    # Set commands for user if they haven't been set
    is_admin_user = is_authorized(user_id)
    await set_commands_for_user(user_id, is_admin=is_admin_user)

    # Check if it's from an admin
    if is_admin_user:
        # For admins, we post directly to the channel
        await handle_admin_message(message)
    else:
        # For regular users, we queue for review
        await handle_user_suggestion(message)


async def handle_admin_message(message: Message):
    """Handle direct posting from admins"""
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
        await message.reply(f"Please send a message with media content to post to the channel.")
        return

    try:
        # Create user info dict for notification
        user_info = {
            'id': message.from_user.id,
            'username': message.from_user.username or f"User_{message.from_user.id}"
        }

        # Check if it's part of a media group
        if message.media_group_id:
            # Let admin know we're collecting the group
            if message.media_group_id not in media_group_collector:
                await message.reply("Collecting media group... Will post when complete.")

            # Process as part of media group
            await process_media_group(
                user_id=user_info['id'],
                username=user_info['username'],
                media_group_id=message.media_group_id,
                media_type=media_type,
                file_id=media.file_id,
                caption=message.caption
            )

            # We don't immediately post media groups
            return

        # Post immediately for single media
        if media_type == "photo":
            try:
                # Download the photo
                file = await bot.get_file(media.file_id)
                photo_io = await bot.download_file(file.file_path)
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

        post_tracker.update_last_post_time(datetime.now(TIMEZONE))
        await message.reply("Message posted successfully.")
        await notify_main_admin(
            user_info,
            f"posted a {media_type}"
        )

    except Exception as e:
        logger.error(f"Error processing admin message: {e}")
        await message.reply(f"Error processing your message: {str(e)}")


async def handle_user_suggestion(message: Message):
    """Handle suggestions from regular users"""
    user_id = message.from_user.id
    username = message.from_user.username or f"User_{user_id}"

    # Ignore commands
    if message.text and message.text.startswith('/'):
        return

    # Check if message contains media
    media = None
    media_type = None
    file_id = None

    if message.photo:
        media = message.photo[-1]
        media_type = "photo"
        file_id = media.file_id
    elif message.video:
        media = message.video
        media_type = "video"
        file_id = media.file_id
    elif message.animation:
        media = message.animation
        media_type = "animation"
        file_id = media.file_id
    elif message.video_note:
        media = message.video_note
        media_type = "video_note"
        file_id = media.file_id
    elif message.audio:
        media = message.audio
        media_type = "audio"
        file_id = media.file_id
    elif message.voice:
        media = message.voice
        media_type = "voice"
        file_id = media.file_id
    elif message.document:
        media = message.document
        media_type = "document"
        file_id = media.file_id
    else:
        await message.reply(
            "Please send media content (photos, videos, etc.) to submit for review. "
            "Use /help to learn more about this bot."
        )
        return

    # If it's a media group, handle it specially
    if message.media_group_id:
        group_data = await process_media_group(
            user_id=user_id,
            username=username,
            media_group_id=message.media_group_id,
            media_type=media_type,
            file_id=file_id,
            caption=message.caption,
            message_id=message.message_id
        )

        # If this is the first item in the group, inform user
        if len(group_data["media_ids"]) == 1:
            await message.reply("Collecting your media group... Please send all items.")

        # Media groups are processed by the background task
        return

    # For single media, check if user can suggest
    can_suggest, reason = user_limits_manager.can_suggest(user_id)
    if not can_suggest:
        await message.reply(f"⚠️ {reason}")
        return

    # Record the suggestion
    user_limits_manager.record_suggestion(user_id)

    # Generate a unique post ID
    post_id = int(time.time() * 1000) % 1000000000

    # Add to pending posts
    pending_posts_manager.add_pending_post(
        post_id=post_id,
        user_id=user_id,
        username=username,
        media_ids=[file_id],
        media_type=media_type,
        caption=message.caption,
        original_message_id=message.message_id  # Add this line
    )

    # Notify user
    await message.reply(
        "✅ Your post has been submitted for review. "
        "You'll be notified when an admin reviews it."
    )

    # Notify admins about the new suggestion
    admins = load_admins()
    admin_ids = [MAIN_ADMIN_ID] + list(admins.keys())

    # Remove duplicates
    admin_ids = list(set(admin_ids))

    # Notify each admin
    for admin_id in admin_ids:
        await send_post_to_admin(admin_id, post_id, pending_posts_manager.get_pending_post(post_id))


async def main():
    try:
        # Create task for media group processing
        asyncio.create_task(media_group_cleanup_task())

        # Set default commands (empty) for all users
        try:
            await bot.delete_my_commands()
        except Exception as e:
            logger.warning(f"Error deleting default commands: {e}")

        # Set commands for main admin
        await set_commands_for_user(MAIN_ADMIN_ID, is_admin=True)

        # Set commands for existing admins
        admins = load_admins()
        for admin_id in admins:
            await set_commands_for_user(admin_id, is_admin=True)

        # Start polling
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"Error in main: {e}")

@dp.message_handler(content_types=types.ContentTypes.ANY)
async def get_channel_id(msg: types.Message):
    if msg.forward_from_chat:
        await msg.answer(f"ID канала: <code>{msg.forward_from_chat.id}</code>")
    else:
        await msg.answer("Это не пересланное сообщение из канала")
if __name__ == '__main__':
    asyncio.run(main())
