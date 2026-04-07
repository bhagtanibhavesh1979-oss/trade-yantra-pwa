import os
from sqlalchemy import create_engine, text
import sys

# Add current dir to path to import database config
sys.path.append(os.getcwd())
from database import DATABASE_URL

def migrate():
    print(f"Connecting to database: {DATABASE_URL}")
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            # Check for existing columns and add missing ones
            # PostgreSQL / Neon support IF NOT EXISTS
            try:
                conn.execute(text("ALTER TABLE user_sessions ADD COLUMN IF NOT EXISTS auto_live_trade BOOLEAN DEFAULT FALSE"))
                print("✅ Checked/Added auto_live_trade")
            except Exception as e: 
                # Fallback for SQLite which doesn't support IF NOT EXISTS
                if "duplicate column" not in str(e).lower():
                    try:
                        conn.execute(text("ALTER TABLE user_sessions ADD COLUMN auto_live_trade BOOLEAN DEFAULT 0"))
                        print("✅ Added auto_live_trade (SQLite)")
                    except: pass
            
            try:
                conn.execute(text("ALTER TABLE user_sessions ADD COLUMN IF NOT EXISTS trade_quantity INTEGER DEFAULT 100"))
                print("✅ Checked/Added trade_quantity")
            except Exception as e:
                if "duplicate column" not in str(e).lower():
                    try:
                        conn.execute(text("ALTER TABLE user_sessions ADD COLUMN trade_quantity INTEGER DEFAULT 100"))
                        print("✅ Added trade_quantity (SQLite)")
                    except: pass

            try:
                conn.execute(text("ALTER TABLE user_sessions ADD COLUMN IF NOT EXISTS trade_capital FLOAT DEFAULT 0.0"))
                print("✅ Checked/Added trade_capital")
            except Exception as e:
                if "duplicate column" not in str(e).lower():
                    try:
                        conn.execute(text("ALTER TABLE user_sessions ADD COLUMN trade_capital FLOAT DEFAULT 0.0"))
                        print("✅ Added trade_capital (SQLite)")
                    except: pass
            
            # Use raw connection for commit
            conn.execute(text("COMMIT"))
            print("\n🎉 Database Migration Complete!")
    except Exception as e:
        print(f"❌ Migration Error: {e}")

if __name__ == "__main__":
    migrate()
