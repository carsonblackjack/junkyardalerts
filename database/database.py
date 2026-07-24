import sqlite3

DB_NAME = "inventory.db"


def get_connection():
    return sqlite3.connect(DB_NAME)


def initialize_database():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vehicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year TEXT,
            make TEXT,
            model TEXT,
            row_location TEXT,
            yard TEXT,
            date_found TEXT,
            UNIQUE(year, make, model, row_location, yard)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT
        )
    """)

    conn.commit()
    conn.close()


def save_vehicle(year, make, model, row_location, yard, date_found):
    """Insert a vehicle if it hasn't been seen before.

    Returns True if this was a new vehicle, False if it was a duplicate
    (already in the DB per the UNIQUE constraint) and the insert was skipped.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR IGNORE INTO vehicles
        (year, make, model, row_location, yard, date_found)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (year, make, model, row_location, yard, date_found))

    is_new = cursor.rowcount > 0

    conn.commit()
    conn.close()

    return is_new


def create_user(email, password_hash, created_at):
    """Add a new user. Returns True if created, False if that email is
    already taken (email must be unique)."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO users (email, password_hash, created_at)
            VALUES (?, ?, ?)
        """, (email, password_hash, created_at))
        conn.commit()
        created = True
    except sqlite3.IntegrityError:
        created = False

    conn.close()

    return created


def get_user_by_email(email):
    """Return (id, email, password_hash, created_at) for this email, or
    None if no user has that email."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, email, password_hash, created_at FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()

    conn.close()

    return user


def get_inventory_counts_by_yard():
    """Return [(yard, vehicle_count), ...] for everything currently saved."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT yard, COUNT(*) FROM vehicles GROUP BY yard")
    counts = cursor.fetchall()

    conn.close()

    return counts