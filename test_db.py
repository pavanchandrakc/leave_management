import sys
from src.models import engine, init_db, Employee, LeaveType, LeaveBalance
from sqlalchemy import text

def test_orm():
    print("Connecting to database via SQLAlchemy...")
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version();")).fetchone()
            print(f"[SUCCESS] Connected: {result[0]}")

        print("Initializing tables & seed data via SQLAlchemy...")
        init_db()
        print("[SUCCESS] Tables and seeds initialized!")

        with engine.connect() as conn:
            tables = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name;
            """)).fetchall()
            print(f"Active tables in pgAdmin/Postgres: {[t[0] for t in tables]}")
    except Exception as e:
        print(f"[ERROR] Connection/Setup failed: {e}")
        print("\nPlease check your .env settings (DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD).")
        sys.exit(1)

if __name__ == "__main__":
    test_orm()
