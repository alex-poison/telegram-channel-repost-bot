# ChannelMaster: Telegram Content Management Bot

A powerful Telegram bot for managing content submissions, approval workflows, and channel publishing. Enables both direct admin posting and community-contributed content with moderation.

## Features

### Admin Features
- Multi-admin support with hierarchical permissions
- Manage submissions from community members
- Approve or reject suggested content with one click
- Post directly to channel (bypassing approval workflow)
- Admin notifications for important actions
- Comprehensive statistics and management tools
- Media group support (multiple photos/videos in one post)

### User Features
- Submit content for channel publication
- Receive notifications on submission approval/rejection
- Track personal submission statistics
- Fair rate limiting to prevent spam

### Media Support
- Photos (with automatic watermarking)
- Videos
- GIFs/Animations
- Documents
- Audio files
- Voice messages
- Media groups/albums

## New Commands

### Admin Commands
- All previous commands, plus:
- `/pending` - View submissions awaiting approval
- `/stats` - View submission statistics

### User Commands
- `/start` - Begin using the bot
- `/help` - View available commands
- `/status` - Check submission limits and statistics

## Installation & Configuration

### Using Docker (recommended)
1. Clone the repository:
```bash
git clone https://github.com/yourusername/channelmaster.git
cd channelmaster
```

2. Create `.env` file with your configuration:
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
Follow the same steps as before, using the updated requirements.

## Usage Workflow

### For Users
1. Send media content to the bot
2. Receive confirmation that submission is pending review
3. Get notified when admins approve or reject your content

### For Admins
1. Receive notifications about new submissions
2. Review content with convenient approve/reject buttons
3. Approved content is automatically posted to the channel
4. Alternatively, send media directly to post immediately

## File Structure
```
.
├── bot.py              # Main bot code
├── requirements.txt    # Python dependencies
├── Dockerfile          # Docker configuration
├── docker-compose.yml  # Docker Compose configuration
├── .env                # Environment variables
└── data/               # Data storage directory
    ├── admins.json        # Admins list
    ├── pending_posts.json # Pending submissions
    └── user_limits.json   # User rate limits and stats
```
