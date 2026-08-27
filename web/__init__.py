import os
from datetime import datetime, timedelta, timezone

import sentry_sdk
from dotenv import load_dotenv
from flask import Flask, render_template
from sentry_sdk.integrations.flask import FlaskIntegration

from database.database import initialize_database

load_dotenv()

SENTRY_DSN = os.getenv("SENTRY_DSN")
if SENTRY_DSN:
    sentry_sdk.init(dsn=SENTRY_DSN, integrations=[FlaskIntegration()], send_default_pii=False)


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

    # There's no DATABASE_URL locally (SQLite instead), so this doubles as
    # the same "are we actually in production" check used in database.py.
    # SESSION_COOKIE_SECURE would otherwise stop the login cookie from
    # working at all over plain http://localhost.
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = bool(os.getenv("DATABASE_URL"))

    initialize_database()

    from web.routes import routes
    app.register_blueprint(routes)

    @app.errorhandler(404)
    def not_found(error):
        return render_template("error_404.html"), 404

    @app.errorhandler(500)
    def server_error(error):
        return render_template("error_500.html"), 500

    @app.after_request
    def add_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    return app
