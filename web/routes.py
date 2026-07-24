from datetime import datetime, timezone
from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database.database import create_user, get_user_by_email

routes = Blueprint("routes", __name__)


def login_required(view):
    """Redirect to the login page if no one is logged in."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("routes.login"))
        return view(*args, **kwargs)
    return wrapped


@routes.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("routes.dashboard"))
    return redirect(url_for("routes.login"))


@routes.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        if not email or not password:
            flash("Email and password are required.")
            return render_template("register.html")

        password_hash = generate_password_hash(password)
        created = create_user(email, password_hash, datetime.now(timezone.utc).isoformat())

        if not created:
            flash("An account with that email already exists.")
            return render_template("register.html")

        flash("Account created! Please log in.")
        return redirect(url_for("routes.login"))

    return render_template("register.html")


@routes.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        user = get_user_by_email(email)

        if user is None or not check_password_hash(user[2], password):
            flash("Incorrect email or password.")
            return render_template("login.html")

        session["user_id"] = user[0]
        session["user_email"] = user[1]
        return redirect(url_for("routes.dashboard"))

    return render_template("login.html")


@routes.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("routes.login"))


@routes.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", email=session.get("user_email"))
