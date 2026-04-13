# BUPA Appointment Bot

An automated bot that monitors BUPA's appointment booking system and notifies you via Telegram when earlier appointments become available. It uses browser automation to check for slots and can book them automatically if configured.

## Features

- **Automated Monitoring**: Continuously checks for earlier appointment slots
- **Telegram Notifications**: Real-time alerts for status updates, errors, and successful bookings
- **Browser Automation**: Uses Playwright with Chromium for reliable web interaction
- **Docker Containerized**: Easy deployment with health checks and monitoring
- **Configurable Scheduling**: Randomized intervals to avoid detection
- **Screenshot Capture**: Saves visual evidence of available slots
- **Graceful Shutdown**: Proper signal handling for clean stops

## Prerequisites

- Docker and Docker Compose
- Telegram Bot Token (from @BotFather)
- BUPA account credentials

## Quick Start

1. **Clone the repository**:
   ```bash
   git clone https://github.com/MidhunRaj12/bupa-bot.git
   cd bupa-bot
   ```

2. **Configure environment**:
   - Copy `envs/person_a.env` and edit with your details
   - Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`
   - Adjust `CHECK_INTERVAL_MIN/MAX` for check frequency

3. **Run the bot**:
   ```bash
   docker-compose up -d --build
   ```

4. **Check status**:
   - Health: `http://localhost:8000/`
   - Logs: `docker-compose logs -f bot_person_a`
   - Status: `docker-compose ps`

## Configuration

### Environment Variables

Create a `.env` file in `envs/` directory:

```env
# BUPA Account Details
HAP_ID=your_hap_id
EMAIL=your_email@example.com
GIVEN_NAMES=Your First Name
FAMILY_NAME=Your Last Name
DOB=DD/MM/YYYY
PREFERRED_LOCATION=Your Location

# Current Appointment
CURRENT_APPT_DATE=DD/MM/YYYY

# Telegram Notifications
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
TELEGRAM_CHAT_ID=your_chat_id

# Scheduling (minutes)
CHECK_INTERVAL_MIN=15
CHECK_INTERVAL_MAX=45

# Runtime
CONTAINER_NAME=bot_person_a
HEADLESS=true
```

### Multiple Users

To run multiple instances:

1. Copy `bot_person_a` service in `docker-compose.yml`
2. Rename to `bot_person_b`
3. Create `envs/person_b.env` with different credentials
4. Update `CONTAINER_NAME` and ports if needed

## Usage

### Starting the Bot

```bash
# Build and start
docker-compose up -d --build

# Start existing
docker-compose up -d

# View logs
docker-compose logs -f bot_person_a
```

### Health Monitoring

- **Health Check**: `http://localhost:8000/` returns "OK"
- **Container Status**: `docker-compose ps` shows health status
- **Logs**: Check for errors and notifications

### Stopping the Bot

```bash
# Graceful stop with notification
docker-compose down

# Force stop
docker-compose kill
```

## Project Structure

```
bupa-bot/
├── app/
│   ├── main.py          # Entry point with scheduler
│   ├── bot.py           # Core automation logic
│   ├── config.py        # Configuration management
│   ├── notify.py        # Telegram notifications
│   └── requirements.txt # Python dependencies
├── envs/
│   └── person_a.env     # Environment variables
├── logs/                # Runtime logs and screenshots
├── docker-compose.yml   # Container orchestration
├── Dockerfile           # Multi-stage build
└── README.md           # This file
```

## Development

### Local Setup

1. Install dependencies:
   ```bash
   pip install -r app/requirements.txt
   playwright install chromium
   ```

2. Set environment variables or create `.env`

3. Run locally:
   ```bash
   python -m app.main
   ```

### Building

```bash
# Clean build
docker-compose build --no-cache

# Quick rebuild
docker-compose build
```

## Troubleshooting

### Common Issues

1. **Import errors**: Ensure virtual environment is activated
2. **Browser fails**: Check `playwright install chromium` ran
3. **No notifications**: Verify `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`
4. **Container won't start**: Check logs with `docker-compose logs`
5. **Health check fails**: Ensure port 8000 is accessible

### Logs

```bash
# View all logs
docker-compose logs bot_person_a

# Follow logs
docker-compose logs -f bot_person_a

# Last 50 lines
docker-compose logs --tail=50 bot_person_a
```

### Debugging

- Screenshots are saved to `logs/screenshots/`
- Check `logs/bot_person_a.log` for detailed logs
- Use `docker-compose exec bot_person_a bash` for shell access

## Security Notes

- Never commit `.env` files
- Use strong, unique passwords
- Monitor logs for sensitive data exposure
- Keep dependencies updated

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Submit a pull request

## License

This project is for educational purposes. Use responsibly and in accordance with BUPA's terms of service.

## Support

For issues:
1. Check logs and screenshots
2. Verify configuration
3. Test with local run
4. Open an issue with details
