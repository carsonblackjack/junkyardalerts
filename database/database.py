import os
import sqlite3

DB_NAME = "inventory.db"

# On your own PC there's no DATABASE_URL, so this always uses the local
# SQLite file, exactly like before. Once deployed to a host with a Postgres
# database attached, DATABASE_URL gets set automatically and this switches
# over to that instead - same functions, same behavior, different storage.
DATABASE_URL = os.getenv("DATABASE_URL")
USING_POSTGRES = bool(DATABASE_URL)

if USING_POSTGRES:
    import psycopg2
    IntegrityError = psycopg2.IntegrityError
else:
    IntegrityError = sqlite3.IntegrityError


def get_connection():
    if USING_POSTGRES:
        return psycopg2.connect(DATABASE_URL)
    return sqlite3.connect(DB_NAME)


def _q(query):
    """SQLite uses '?' for placeholders, Postgres uses '%s'. Queries below
    are all written with '?' and translated here when needed."""
    return query.replace("?", "%s") if USING_POSTGRES else query


def initialize_database():
    conn = get_connection()
    cursor = conn.cursor()

    id_column = "id SERIAL PRIMARY KEY" if USING_POSTGRES else "id INTEGER PRIMARY KEY AUTOINCREMENT"

    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS vehicles (
            {id_column},
            year TEXT,
            make TEXT,
            model TEXT,
            row_location TEXT,
            yard TEXT,
            date_found TEXT,
            UNIQUE(year, make, model, row_location, yard)
        )
    """)

    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS users (
            {id_column},
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT,
            is_admin INTEGER NOT NULL DEFAULT 0
        )
    """)

    if USING_POSTGRES:
        cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin INTEGER NOT NULL DEFAULT 0")
    else:
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # already has the column

    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS watchlist (
            {id_column},
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

    if USING_POSTGRES:
        sql = """
            INSERT INTO vehicles
            (year, make, model, row_location, yard, date_found)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT DO NOTHING
        """
    else:
        sql = """
            INSERT OR IGNORE INTO vehicles
            (year, make, model, row_location, yard, date_found)
            VALUES (?, ?, ?, ?, ?, ?)
        """

    cursor.execute(_q(sql), (year, make, model, row_location, yard, date_found))

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
        cursor.execute(_q("""
            INSERT INTO users (email, password_hash, created_at)
            VALUES (?, ?, ?)
        """), (email, password_hash, created_at))
        conn.commit()
        created = True
    except IntegrityError:
        conn.rollback()
        created = False

    conn.close()

    return created


def get_user_by_email(email):
    """Return (id, email, password_hash, created_at, is_admin) for this
    email, or None if no user has that email."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(_q("SELECT id, email, password_hash, created_at, is_admin FROM users WHERE email = ?"), (email,))
    user = cursor.fetchone()

    conn.close()

    return user


def get_all_users():
    """Return every registered user for the admin panel:
    (id, email, created_at, is_admin, watchlist_item_count)."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT u.id, u.email, u.created_at, u.is_admin, COUNT(w.id)
        FROM users u
        LEFT JOIN watchlist w ON w.user_id = u.id
        GROUP BY u.id, u.email, u.created_at, u.is_admin
        ORDER BY u.created_at
    """)
    users = cursor.fetchall()

    conn.close()

    return users


def add_watchlist_item(user_id, make, model, created_at):
    """Add a make (and optionally a model) to a user's watchlist. Leaving
    model blank watches every model of that make. Returns True if added,
    False if that make/model was already on their watchlist."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(_q("""
            INSERT INTO watchlist (user_id, make, model, created_at)
            VALUES (?, ?, ?, ?)
        """), (user_id, make, model, created_at))
        conn.commit()
        added = True
    except IntegrityError:
        conn.rollback()
        added = False

    conn.close()

    return added


def remove_watchlist_item(watchlist_id, user_id):
    """Delete a watchlist item, only if it belongs to this user."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(_q("DELETE FROM watchlist WHERE id = ? AND user_id = ?"), (watchlist_id, user_id))

    conn.commit()
    conn.close()


def get_watchlist(user_id):
    """Return [(id, make, model), ...] for everything this user is watching."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(_q("SELECT id, make, model FROM watchlist WHERE user_id = ? ORDER BY make, model"), (user_id,))
    items = cursor.fetchall()

    conn.close()

    return items


def get_matching_vehicles(user_id):
    """Return every vehicle in inventory that matches this user's
    watchlist (make always, model only if they specified one)."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(_q("""
        SELECT DISTINCT v.year, v.make, v.model, v.row_location, v.yard, v.date_found
        FROM watchlist w
        JOIN vehicles v
            ON UPPER(v.make) = UPPER(w.make)
            AND (w.model = '' OR UPPER(v.model) = UPPER(w.model))
        WHERE w.user_id = ?
        ORDER BY v.date_found DESC
    """), (user_id,))
    vehicles = cursor.fetchall()

    conn.close()

    return vehicles


def get_distinct_models_for_make(make):
    """Return every model we've actually seen in inventory for this make, sorted."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(_q("""
        SELECT DISTINCT model FROM vehicles WHERE UPPER(make) = UPPER(?) ORDER BY model
    """), (make,))
    models = [row[0] for row in cursor.fetchall()]

    conn.close()

    return models


def get_recent_vehicles(limit=20):
    """Return the most recently found vehicles across every yard, newest first."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(_q("""
        SELECT year, make, model, row_location, yard, date_found
        FROM vehicles
        ORDER BY id DESC
        LIMIT ?
    """), (limit,))
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
