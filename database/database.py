import os
import sqlite3

DB_NAME = "inventory.db"

# "Spotted" checkmarks on the Explore tab stop counting as checked after
# this many days, so old sightings don't stick around forever.
SPOTTED_EXPIRY_DAYS = 60

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
            is_admin INTEGER NOT NULL DEFAULT 0,
            notify_daily_summary INTEGER NOT NULL DEFAULT 1,
            notify_recently_found INTEGER NOT NULL DEFAULT 1,
            notify_watchlist_matches INTEGER NOT NULL DEFAULT 1,
            first_name TEXT NOT NULL DEFAULT ''
        )
    """)

    user_columns = [
        ("is_admin", "INTEGER NOT NULL DEFAULT 0"),
        ("notify_daily_summary", "INTEGER NOT NULL DEFAULT 1"),
        ("notify_recently_found", "INTEGER NOT NULL DEFAULT 1"),
        ("notify_watchlist_matches", "INTEGER NOT NULL DEFAULT 1"),
        ("first_name", "TEXT NOT NULL DEFAULT ''"),
    ]
    for column, definition in user_columns:
        if USING_POSTGRES:
            cursor.execute(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {column} {definition}")
        else:
            try:
                cursor.execute(f"ALTER TABLE users ADD COLUMN {column} {definition}")
            except sqlite3.OperationalError:
                pass  # already has the column

    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS watchlist (
            {id_column},
            user_id INTEGER NOT NULL,
            make TEXT NOT NULL,
            model TEXT NOT NULL DEFAULT '',
            year_from TEXT NOT NULL DEFAULT '',
            year_to TEXT NOT NULL DEFAULT '',
            created_at TEXT,
            UNIQUE(user_id, make, model),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    if USING_POSTGRES:
        cursor.execute("ALTER TABLE watchlist ADD COLUMN IF NOT EXISTS year_from TEXT NOT NULL DEFAULT ''")
        cursor.execute("ALTER TABLE watchlist ADD COLUMN IF NOT EXISTS year_to TEXT NOT NULL DEFAULT ''")
    else:
        for column in ("year_from", "year_to"):
            try:
                cursor.execute(f"ALTER TABLE watchlist ADD COLUMN {column} TEXT NOT NULL DEFAULT ''")
            except sqlite3.OperationalError:
                pass  # already has the column

    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS spotted (
            {id_column},
            user_id INTEGER NOT NULL,
            vehicle_id INTEGER NOT NULL,
            spotted_at TEXT NOT NULL,
            UNIQUE(user_id, vehicle_id),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (vehicle_id) REFERENCES vehicles(id)
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


def create_user(email, password_hash, created_at, first_name=""):
    """Add a new user. Returns True if created, False if that email is
    already taken (email must be unique)."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(_q("""
            INSERT INTO users (email, password_hash, created_at, first_name)
            VALUES (?, ?, ?, ?)
        """), (email, password_hash, created_at, first_name))
        conn.commit()
        created = True
    except IntegrityError:
        conn.rollback()
        created = False

    conn.close()

    return created


def get_user_by_email(email):
    """Return (id, email, password_hash, created_at, is_admin,
    notify_daily_summary, notify_recently_found, notify_watchlist_matches,
    first_name) for this email, or None if no user has that email."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(_q("""
        SELECT id, email, password_hash, created_at, is_admin,
               notify_daily_summary, notify_recently_found, notify_watchlist_matches,
               first_name
        FROM users WHERE email = ?
    """), (email,))
    user = cursor.fetchone()

    conn.close()

    return user


def get_user_by_id(user_id):
    """Return (id, email, notify_daily_summary, notify_recently_found,
    notify_watchlist_matches, first_name) for this user id, or None."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(_q("""
        SELECT id, email, notify_daily_summary, notify_recently_found,
               notify_watchlist_matches, first_name
        FROM users WHERE id = ?
    """), (user_id,))
    user = cursor.fetchone()

    conn.close()

    return user


def update_notification_preferences(user_id, daily_summary, recently_found, watchlist_matches):
    """Update a user's email notification preferences."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(_q("""
        UPDATE users
        SET notify_daily_summary = ?, notify_recently_found = ?, notify_watchlist_matches = ?
        WHERE id = ?
    """), (int(daily_summary), int(recently_found), int(watchlist_matches), user_id))

    conn.commit()
    conn.close()


def update_first_name(user_id, first_name):
    """Update a user's first name."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(_q("UPDATE users SET first_name = ? WHERE id = ?"), (first_name, user_id))

    conn.commit()
    conn.close()


def get_users_for_notifications():
    """Return every user's notification settings for the scraper to use:
    [(id, email, notify_daily_summary, notify_recently_found, notify_watchlist_matches), ...]."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, email, notify_daily_summary, notify_recently_found, notify_watchlist_matches
        FROM users
    """)
    users = cursor.fetchall()

    conn.close()

    return users


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


