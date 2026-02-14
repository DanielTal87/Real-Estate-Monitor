# 🏠 Real Estate Monitor for Central Israel

**Fully autonomous local real estate monitoring system** that scrapes, analyzes, and notifies you about apartment listings from Yad2, Madlan, and Facebook Marketplace.

---

## 🎯 Features

### Core Functionality

- ✅ **Automated Scraping** from Yad2, Madlan & Facebook Marketplace
- ✅ **Intelligent Deal Scoring** (0-100 based on price, features, recency)
- ✅ **Price Drop Detection** - Automatically re-surfaces good deals
- ✅ **Cross-Site Duplicate Detection** - Avoid seeing the same listing twice
- ✅ **Telegram Notifications** - Get instant alerts for hot deals
- ✅ **Web Dashboard** - Beautiful UI to browse and manage listings
- ✅ **Smart Filtering** - Must-have, nice-to-have, and deal-breakers
- ✅ **Neighborhood Analytics** - Compare prices to local averages
- ✅ **24/7 Local Operation** - No cloud, no subscriptions

### Dashboard Features

- 📊 Real-time statistics (new today, high scores)
- 🔍 Advanced filtering (city, neighborhood, score, price)
- ❤️ Like/Hide/Contacted status tracking
- 📈 Price history charts
- 💬 One-click WhatsApp contact
- 🎨 Responsive Bootstrap UI

---

## 📋 Prerequisites

- **Python 3.9+**
- **Playwright** (for browser automation)
- **SQLite** (included with Python)
- **Telegram Bot** (optional, for notifications)

---

## 🚀 Installation

### 1. Clone or Download This Project

```bash
cd real-estate-monitor
```

### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Install Playwright Browsers

```bash
playwright install chromium
```

### 5. Configure Environment

```bash
cp .env.example .env
nano .env  # Edit with your preferences
```

---

## ⚙️ Configuration Guide

### Basic Configuration (.env file)

```bash
# Search Filters
CITIES=תל אביב-יפו,רמת גן,גבעתיים,הרצליה
MAX_PRICE=8000
MIN_ROOMS=2.5
MIN_SIZE_SQM=65

# High Priority Neighborhoods (get notifications even at lower scores)
HIGH_PRIORITY_NEIGHBORHOODS=רמת אביב,בבלי,יד אליהו

# Deal Breakers
EXCLUDE_GROUND_FLOOR=true
REQUIRE_ELEVATOR_ABOVE_FLOOR=2
REQUIRE_PARKING=false

# Preferences (affects deal score)
PREFER_BALCONY=true
PREFER_PARKING=true
PREFER_ELEVATOR=true

# Scraping Intervals (minutes)
SCRAPING_INTERVAL_MINUTES=15
YAD2_INTERVAL_MINUTES=15
MADLAN_INTERVAL_MINUTES=15
FACEBOOK_INTERVAL_MINUTES=20
```

### Telegram Setup (Optional)

