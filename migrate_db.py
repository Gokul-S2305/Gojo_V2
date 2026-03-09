import sqlite3
import asyncio
from app.database import init_db
from app.models import ItineraryItem # Import to register with SQLModel

DB_PATH = "gojo.db"

def migrate():
    print("Migrating database...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if user table needs migration (password_hash is NOT NULL)
    cursor.execute("PRAGMA table_info(user)")
    columns = cursor.fetchall()
    # columns format: (id, name, type, notnull, dflt_value, pk)
    password_hash_col = next((col for col in columns if col[1] == 'password_hash'), None)
    
    if password_hash_col and password_hash_col[3] == 1: # 1 means NOT NULL
        print("Migrating user table to support nullable password_hash...")
        # Create new table with correct schema
        cursor.execute("""
            CREATE TABLE user_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT,
                full_name TEXT
            )
        """)
        
        # Copy data
        cursor.execute("INSERT INTO user_new (id, email, password_hash, full_name) SELECT id, email, password_hash, full_name FROM user")
        
        # Swap tables
        cursor.execute("DROP TABLE user")
        cursor.execute("ALTER TABLE user_new RENAME TO user")
        cursor.execute("CREATE INDEX ix_user_email ON user (email)")
        print("User table migration completed.")
    
    # Continue with existing migrations...
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
    # Google Drive Integration
    try:
        cursor.execute("ALTER TABLE user ADD COLUMN drive_connected BOOLEAN DEFAULT 0")
        print("Added drive_connected to user")
    except sqlite3.OperationalError:
        print("drive_connected already exists in user")

    try:
        cursor.execute("ALTER TABLE trip ADD COLUMN drive_folder_id TEXT")
        print("Added drive_folder_id to trip")
    except sqlite3.OperationalError:
        print("drive_folder_id already exists in trip")

    conn.commit()
    conn.close()
    
    # 4. Create new tables (ItineraryItem)
    # We can run the async init_db
    print("Initializing new tables...")
    asyncio.run(init_db())
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
