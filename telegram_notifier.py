from telegram import Bot
from telegram.error import TelegramError
from sqlalchemy.orm import Session
from database import Listing, Notification
from config import settings
from deal_score import DealScoreCalculator
from datetime import datetime, timedelta
import logging
from typing import Optional
import asyncio

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Send notifications via Telegram"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.deal_calculator = DealScoreCalculator(db_session)
        
        if not settings.is_telegram_enabled():
            logger.warning("Telegram is not configured. Notifications disabled.")
            self.bot = None
            self.chat_id = None
        else:
            self.bot = Bot(token=settings.telegram_bot_token)
            self.chat_id = settings.telegram_chat_id
    
    async def notify_new_listing(self, listing: Listing) -> bool:
        """Send notification for a new listing"""
        if not self.bot:
            return False
        
        # Check if should notify
        if not self._should_notify(listing, 'new_listing'):
            return False
        
        # Check if already notified
        if self._already_notified(listing, 'new_listing'):
            return False
        
        # Build message
        message = self._build_listing_message(listing, notification_type='new_listing')
        
        # Send notification
        success = await self._send_message(message)
        
        if success:
            self._record_notification(listing, 'new_listing', message)
        
        return success
    
    async def notify_price_drop(self, listing: Listing) -> bool:
        """Send notification for a price drop"""
        if not self.bot:
            return False
        
        # Check if should notify
        price_drop_pct = self.deal_calculator.get_price_drop_percentage(listing)
        if not price_drop_pct or price_drop_pct < settings.min_price_drop_percent_notify:
            return False
        
        # Don't re-notify about same price drop within 24 hours
        recent_notification = self.db.query(Notification).filter(
            Notification.listing_id == listing.id,
            Notification.notification_type == 'price_drop',
            Notification.sent_at > datetime.utcnow() - timedelta(hours=24)
        ).first()
        
        if recent_notification:
            return False
        
        # Build message
        message = self._build_listing_message(listing, notification_type='price_drop', price_drop_pct=price_drop_pct)
        
        # Send notification
        success = await self._send_message(message)
        
        if success:
            self._record_notification(listing, 'price_drop', message)
        
        return success
    
    async def notify_high_score(self, listing: Listing) -> bool:
        """Send notification for high deal score"""
        if not self.bot:
            return False
        
        # Check if should notify
        if listing.deal_score < settings.min_deal_score_notify:
            return False
        
        # Check if already notified
        if self._already_notified(listing, 'high_score'):
            return False
        
        # Build message
        message = self._build_listing_message(listing, notification_type='high_score')
        
        # Send notification
        success = await self._send_message(message)
        
        if success:
            self._record_notification(listing, 'high_score', message)
        
        return success
    
    def _should_notify(self, listing: Listing, notification_type: str) -> bool:
        """Determine if notification should be sent"""
        
        # Don't notify for listings marked as "not interested"
        if listing.status == 'not_interested':
            return False
        
        # Don't notify for listings already contacted
        if listing.status == 'contacted':
            return False
        
        if notification_type == 'new_listing':
            # Notify if high score
            if listing.deal_score >= settings.min_deal_score_notify:
                return True
            
            # Notify if in high priority neighborhood
            high_priority = settings.get_high_priority_neighborhoods_list()
            if listing.neighborhood in high_priority:
                return True
            
            return False
        
        return True
    
    def _already_notified(self, listing: Listing, notification_type: str) -> bool:
        """Check if already notified about this listing"""
        existing = self.db.query(Notification).filter(
            Notification.listing_id == listing.id,
            Notification.notification_type == notification_type
        ).first()
        
        return existing is not None
    
    def _build_listing_message(self, listing: Listing, notification_type: str, price_drop_pct: Optional[float] = None) -> str:
        """Build notification message"""
        
        # Emoji based on notification type
        emoji_map = {
            'new_listing': '🆕',
            'price_drop': '🔥',
            'high_score': '⭐'
        }
        emoji = emoji_map.get(notification_type, '📢')
        
        # Build message
        lines = []
        
        if notification_type == 'price_drop' and price_drop_pct:
            lines.append(f"{emoji} *PRICE DROP - {price_drop_pct:.1f}% OFF!*")
        elif notification_type == 'high_score':
            lines.append(f"{emoji} *HIGH SCORE LISTING* (Score: {listing.deal_score:.0f}/100)")
        else:
            lines.append(f"{emoji} *New Listing*")
        
        lines.append("")
        lines.append(f"*{listing.title}*")
        lines.append("")
        
        # Address
        if listing.address:
            lines.append(f"📍 {listing.address}")
        
        # Price
        if listing.price:
            price_text = f"💰 ₪{listing.price:,.0f}"
            if listing.price_per_sqm:
                price_text += f" (₪{listing.price_per_sqm:.0f}/m²)"
            lines.append(price_text)
        
        # Details
        details = []
        if listing.rooms:
            details.append(f"{listing.rooms} חדרים")
        if listing.size_sqm:
            details.append(f"{listing.size_sqm:.0f} מ״ר")
        if listing.floor is not None:
            floor_text = f"קומה {listing.floor}"
            if listing.total_floors:
                floor_text += f"/{listing.total_floors}"
            details.append(floor_text)
        
        if details:
            lines.append(f"📐 {' | '.join(details)}")
        
        # Features
        features = []
        if listing.has_parking:
            features.append("🅿️ חניה")
        if listing.has_elevator:
            features.append("🛗 מעלית")
        if listing.has_balcony:
            features.append("🏖 מרפסת")
        
        if features:
            lines.append(" ".join(features))
        
        # Deal score
        lines.append("")
        lines.append(f"🎯 Deal Score: *{listing.deal_score:.0f}/100*")
        
        # Source
        lines.append(f"📱 Source: {listing.source.title()}")
        
        # Link
        if listing.url:
            lines.append("")
            lines.append(f"🔗 [View Listing]({listing.url})")
        
        # WhatsApp contact
        if listing.contact_phone:
            # Clean phone for WhatsApp
            clean_phone = listing.contact_phone.replace('-', '').replace(' ', '')
            if clean_phone.startswith('0'):
                clean_phone = '972' + clean_phone[1:]
            
            whatsapp_msg = f"היי, ראיתי את הדירה שלך ב-{listing.source} - {listing.address}"
            whatsapp_url = f"https://wa.me/{clean_phone}?text={whatsapp_msg}"
            lines.append(f"💬 [Contact via WhatsApp]({whatsapp_url})")
        
        return "\n".join(lines)
    
    async def _send_message(self, message: str) -> bool:
        """Send message via Telegram"""
        if not self.bot or not self.chat_id:
            return False
        
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='Markdown',
                disable_web_page_preview=False
            )
            logger.info("Telegram notification sent successfully")
            return True
            
        except TelegramError as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending Telegram message: {e}")
            return False
    
    def _record_notification(self, listing: Listing, notification_type: str, message: str):
        """Record that notification was sent"""
        notification = Notification(
            listing_id=listing.id,
            notification_type=notification_type,
            message=message,
            sent_at=datetime.utcnow()
        )
        self.db.add(notification)
        self.db.commit()


async def send_test_notification(db_session: Session):
    """Send a test notification to verify Telegram is working"""
    notifier = TelegramNotifier(db_session)
    
    if not notifier.bot:
        logger.error("Telegram is not configured")
        return False
    
    message = """
🧪 *Test Notification*

Your Real Estate Monitor is working!

You will receive notifications for:
• New listings with high deal scores
• Price drops on existing listings
• Listings in high-priority neighborhoods

Happy house hunting! 🏡
    """
    
    try:
        await notifier.bot.send_message(
            chat_id=notifier.chat_id,
            text=message,
            parse_mode='Markdown'
        )
        logger.info("✅ Test notification sent successfully!")
        return True
    except Exception as e:
        logger.error(f"❌ Test notification failed: {e}")
        return False