1. **Create a Telegram Bot**:
   - Message [@BotFather](https://t.me/botfather) on Telegram
   - Send `/newbot` and follow instructions
   - Copy the bot token

2. **Get Your Chat ID**:
   - Message your bot
   - Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
   - Find your `chat_id` in the response

3. **Add to .env**:

```bash
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

### Facebook Setup (Advanced)

Facebook requires authentication. You need to extract your cookies:

1. **Install Cookie Editor Extension** (Chrome/Firefox)
2. **Login to Facebook**
3. **Export Cookies** as JSON
4. **Save as** `facebook_cookies.json` in project root

---

## 🎬 Running the System

### Start Everything

```bash
python main.py
```

This starts:

1. ✅ Web dashboard at `http://127.0.0.1:8000`
2. ✅ Automated scraping every 15 minutes
3. ✅ Telegram notifications (if configured)

### Dashboard URL

Open your browser:

```
http://127.0.0.1:8000
```

### Test Telegram

```bash
python -c "import asyncio; from database import init_db; from telegram_notifier import send_test_notification; from config import settings; asyncio.run(send_test_notification(init_db(settings.database_url)[1]()))"
```

---

## 📊 Using the Dashboard

### Main Page

- **View Listings**: All scraped listings with scores
- **Filter**: By city, neighborhood, status, score
- **Sort**: By score, price, date
- **Actions**:
  - ❤️ Like (mark as interested)
  - ❌ Hide (mark as not interested)
  - 📞 Contacted (mark as contacted)
  - 👁️ View (open listing on source site)
  - 💬 WhatsApp (direct contact)

### Statistics

- Total listings in database
- New listings today
- High-score count
- Active filters indicator

### Listing Detail Page

- Full description and images
- Price history chart
- Neighborhood price comparison
- All features and contact info

---

## 🧠 How Deal Scoring Works

Each listing gets a score from 0-100 based on:

### Price Competitiveness (40 points)

- Compared to neighborhood average
- 30%+ below average = 40 points
- At average = 25 points
- 20%+ above average = 5 points

### Features Match (30 points)

- Parking (if preferred): 10 points
- Balcony (if preferred): 8 points
- Elevator (if preferred): 7 points
- Top floor (if preferred): 5 points

### Recency (15 points)

- Today: 15 points
- 1-2 days: 12 points
- 3-5 days: 9 points
- Older: decreases to 1 point

### Price Trend (15 points)

- 10%+ price drop: 15 points
- 5-10% drop: 12 points
- 2-5% drop: 9 points
- Price increase: 2 points

---

## 🔔 Notifications

Telegram notifications are sent when:

1. **New Listing** with deal score ≥ 80
2. **New Listing** in high-priority neighborhood
3. **Price Drop** ≥ 3%

Notifications include:

- 🏠 Property details
- 💰 Price and price/m²
- 🎯 Deal score
- 📍 Location
- 🔗 Direct link
- 💬 WhatsApp contact button

---

## 📁 Project Structure

```
real-estate-monitor/
├── main.py                 # Application entry point
├── config.py              # Configuration management
├── database.py            # Database models
├── deal_score.py          # Deal scoring algorithm
├── listing_processor.py   # Listing processing logic
├── telegram_notifier.py   # Telegram notifications
├── scheduler.py           # Scraping scheduler
├── dashboard.py           # Web dashboard (FastAPI)
├── scrapers/
│   ├── base_scraper.py    # Base scraper class
│   ├── yad2_scraper.py    # Yad2 scraper
│   ├── madlan_scraper.py  # Madlan scraper
│   └── facebook_scraper.py # Facebook scraper
├── templates/
│   └── index.html         # Dashboard template
├── requirements.txt       # Python dependencies
├── .env                   # Configuration (create from .env.example)
├── .env.example          # Example configuration
├── real_estate.db        # SQLite database (auto-created)
└── README.md             # This file
```

---

## 🗄️ Database Schema

### Listings Table

- Property details (address, rooms, size, floor)
- Price and price history
- Features (parking, elevator, balcony)
- Deal score
- Status (unseen/interested/not_interested/contacted)
- Images
- Contact info

### Supporting Tables

- `price_history` - Track price changes
- `description_history` - Track description changes
- `notifications` - Prevent duplicate notifications
- `scraping_state` - Track scraper status
- `neighborhood_stats` - Price averages by area

---

## 🛠️ Maintenance & Troubleshooting

### Check Logs

```bash
tail -f real_estate_monitor.log
```

### Reset Database

```bash
rm real_estate.db
python main.py  # Will recreate
```

### Update Scrapers

If a website changes its HTML structure, you'll need to update the scraper selectors in `scrapers/` directory.

### Common Issues

**Scraper fails:**

- Check if website is accessible
- Verify HTML selectors haven't changed
- Check logs for specific errors

**No Telegram notifications:**

- Verify bot token and chat ID
- Send test notification (see above)
- Check logs for errors

**Listings not appearing:**

- Check filters in .env
- Verify cities are spelled correctly
- Check scraper logs

---

## 🔒 Privacy & Ethics

This system is for **personal use only**:

✅ **Allowed**:

- Running locally for apartment hunting
- Notifying yourself about listings
- Storing data locally

❌ **Not Allowed**:

- Sharing scraped data publicly
- Selling or commercializing data
- Overloading websites with requests
- Violating terms of service

**Rate Limiting**: Built-in delays and limits to be respectful to source sites.

---

## 🎯 Pro Tips

1. **Start Broad**: Begin with wider filters, then narrow down
2. **Monitor Scores**: Adjust preferences to match your priorities
3. **Check Daily**: Even automated, check dashboard for new matches
4. **WhatsApp Ready**: Have template messages ready
5. **Be Quick**: Good deals go fast - act on high scores immediately

---

## 🚀 Future Enhancements

Potential additions:

- [ ] Email notifications
- [ ] More sources (HomeLess, etc.)
- [ ] Advanced ML price predictions
- [ ] Map view of listings
- [ ] Chrome extension
- [ ] Mobile app

---

## 📝 License

This is personal software for individual use. Not licensed for commercial distribution.

---

## 🙏 Credits

Built with:

- Python 3.9+
- FastAPI - Web framework
- Playwright - Browser automation
- SQLAlchemy - Database ORM
- Bootstrap - UI framework
- python-telegram-bot - Notifications

---

## 📞 Support

This is a personal project. For issues:

1. Check logs first
2. Review configuration
3. Verify prerequisites
4. Search existing issues

**Happy House Hunting! 🏡**
