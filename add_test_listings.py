#!/usr/bin/env python3
"""
Add test listings to see the dashboard in action
Run this from your project directory: python add_test_listings.py
"""

from database import init_db, Listing, PriceHistory
from config import settings
from datetime import datetime, timedelta
import random

print("🏠 Adding test listings to database...")

engine, SessionLocal = init_db(settings.database_url)
db = SessionLocal()

# Clear old test listings
db.query(Listing).filter(Listing.external_id.like('test%')).delete()
db.commit()

# Sample listings for different cities
test_listings = [
    {
        'source': 'yad2',
        'external_id': 'test001',
        'url': 'https://www.yad2.co.il/realestate/forsale/test001',
        'title': 'דירת 3 חדרים מרווחת ומשופצת ברמת אביב',
        'description': 'דירה יפה ומשופצת כחדשה! 3 חדרים גדולים, קומה 4 מתוך 5, עם מעלית, חניה וממ"ד. מטבח מודרני, אמבטיה מחודשת, ריצוף שיש. קרוב לפארק ולתחבורה ציבורית.',
        'address': 'רחוב הרצל 10, רמת אביב, תל אביב-יפו',
        'city': 'תל אביב-יפו',
        'neighborhood': 'רמת אביב',
        'street': 'הרצל',
        'rooms': 3,
        'size_sqm': 85,
        'floor': 4,
        'total_floors': 5,
        'price': 2300000,
        'has_elevator': True,
        'has_parking': True,
        'has_balcony': True,
        'has_mamad': True,
        'contact_phone': '050-1234567',
        'deal_score': 88,
        'status': 'unseen',
        'first_seen': datetime.utcnow()
    },
    {
        'source': 'yad2',
        'external_id': 'test002',
        'url': 'https://www.yad2.co.il/realestate/forsale/test002',
        'title': 'דירת 2.5 חדרים בגבעתיים במיקום מעולה',
        'description': 'דירה נעימה בבניין מתוחזק, 2.5 חדרים, קומה 2. מזגן בכל החדרים, משופצת חלקית. קרוב למרכזי קניות ובתי ספר.',
        'address': 'רחוב ירושלים 25, גבעתיים',
        'city': 'גבעתיים',
        'neighborhood': 'מרכז העיר',
        'street': 'ירושלים',
        'rooms': 2.5,
        'size_sqm': 65,
        'floor': 2,
        'total_floors': 4,
        'price': 2100000,
        'has_elevator': False,
        'has_parking': False,
        'has_balcony': True,
        'has_mamad': False,
        'contact_phone': '050-7654321',
        'deal_score': 72,
        'status': 'unseen',
        'first_seen': datetime.utcnow() - timedelta(days=2)
    },
    {
        'source': 'madlan',
        'external_id': 'test003',
        'url': 'https://www.madlan.co.il/for-sale/test003',
        'title': 'דירת גן 4 חדרים ברמת גן - הזדמנות!',
        'description': 'דירת גן מדהימה! 4 חדרים מרווחים, עם גינה פרטית של 40 מ"ר, חניה פרטית וממ"ד. בניין חדיש, שכונה שקטה ומבוקשת. מתאימה למשפחות.',
        'address': 'רחוב ביאליק 15, בילו, רמת גן',
        'city': 'רמת גן',
        'neighborhood': 'בילו',
        'street': 'ביאליק',
        'rooms': 4,
        'size_sqm': 95,
        'floor': 0,
        'total_floors': 3,
        'price': 2700000,
        'has_elevator': False,
        'has_parking': True,
        'has_balcony': False,
        'has_mamad': True,
        'contact_phone': '052-9876543',
        'deal_score': 81,
        'status': 'unseen',
        'first_seen': datetime.utcnow() - timedelta(hours=5)
    },
    {
        'source': 'yad2',
        'external_id': 'test004',
        'url': 'https://www.yad2.co.il/realestate/forsale/test004',
        'title': 'דירת 3.5 חדרים בהרצליה - נוף לים!',
        'description': 'דירה מהממת עם נוף פנורמי לים! 3.5 חדרים, קומה 6, פנטהאוז. מרפסת ענקית 30 מ"ר, חניה כפולה, ממ"ד, מעלית שבת. בניין בוטיק עם 8 דירות בלבד.',
        'address': 'רחוב המעפילים 42, הרצליה',
        'city': 'הרצליה',
        'neighborhood': 'הרצליה פיתוח',
        'street': 'המעפילים',
        'rooms': 3.5,
        'size_sqm': 110,
        'floor': 6,
        'total_floors': 6,
        'price': 4200000,
        'has_elevator': True,
        'has_parking': True,
        'has_balcony': True,
        'has_mamad': True,
        'contact_phone': '054-1112233',
        'deal_score': 75,
        'status': 'unseen',
        'first_seen': datetime.utcnow() - timedelta(days=1)
    },
    {
        'source': 'facebook',
        'external_id': 'test005',
        'url': 'https://www.facebook.com/marketplace/item/test005',
        'title': 'דירת 3 חדרים ברמת השרון - מחיר מציאה!',
        'description': 'למכירה דחופה! דירת 3 חדרים בבניין משופץ, קומה 3 עם מעלית. חניה, מרפסת שמש, ממ"ד. הדירה זקוקה לשיפוץ קוסמטי. מחיר אטרקטיבי למהירי החלטה!',
        'address': 'רחוב סוקולוב 18, רמת השרון',
        'city': 'רמת השרון',
        'neighborhood': 'הוותיקה',
        'street': 'סוקולוב',
        'rooms': 3,
        'size_sqm': 78,
        'floor': 3,
        'total_floors': 4,
        'price': 2450000,
        'has_elevator': True,
        'has_parking': True,
        'has_balcony': True,
        'has_mamad': True,
        'contact_phone': '053-4445566',
        'deal_score': 85,
        'status': 'unseen',
        'first_seen': datetime.utcnow() - timedelta(hours=3)
    }
]

# Add listings to database
for listing_data in test_listings:
    # Calculate price per sqm
    if listing_data.get('price') and listing_data.get('size_sqm'):
        listing_data['price_per_sqm'] = listing_data['price'] / listing_data['size_sqm']

    # Generate property hash
    property_hash = Listing.generate_property_hash(
        listing_data['address'],
        listing_data['rooms'],
        listing_data['size_sqm']
    )

    listing = Listing(
        property_hash=property_hash,
        last_seen=datetime.utcnow(),
        last_checked=datetime.utcnow(),
        **listing_data
    )

    db.add(listing)
    db.flush()

    # Add initial price history
    price_history = PriceHistory(
        listing_id=listing.id,
        price=listing.price,
        price_per_sqm=listing.price_per_sqm,
        timestamp=listing.first_seen
    )
    db.add(price_history)

    print(f"  ✅ Added: {listing.title[:50]}... (Score: {listing.deal_score})")

db.commit()
db.close()

print(f"\n🎉 Successfully added {len(test_listings)} test listings!")
print("\n📊 Statistics:")
print(f"   - Cities: {len(set(l['city'] for l in test_listings))}")
print(f"   - High scores (>80): {len([l for l in test_listings if l['deal_score'] > 80])}")
print(f"   - With Mamad: {len([l for l in test_listings if l['has_mamad']])}")
print("\n🚀 Now restart your app and open http://127.0.0.1:8000")
print("   You should see 5 listings with proper cities in the dropdown!")