def add_watchlist_item(user_id, make, model, created_at, year_from="", year_to=""):
    """Add a make (and optionally a model and year range) to a user's
    watchlist. Leaving model blank watches every model of that make;
    leaving year_from/year_to blank means no limit on that end of the
    range. Returns True if added, False if that make/model was already
    on their watchlist."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(_q("""
            INSERT INTO watchlist (user_id, make, model, year_from, year_to, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """), (user_id, make, model, year_from, year_to, created_at))
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
    """Return [(id, make, model, year_from, year_to), ...] for everything
    this user is watching."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(_q("""
        SELECT id, make, model, year_from, year_to FROM watchlist
        WHERE user_id = ? ORDER BY make, model
    """), (user_id,))
    items = cursor.fetchall()

    conn.close()

    return items


def get_matches_grouped(user_id):
    """Return [(make, model, year_from, year_to, [matching_vehicle_rows]), ...]
    - one group per watchlist item, so matches for different makes/models
    don't get mixed together in one list."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(_q("""
        SELECT make, model, year_from, year_to FROM watchlist
        WHERE user_id = ? ORDER BY make, model
    """), (user_id,))
    items = cursor.fetchall()

    groups = []
    for make, model, year_from, year_to in items:
        cursor.execute(_q("""
            SELECT DISTINCT year, make, model, row_location, yard, date_found
            FROM vehicles
            WHERE UPPER(make) = UPPER(?)
            AND (? = '' OR UPPER(model) = UPPER(?))
            AND (? = '' OR year >= ?)
            AND (? = '' OR year <= ?)
            ORDER BY date_found DESC
        """), (make, model, model, year_from, year_from, year_to, year_to))
        matches = cursor.fetchall()
        groups.append((make, model, year_from, year_to, matches))

    conn.close()

    return groups


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


def get_distinct_years():
    """Return every year we've seen across all inventory, sorted."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT DISTINCT year FROM vehicles ORDER BY year")
    years = [row[0] for row in cursor.fetchall()]

    conn.close()

    return years


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


def search_vehicles(query, limit=100):
    """Return vehicles where the search term appears in year, make,
    model, row, or yard - newest first."""
    conn = get_connection()
    cursor = conn.cursor()

    like_term = f"%{query}%"

    cursor.execute(_q("""
        SELECT year, make, model, row_location, yard, date_found
        FROM vehicles
        WHERE UPPER(year) LIKE UPPER(?)
           OR UPPER(make) LIKE UPPER(?)
           OR UPPER(model) LIKE UPPER(?)
           OR UPPER(row_location) LIKE UPPER(?)
           OR UPPER(yard) LIKE UPPER(?)
        ORDER BY date_found DESC
        LIMIT ?
    """), (like_term, like_term, like_term, like_term, like_term, limit))
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


def get_distinct_yards():
    """Return every yard name we've seen, sorted, for the Explore yard picker."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT DISTINCT yard FROM vehicles ORDER BY yard")
    yards = [row[0] for row in cursor.fetchall()]

    conn.close()

    return yards


def get_explore_vehicles(user_id, spotted_cutoff, yard="", make="", model="", year_from="", year_to="", limit=200):
    """Return vehicles matching the Explore filters, along with whether
    this user has marked each one as spotted (within the last 60 days):
    [(vehicle_id, year, make, model, row_location, yard, date_found, is_spotted), ...]."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(_q("""
        SELECT v.id, v.year, v.make, v.model, v.row_location, v.yard, v.date_found,
               CASE WHEN s.id IS NOT NULL THEN 1 ELSE 0 END
        FROM vehicles v
        LEFT JOIN spotted s
            ON s.vehicle_id = v.id AND s.user_id = ? AND s.spotted_at >= ?
        WHERE (? = '' OR v.yard = ?)
        AND (? = '' OR UPPER(v.make) = UPPER(?))
        AND (? = '' OR UPPER(v.model) = UPPER(?))
        AND (? = '' OR v.year >= ?)
        AND (? = '' OR v.year <= ?)
        ORDER BY v.date_found DESC
        LIMIT ?
    """), (
        user_id, spotted_cutoff,
        yard, yard,
        make, make,
        model, model,
        year_from, year_from,
        year_to, year_to,
        limit,
    ))
    vehicles = cursor.fetchall()

    conn.close()

    return vehicles


def toggle_spotted(user_id, vehicle_id, spotted_at):
    """Mark a vehicle as spotted if it wasn't, or un-mark it if it was.
    Returns the new state (True if now spotted, False if now cleared)."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(_q("SELECT id FROM spotted WHERE user_id = ? AND vehicle_id = ?"), (user_id, vehicle_id))
    existing = cursor.fetchone()

    if existing:
        cursor.execute(_q("DELETE FROM spotted WHERE id = ?"), (existing[0],))
        now_spotted = False
    else:
        cursor.execute(_q("""
            INSERT INTO spotted (user_id, vehicle_id, spotted_at) VALUES (?, ?, ?)
        """), (user_id, vehicle_id, spotted_at))
        now_spotted = True

    conn.commit()
    conn.close()

    return now_spotted


def delete_expired_spotted(cutoff):
    """Clear out spotted marks older than the cutoff (60 days), so the
    table doesn't grow forever and old marks stop showing as checked."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(_q("DELETE FROM spotted WHERE spotted_at < ?"), (cutoff,))

    conn.commit()
    conn.close()
