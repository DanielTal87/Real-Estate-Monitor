# 🚀 Quick Start Guide

Get your Real Estate Monitor running in **5 minutes**!

## Step 1: Setup (2 minutes)

```bash
# Run the setup script
python3 setup.py

# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

## Step 2: Configure (2 minutes)

Edit `.env` file with your preferences:

```bash
# Essential settings
CITIES=תל אביב-יפו,רמת גן,גבעתיים
MAX_PRICE=8000
MIN_ROOMS=2.5
MIN_SIZE_SQM=65

# Optional: Add Telegram for notifications
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

## Step 3: Run (1 minute)

```bash
python main.py
```

Open your browser to: **http://127.0.0.1:8000**

## That's It! 🎉

The system is now:
- ✅ Scraping listings every 15 minutes
- ✅ Calculating deal scores
- ✅ Detecting price drops
- ✅ Available via web dashboard

---

## Optional: Telegram Notifications

### Get Bot Token:
1. Message [@BotFather](https://t.me/botfather)
2. Send `/newbot`
3. Follow instructions
4. Copy token

### Get Chat ID:
1. Message your bot
2. Visit: `https://api.telegram.org/bot<TOKEN>/getUpdates`
3. Find your `chat_id`

### Test:
```bash
python -c "import asyncio; from database import init_db; from telegram_notifier import send_test_notification; from config import settings; asyncio.run(send_test_notification(init_db(settings.database_url)[1]()))"
```

---

## Troubleshooting

**Can't install dependencies?**
```bash
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

**Playwright not working?**
```bash
playwright install chromium
```

**Port 8000 already in use?**
Change `DASHBOARD_PORT=8001` in `.env`

**Need help?**
Check `real_estate_monitor.log` for errors

---

## Using the Dashboard

### Main Features:

1. **Filter Listings**
   - By city, neighborhood, status
   - By minimum deal score
   - By price range

2. **Sort Listings**
   - By deal score (default)
   - By price (low to high / high to low)
   - By date (newest first)

3. **Manage Listings**
   - ❤️ Like (mark as interested)
   - ❌ Hide (mark as not interested)
   - 📞 Contacted (mark as contacted)
   - 👁️ View (open on source site)
   - 💬 WhatsApp (contact seller)

### Understanding Deal Scores:

- **80-100**: 🔥 Excellent deal - Act fast!
- **60-79**: 👍 Good listing - Worth considering
- **Below 60**: 😐 Average - May not meet all criteria

---

## Pro Tips

1. **Start Broad**: Use relaxed filters initially
2. **Refine**: Adjust based on what you see
3. **Act Fast**: High-score deals go quickly
4. **Check Daily**: New listings appear constantly
5. **Use WhatsApp**: Fastest way to contact sellers

---

## What's Next?

- Monitor the dashboard for new listings
- Respond to Telegram notifications
- Adjust filters in `.env` as needed
- Keep the system running 24/7

**Happy House Hunting! 🏡**
