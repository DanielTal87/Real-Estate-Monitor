#!/usr/bin/env python3
"""
Test script for Real Estate Monitor
Run this to verify your setup
"""

import sys
from pathlib import Path


def test_imports():
    """Test that all imports work"""
    print("Testing imports...")
    
    try:
        import sqlalchemy
        print("  ✅ SQLAlchemy")
    except ImportError as e:
        print(f"  ❌ SQLAlchemy: {e}")
        return False
    
    try:
        import fastapi
        print("  ✅ FastAPI")
    except ImportError as e:
        print(f"  ❌ FastAPI: {e}")
        return False
    
    try:
        import playwright
        print("  ✅ Playwright")
    except ImportError as e:
        print(f"  ❌ Playwright: {e}")
        return False
    
    try:
        import telegram
        print("  ✅ python-telegram-bot")
    except ImportError as e:
        print(f"  ❌ python-telegram-bot: {e}")
        return False
    
    try:
        import apscheduler
        print("  ✅ APScheduler")
    except ImportError as e:
        print(f"  ❌ APScheduler: {e}")
        return False
    
    return True


def test_config():
    """Test configuration"""
    print("\nTesting configuration...")
    
    try:
        from config import settings
        print(f"  ✅ Config loaded")
        print(f"     - Cities: {settings.get_cities_list()[:3]}...")
        print(f"     - Max Price: ₪{settings.max_price}")
        print(f"     - Min Rooms: {settings.min_rooms}")
        print(f"     - Telegram: {'Enabled' if settings.is_telegram_enabled() else 'Disabled'}")
        return True
    except Exception as e:
        print(f"  ❌ Config error: {e}")
        return False


def test_database():
    """Test database connection"""
    print("\nTesting database...")
    
    try:
        from database import init_db
        from config import settings
        
        engine, SessionLocal = init_db(settings.database_url)
        db = SessionLocal()
        
        # Try a simple query
        from database import Listing
        count = db.query(Listing).count()
        
        print(f"  ✅ Database connected")
        print(f"     - Listings in database: {count}")
        
        db.close()
        return True
    except Exception as e:
        print(f"  ❌ Database error: {e}")
        return False


def test_scrapers():
    """Test scraper imports"""
    print("\nTesting scrapers...")
    
    try:
        from scrapers import Yad2Scraper, MadlanScraper, FacebookScraper
        print("  ✅ Scrapers imported successfully")
        return True
    except Exception as e:
        print(f"  ❌ Scraper error: {e}")
        return False


def test_files():
    """Test that required files exist"""
    print("\nTesting required files...")
    
    required_files = [
        'main.py',
        'config.py',
        'database.py',
        'dashboard.py',
        'scheduler.py',
        'deal_score.py',
        'listing_processor.py',
        'telegram_notifier.py',
        'requirements.txt',
        '.env',
        'scrapers/base_scraper.py',
        'scrapers/yad2_scraper.py',
        'templates/index.html'
    ]
    
    all_exist = True
    for file_path in required_files:
        if Path(file_path).exists():
            print(f"  ✅ {file_path}")
        else:
            print(f"  ❌ {file_path} - MISSING!")
            all_exist = False
    
    return all_exist


def print_summary(results):
    """Print test summary"""
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(results.values())
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    print("\n" + "-" * 60)
    print(f"Results: {passed}/{total} tests passed")
    print("-" * 60)
    
    if passed == total:
        print("\n🎉 All tests passed! Your setup is ready.")
        print("\nNext steps:")
        print("  1. Review your .env configuration")
        print("  2. Run: python main.py")
        print("  3. Open: http://127.0.0.1:8000")
    else:
        print("\n⚠️  Some tests failed. Please:")
        print("  1. Run: pip install -r requirements.txt")
        print("  2. Run: playwright install chromium")
        print("  3. Verify all files are present")
        print("  4. Run this test again")


def main():
    """Run all tests"""
    print("\n" + "🔍" * 20)
    print("   REAL ESTATE MONITOR - SYSTEM TEST")
    print("🔍" * 20 + "\n")
    
    tests = {
        "Package Imports": test_imports,
        "Configuration": test_config,
        "Database": test_database,
        "Scrapers": test_scrapers,
        "Required Files": test_files
    }
    
    results = {}
    
    for test_name, test_func in tests.items():
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"\n❌ {test_name} failed with exception: {e}")
            results[test_name] = False
    
    print_summary(results)
    
    return all(results.values())


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
