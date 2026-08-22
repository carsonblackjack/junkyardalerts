import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from flask import Flask

from database.database import initialize_database

load_dotenv()


def format_us_date(value):
    """Show dates the American way (MM-DD-YYYY) instead of YYYY-MM-DD.
    Works whether the stored value is a plain date or a full timestamp."""
    if not value:
        return value

    date_part = value.split("T")[0]

    try:
        return datetime.strptime(date_part, "%Y-%m-%d").strftime("%m-%d-%Y")
    except ValueError:
        return value


def format_relative_time(value):
    """Show a timestamp as "5 minutes ago" / "3 hours ago" / "2 days ago"
    instead of a raw ISO string, for the yard freshness indicator."""
    if not value:
        return "never"

    try:
        then = datetime.fromisoformat(value)
    except ValueError:
        return value

    if then.tzinfo is None:
        then = then.replace(tzinfo=timezone.utc)

    seconds = (datetime.now(timezone.utc) - then).total_seconds()

    if seconds < 60:
        return "just now"
    if seconds < 3600:
        minutes = int(seconds // 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    if seconds < 86400:
        hours = int(seconds // 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = int(seconds // 86400)
    return f"{days} day{'s' if days != 1 else ''} ago"


def create_app():
    app = Flask(__name__)
    app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-change-me")
    app.permanent_session_lifetime = timedelta(days=30)
    app.jinja_env.filters["us_date"] = format_us_date
    app.jinja_env.filters["relative_time"] = format_relative_time

    initialize_database()

    from web.routes import routes
    app.register_blueprint(routes)

    return app
