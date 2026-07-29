import os
from datetime import datetime, timedelta

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


def create_app():
    app = Flask(__name__)
    app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-change-me")
    app.permanent_session_lifetime = timedelta(days=30)
    app.jinja_env.filters["us_date"] = format_us_date

    initialize_database()

    from web.routes import routes
    app.register_blueprint(routes)

    return app
