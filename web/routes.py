from datetime import datetime, timezone
from functools import wraps

from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database.database import (
    add_watchlist_item,
    create_user,
    get_distinct_models_for_make,
    get_matching_vehicles,
    get_user_by_email,
    get_watchlist,
    remove_watchlist_item,
)
from scraper.jalopy import ALL_MAKES as JALOPY_MAKES
from scraper.trusty_pap import ALL_MAKES as TRUSTY_MAKES

routes = Blueprint("routes", __name__)

# Every make either yard's website lets you search for, combined.
ALL_MAKES = sorted(set(JALOPY_MAKES) | set(TRUSTY_MAKES))


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
    user_id = session["user_id"]
    watchlist = get_watchlist(user_id)
    matches = get_matching_vehicles(user_id)
    return render_template(
        "dashboard.html",
        email=session.get("user_email"),
        watchlist=watchlist,
        matches=matches,
        makes=ALL_MAKES,
    )


@routes.route("/api/models/<make>")
@login_required
def api_models(make):
    """Models we've seen in inventory for this make, used to fill in the
    model dropdown after a make is picked."""
    return jsonify(get_distinct_models_for_make(make))


@routes.route("/watchlist/add", methods=["POST"])
@login_required
def watchlist_add():
    make = request.form["make"].strip().upper()
    model = request.form.get("model", "").strip().upper()

    if not make:
        flash("Make is required.")
        return redirect(url_for("routes.dashboard"))

    added = add_watchlist_item(session["user_id"], make, model, datetime.now(timezone.utc).isoformat())

    if not added:
        flash("That's already on your watchlist.")

    return redirect(url_for("routes.dashboard"))


@routes.route("/watchlist/remove/<int:item_id>", methods=["POST"])
@login_required
def watchlist_remove(item_id):
    remove_watchlist_item(item_id, session["user_id"])
    return redirect(url_for("routes.dashboard"))
