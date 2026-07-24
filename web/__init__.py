import os

from dotenv import load_dotenv
from flask import Flask

from database.database import initialize_database

load_dotenv()


def create_app():
    app = Flask(__name__)
    app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-change-me")

    initialize_database()

    from web.routes import routes
    app.register_blueprint(routes)

    return app
