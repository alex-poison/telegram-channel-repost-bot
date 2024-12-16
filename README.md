# Telegram Channel Repost Bot

A simple Telegram bot that allows authorized administrators to repost media content to a specific channel. Built with Python and aiogram.

## Features

- Multi-admin support with authorization system
- Support for various media types:
  - Photos
  - Videos
  - GIFs/Animations
- Admin management commands
- Main admin notifications about others' activities
- Clean reposts (no forwarding metadata)

## Prerequisites

- Docker and Docker Compose (for Docker installation)
- OR Python 3.11+ (for manual installation)
- Telegram Bot Token from [@BotFather](https://t.me/BotFather)
- Channel administrator rights for your bot

## Installation

### Using Docker (recommended)

1. Clone the repository:
```bash
git clone https://github.com/TurboKach/telegram-channel-repost-bot.git
cd telegram-channel-repost-bot
```

2. Create `.env` file:
```env
BOT_TOKEN=your_bot_token
CHANNEL_ID=your_channel_id
MAIN_ADMIN_ID=your_user_id
TIMEZONE=UTC
```

3. Run with Docker Compose:
```bash
docker-compose up -d
```

### Manual Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/telegram-channel-repost-bot.git
cd telegram-channel-repost-bot
```

2. Install requirements:
```bash
pip install -r requirements.txt
```

3. Create `.env` file as shown above

4. Run the bot:
```bash
python bot.py
```

## Configuration

- `BOT_TOKEN`: Your Telegram bot token
- `CHANNEL_ID`: ID of your Telegram channel (with minus sign if it's public)
- `MAIN_ADMIN_ID`: Telegram user ID of the main administrator
- `TIMEZONE`: Your timezone (default: UTC)

## Commands

### Main Admin Commands
- `/add_admin USER_ID` - Add new administrator
- `/remove_admin USER_ID` - Remove administrator
- `/list_admins` - Show list of authorized administrators
- `/last_post` - Check when the last post was made
- `/help` - Show help message

### Regular Admin Commands
- `/last_post` - Check when the last post was made
- `/help` - Show help message

## Usage

1. Add the bot as administrator to your channel
2. Send or forward media (photos, videos, GIFs) to the bot
3. Bot will post the media to your channel immediately
4. Main admin will receive notifications about other admins' posts

## File Structure
```
.
├── bot.py              # Main bot code
├── requirements.txt    # Python dependencies
├── Dockerfile         # Docker configuration
├── docker-compose.yml # Docker Compose configuration
├── .env               # Environment variables
└── admins.json        # Admins storage
```

## Dependencies

- aiogram==3.15.0
- python-dotenv==1.0.0
- pytz==2024.1

## Docker Volumes

The bot uses a persistent volume for `admins.json` to maintain the list of authorized administrators across container restarts.

## Docker Commands

Start the bot:
```bash
docker-compose up -d
```

View logs:
```bash
docker-compose logs -f
```

Stop the bot:
```bash
docker-compose down
```

Update the bot:
```bash
docker-compose pull  # If using prebuilt image
# or
docker-compose up -d --build  # If building locally
```

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.