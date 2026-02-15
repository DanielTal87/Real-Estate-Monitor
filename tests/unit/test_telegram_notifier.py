"""
Unit tests for telegram notifier service
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta

from app.services.telegram_notifier import TelegramNotifier, send_test_notification
from app.core.database import Listing, Notification


@pytest.fixture
def mock_db_session():
    """Create mock database session"""
    return Mock()


@pytest.fixture
def mock_listing():
    """Create mock listing"""
    listing = Mock(spec=Listing)
    listing.id = 1
    listing.title = "Test Apartment"
    listing.address = "Test St, Tel Aviv"
    listing.price = 5000
    listing.price_per_sqm = 100
    listing.rooms = 3
    listing.size_sqm = 50
    listing.floor = 2
    listing.total_floors = 5
    listing.has_parking = True
    listing.has_elevator = True
    listing.has_balcony = True
    listing.deal_score = 85
    listing.source = "yad2"
    listing.url = "https://example.com/listing/1"
    listing.contact_phone = "0501234567"
    listing.status = "unseen"
    listing.first_seen = datetime.utcnow()
    return listing


@pytest.fixture
def notifier_enabled(mock_db_session):
    """Create notifier with Telegram enabled"""
    with patch('app.services.telegram_notifier.settings') as mock_settings:
        mock_settings.is_telegram_enabled.return_value = True
        mock_settings.telegram_bot_token = "test_token"
        mock_settings.telegram_chat_id = "test_chat_id"
        mock_settings.min_deal_score_notify = 80
        mock_settings.min_price_drop_percent_notify = 10
        mock_settings.get_high_priority_neighborhoods_list.return_value = ["Center"]

        with patch('app.services.telegram_notifier.Bot') as mock_bot_class:
            with patch('app.services.telegram_notifier.DealScoreCalculator'):
                notifier = TelegramNotifier(mock_db_session)
                yield notifier


@pytest.fixture
def notifier_disabled(mock_db_session):
    """Create notifier with Telegram disabled"""
    with patch('app.services.telegram_notifier.settings') as mock_settings:
        mock_settings.is_telegram_enabled.return_value = False

        with patch('app.services.telegram_notifier.DealScoreCalculator'):
            notifier = TelegramNotifier(mock_db_session)
            yield notifier


class TestTelegramNotifier:
    """Test TelegramNotifier class"""

    def test_init_enabled(self, notifier_enabled):
        """Test initialization with Telegram enabled"""
        assert notifier_enabled.bot is not None
        assert notifier_enabled.chat_id is not None

    def test_init_disabled(self, notifier_disabled):
        """Test initialization with Telegram disabled"""
        assert notifier_disabled.bot is None
        assert notifier_disabled.chat_id is None

    @pytest.mark.asyncio
    async def test_notify_new_listing_disabled(self, notifier_disabled, mock_listing):
        """Test notifying when Telegram is disabled"""
        result = await notifier_disabled.notify_new_listing(mock_listing)
        assert result is False

    @pytest.mark.asyncio
    async def test_notify_new_listing_success(self, notifier_enabled, mock_listing):
        """Test successful new listing notification"""
        # Setup mocks
        notifier_enabled.bot.send_message = AsyncMock()

        with patch.object(notifier_enabled, '_should_notify', return_value=True):
            with patch.object(notifier_enabled, '_already_notified', return_value=False):
                with patch.object(notifier_enabled, '_send_message', return_value=True) as mock_send:
                    with patch.object(notifier_enabled, '_record_notification'):
                        result = await notifier_enabled.notify_new_listing(mock_listing)

                        assert result is True
                        mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_notify_new_listing_already_notified(self, notifier_enabled, mock_listing):
        """Test notification when already notified"""
        with patch.object(notifier_enabled, '_should_notify', return_value=True):
            with patch.object(notifier_enabled, '_already_notified', return_value=True):
                result = await notifier_enabled.notify_new_listing(mock_listing)

                assert result is False

    @pytest.mark.asyncio
    async def test_notify_new_listing_should_not_notify(self, notifier_enabled, mock_listing):
        """Test notification when should not notify"""
        with patch.object(notifier_enabled, '_should_notify', return_value=False):
            result = await notifier_enabled.notify_new_listing(mock_listing)

            assert result is False

    @pytest.mark.asyncio
    async def test_notify_price_drop_success(self, notifier_enabled, mock_listing):
        """Test successful price drop notification"""
        notifier_enabled.deal_calculator.get_price_drop_percentage = Mock(return_value=15.0)
        notifier_enabled.bot.send_message = AsyncMock()

        mock_query = Mock()
        notifier_enabled.db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        with patch.object(notifier_enabled, '_send_message', return_value=True) as mock_send:
            with patch.object(notifier_enabled, '_record_notification'):
                result = await notifier_enabled.notify_price_drop(mock_listing)

                assert result is True
                mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_notify_price_drop_too_small(self, notifier_enabled, mock_listing):
        """Test price drop notification when drop is too small"""
        notifier_enabled.deal_calculator.get_price_drop_percentage = Mock(return_value=5.0)

        result = await notifier_enabled.notify_price_drop(mock_listing)

        assert result is False

    @pytest.mark.asyncio
    async def test_notify_price_drop_recently_notified(self, notifier_enabled, mock_listing):
        """Test price drop when recently notified"""
        notifier_enabled.deal_calculator.get_price_drop_percentage = Mock(return_value=15.0)

        mock_notification = Mock(spec=Notification)
        mock_query = Mock()
        notifier_enabled.db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_notification

        result = await notifier_enabled.notify_price_drop(mock_listing)

        assert result is False

    @pytest.mark.asyncio
    async def test_notify_high_score_success(self, notifier_enabled, mock_listing):
        """Test successful high score notification"""
        mock_listing.deal_score = 90
        notifier_enabled.bot.send_message = AsyncMock()

        with patch.object(notifier_enabled, '_already_notified', return_value=False):
            with patch.object(notifier_enabled, '_send_message', return_value=True) as mock_send:
                with patch.object(notifier_enabled, '_record_notification'):
                    result = await notifier_enabled.notify_high_score(mock_listing)

                    assert result is True
                    mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_notify_high_score_low_score(self, notifier_enabled, mock_listing):
        """Test high score notification with low score"""
        mock_listing.deal_score = 50

        result = await notifier_enabled.notify_high_score(mock_listing)

        assert result is False

    def test_should_notify_not_interested(self, notifier_enabled, mock_listing):
        """Test should notify for not interested listing"""
        mock_listing.status = "not_interested"

        result = notifier_enabled._should_notify(mock_listing, "new_listing")

        assert result is False

    def test_should_notify_contacted(self, notifier_enabled, mock_listing):
        """Test should notify for contacted listing"""
        mock_listing.status = "contacted"

        result = notifier_enabled._should_notify(mock_listing, "new_listing")

        assert result is False

    def test_should_notify_high_score(self, notifier_enabled, mock_listing):
        """Test should notify for high score listing"""
        mock_listing.deal_score = 90

        result = notifier_enabled._should_notify(mock_listing, "new_listing")

        assert result is True

    def test_should_notify_high_priority_neighborhood(self, notifier_enabled, mock_listing):
        """Test should notify for high priority neighborhood"""
        mock_listing.deal_score = 50
        mock_listing.neighborhood = "Center"

        result = notifier_enabled._should_notify(mock_listing, "new_listing")

        assert result is True

    def test_should_notify_low_score_normal_neighborhood(self, notifier_enabled, mock_listing):
        """Test should not notify for low score in normal neighborhood"""
        mock_listing.deal_score = 50
        mock_listing.neighborhood = "Other"

        result = notifier_enabled._should_notify(mock_listing, "new_listing")

        assert result is False

    def test_already_notified_true(self, notifier_enabled, mock_listing):
        """Test already notified returns true"""
        mock_notification = Mock(spec=Notification)
        mock_query = Mock()
        notifier_enabled.db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_notification

        result = notifier_enabled._already_notified(mock_listing, "new_listing")

        assert result is True

    def test_already_notified_false(self, notifier_enabled, mock_listing):
        """Test already notified returns false"""
        mock_query = Mock()
        notifier_enabled.db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        result = notifier_enabled._already_notified(mock_listing, "new_listing")

        assert result is False

    def test_build_listing_message_new_listing(self, notifier_enabled, mock_listing):
        """Test building message for new listing"""
        message = notifier_enabled._build_listing_message(mock_listing, "new_listing")

        assert "New Listing" in message
        assert mock_listing.title in message
        # Price is formatted with comma separator, so check for formatted version
        assert "5,000" in message

    def test_build_listing_message_price_drop(self, notifier_enabled, mock_listing):
        """Test building message for price drop"""
        message = notifier_enabled._build_listing_message(
            mock_listing, "price_drop", price_drop_pct=15.0
        )

        assert "PRICE DROP" in message
        assert "15.0%" in message

    def test_build_listing_message_high_score(self, notifier_enabled, mock_listing):
        """Test building message for high score"""
        message = notifier_enabled._build_listing_message(mock_listing, "high_score")

        assert "HIGH SCORE" in message
        assert str(mock_listing.deal_score) in message

    def test_build_listing_message_with_features(self, notifier_enabled, mock_listing):
        """Test building message with features"""
        message = notifier_enabled._build_listing_message(mock_listing, "new_listing")

        assert "חניה" in message  # Parking
        assert "מעלית" in message  # Elevator
        assert "מרפסת" in message  # Balcony

    def test_build_listing_message_with_whatsapp(self, notifier_enabled, mock_listing):
        """Test building message with WhatsApp link"""
        message = notifier_enabled._build_listing_message(mock_listing, "new_listing")

        assert "wa.me" in message
        assert "972" in message

    @pytest.mark.asyncio
    async def test_send_message_success(self, notifier_enabled):
        """Test successful message sending"""
        notifier_enabled.bot.send_message = AsyncMock()

        result = await notifier_enabled._send_message("Test message")

        assert result is True
        notifier_enabled.bot.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_message_no_bot(self, notifier_disabled):
        """Test sending message with no bot"""
        result = await notifier_disabled._send_message("Test message")

        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_telegram_error(self, notifier_enabled):
        """Test sending message with Telegram error"""
        from telegram.error import TelegramError

        notifier_enabled.bot.send_message = AsyncMock(side_effect=TelegramError("Test error"))

        result = await notifier_enabled._send_message("Test message")

        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_generic_error(self, notifier_enabled):
        """Test sending message with generic error"""
        notifier_enabled.bot.send_message = AsyncMock(side_effect=Exception("Test error"))

        result = await notifier_enabled._send_message("Test message")

        assert result is False

    def test_record_notification(self, notifier_enabled, mock_listing):
        """Test recording notification"""
        notifier_enabled._record_notification(mock_listing, "new_listing", "Test message")

        notifier_enabled.db.add.assert_called_once()
        notifier_enabled.db.commit.assert_called_once()


class TestSendTestNotification:
    """Test send_test_notification function"""

    @pytest.mark.asyncio
    async def test_send_test_notification_success(self, mock_db_session):
        """Test successful test notification"""
        with patch('app.services.telegram_notifier.TelegramNotifier') as mock_notifier_class:
            mock_notifier = Mock()
            mock_notifier.bot = Mock()
            mock_notifier.chat_id = "test_chat_id"
            mock_notifier.bot.send_message = AsyncMock()
            mock_notifier_class.return_value = mock_notifier

            result = await send_test_notification(mock_db_session)

            assert result is True
            mock_notifier.bot.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_test_notification_no_bot(self, mock_db_session):
        """Test test notification with no bot"""
        with patch('app.services.telegram_notifier.TelegramNotifier') as mock_notifier_class:
            mock_notifier = Mock()
            mock_notifier.bot = None
            mock_notifier_class.return_value = mock_notifier

            result = await send_test_notification(mock_db_session)

            assert result is False

    @pytest.mark.asyncio
    async def test_send_test_notification_error(self, mock_db_session):
        """Test test notification with error"""
        with patch('app.services.telegram_notifier.TelegramNotifier') as mock_notifier_class:
            mock_notifier = Mock()
            mock_notifier.bot = Mock()
            mock_notifier.chat_id = "test_chat_id"
            mock_notifier.bot.send_message = AsyncMock(side_effect=Exception("Test error"))
            mock_notifier_class.return_value = mock_notifier

            result = await send_test_notification(mock_db_session)

            assert result is False
