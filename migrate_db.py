import sqlite3
import asyncio
from app.database import init_db
from app.models import ItineraryItem # Import to register with SQLModel

DB_PATH = "gojo.db"

def migrate():
    print("Migrating database...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Trip table
    try:
        cursor.execute("ALTER TABLE trip ADD COLUMN start_location TEXT")
        print("Added start_location to trip")
    except sqlite3.OperationalError:
        print("start_location already exists in trip")
        
    try:
        cursor.execute("ALTER TABLE trip ADD COLUMN estimated_budget FLOAT")
        print("Added estimated_budget to trip")
    except sqlite3.OperationalError:
        print("estimated_budget already exists in trip")

    # 2. TripUserLink table
    try:
        cursor.execute("ALTER TABLE tripuserlink ADD COLUMN role TEXT DEFAULT 'member'")
        print("Added role to tripuserlink")
    except sqlite3.OperationalError:
        print("role already exists in tripuserlink")
        
    # 3. Photo table
    try:
        cursor.execute("ALTER TABLE photo ADD COLUMN media_type TEXT DEFAULT 'image'")
        print("Added media_type to photo")
    except sqlite3.OperationalError:
        print("media_type already exists in photo")

    conn.commit()
    conn.close()
    
    # 4. Create new tables (ItineraryItem)
    # We can run the async init_db
    print("Initializing new tables...")
    asyncio.run(init_db())
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
