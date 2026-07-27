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

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS watchlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            make TEXT NOT NULL,
            model TEXT NOT NULL DEFAULT '',
            created_at TEXT,
            UNIQUE(user_id, make, model),
            FOREIGN KEY (user_id) REFERENCES users(id)
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


def add_watchlist_item(user_id, make, model, created_at):
    """Add a make (and optionally a model) to a user's watchlist. Leaving
    model blank watches every model of that make. Returns True if added,
    False if that make/model was already on their watchlist."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO watchlist (user_id, make, model, created_at)
            VALUES (?, ?, ?, ?)
        """, (user_id, make, model, created_at))
        conn.commit()
        added = True
    except sqlite3.IntegrityError:
        added = False

    conn.close()

    return added


def remove_watchlist_item(watchlist_id, user_id):
    """Delete a watchlist item, only if it belongs to this user."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM watchlist WHERE id = ? AND user_id = ?", (watchlist_id, user_id))

    conn.commit()
    conn.close()


def get_watchlist(user_id):
    """Return [(id, make, model), ...] for everything this user is watching."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, make, model FROM watchlist WHERE user_id = ? ORDER BY make, model", (user_id,))
    items = cursor.fetchall()

    conn.close()

    return items


def get_matching_vehicles(user_id):
    """Return every vehicle in inventory that matches this user's
    watchlist (make always, model only if they specified one)."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT v.year, v.make, v.model, v.row_location, v.yard, v.date_found
        FROM watchlist w
        JOIN vehicles v
            ON UPPER(v.make) = UPPER(w.make)
            AND (w.model = '' OR UPPER(v.model) = UPPER(w.model))
        WHERE w.user_id = ?
        ORDER BY v.date_found DESC
    """, (user_id,))
    vehicles = cursor.fetchall()

    conn.close()

    return vehicles


def get_distinct_models_for_make(make):
    """Return every model we've actually seen in inventory for this make, sorted."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT model FROM vehicles WHERE UPPER(make) = UPPER(?) ORDER BY model
    """, (make,))
    models = [row[0] for row in cursor.fetchall()]

    conn.close()

    return models


def get_recent_vehicles(limit=20):
    """Return the most recently found vehicles across every yard, newest first."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT year, make, model, row_location, yard, date_found
        FROM vehicles
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))
    vehicles = cursor.fetchall()

    conn.close()

    return vehicles


def get_inventory_counts_by_yard():
    """Return [(yard, vehicle_count), ...] for everything currently saved."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT yard, COUNT(*) FROM vehicles GROUP BY yard")
    counts = cursor.fetchall()

    conn.close()

    return counts