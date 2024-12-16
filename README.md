# Telegram Channel Scheduler Bot

A Docker-containerized Telegram bot that helps manage media content scheduling in Telegram channels. The bot automatically schedules posts at regular intervals, removes forwarding metadata, and maintains a smart posting queue.

## Features

- **Smart Scheduling**: 
  - Posts immediately if queue is empty
  - Schedules to next half-hour slot if queue exists
  - Maintains posting schedule from 06:00 to 01:00 next day
  - Automatically adjusts scheduling to maintain consistent intervals

- **Media Support**:
  - Photos
  - Videos
  - GIFs/Animations

- **Authorization System**:
  - Multi-admin support
  - JSON-based persistent storage
  - Admin management commands

- **Clean Content**:
  - Automatically removes forwarding metadata
  - Strips captions and other message attributes

## Prerequisites

- Docker and Docker Compose
- Telegram Bot Token (from [@BotFather](https://t.me/BotFather))
- Channel administrator rights for your bot
- Python 3.11+ (if running without Docker)

## Quick Start

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/telegram-channel-scheduler-bot.git
   cd telegram-channel-scheduler-bot
   ```

2. Create `.env` file:
   ```env
   BOT_TOKEN=your_bot_token
   CHANNEL_ID=your_channel_id
   MAIN_ADMIN_ID=your_admin_id
   TIMEZONE=UTC
   ```

3. Run with Docker Compose:
   ```bash
   docker-compose up -d
   ```

## Environment Variables

- `BOT_TOKEN`: Your Telegram bot token
- `CHANNEL_ID`: ID of your Telegram channel (with minus sign if it's public)
- `MAIN_ADMIN_ID`: Telegram user ID of the main administrator
- `TIMEZONE`: Timezone for scheduling (default: UTC)

## Admin Commands

- `/add_admin USER_ID` - Add new administrator (main admin only)
- `/remove_admin USER_ID` - Remove administrator (main admin only)
- `/list_admins` - Show list of authorized administrators

## Usage

1. Add the bot as administrator to your channel
2. Forward or send media files (photos, videos, GIFs) to the bot
3. Bot will either:
   - Post immediately if no queue and within allowed hours (06:00-01:00)
   - Schedule to next available half-hour slot
4. Bot will confirm scheduling with timestamp

## Development

### Running without Docker

1. Install requirements:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the bot:
   ```bash
   python bot.py
   ```

### Project Structure
```
.
├── bot.py              # Main bot logic
├── requirements.txt    # Python dependencies
├── Dockerfile         # Docker configuration
├── docker-compose.yml # Docker Compose configuration
├── admins.json        # Persistent storage for admins
└── .env              # Environment variables
```

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [aiogram](https://github.com/aiogram/aiogram) - Telegram Bot framework
- [python-telegram-bot](https://python-telegram-bot.org/) - Telegram Bot API wrapper

## Contact

Project Link: [https://github.com/TurboKach/telegram-channel-scheduler-bot.git](https://github.com/TurboKach/telegram-channel-scheduler-bot.git)
