from datetime import datetime, timezone
from functools import wraps

from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database.database import (
    add_watchlist_item,
    create_user,
    get_all_users,
    get_distinct_models_for_make,
    get_distinct_years,
    get_inventory_counts_by_yard,
    get_matches_grouped,
    get_recent_vehicles,
    get_user_by_email,
    get_user_by_id,
    get_watchlist,
    remove_watchlist_item,
    search_vehicles,
    update_notification_preferences,
)
from scraper.jalopy import ALL_MAKES as JALOPY_MAKES
from scraper.trusty_pap import ALL_MAKES as TRUSTY_MAKES
from web.turnstile import TURNSTILE_SITE_KEY, verify_turnstile

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


def admin_required(view):
    """Redirect non-admins back to the dashboard."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("routes.login"))
        if not session.get("is_admin"):
            flash("You don't have access to that page.")
            return redirect(url_for("routes.dashboard"))
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
        if not verify_turnstile(request.form.get("cf-turnstile-response"), request.remote_addr):
            flash("Please complete the security check and try again.")
            return render_template("register.html", turnstile_site_key=TURNSTILE_SITE_KEY)

        email = request.form["email"].strip().lower()
        password = request.form["password"]

        if not email or not password:
            flash("Email and password are required.")
            return render_template("register.html", turnstile_site_key=TURNSTILE_SITE_KEY)

        password_hash = generate_password_hash(password)
        created = create_user(email, password_hash, datetime.now(timezone.utc).isoformat())

        if not created:
            flash("An account with that email already exists.")
            return render_template("register.html", turnstile_site_key=TURNSTILE_SITE_KEY)

        flash("Account created! Please log in.")
        return redirect(url_for("routes.login"))

    return render_template("register.html", turnstile_site_key=TURNSTILE_SITE_KEY)


@routes.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if not verify_turnstile(request.form.get("cf-turnstile-response"), request.remote_addr):
            flash("Please complete the security check and try again.")
            return render_template("login.html", turnstile_site_key=TURNSTILE_SITE_KEY)

        email = request.form["email"].strip().lower()
        password = request.form["password"]

        user = get_user_by_email(email)

        if user is None or not check_password_hash(user[2], password):
            flash("Incorrect email or password.")
            return render_template("login.html", turnstile_site_key=TURNSTILE_SITE_KEY)

        session.permanent = True
        session["user_id"] = user[0]
        session["user_email"] = user[1]
        session["is_admin"] = bool(user[4])
        return redirect(url_for("routes.dashboard"))

    return render_template("login.html", turnstile_site_key=TURNSTILE_SITE_KEY)


@routes.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("routes.login"))


@routes.route("/dashboard")
@login_required
def dashboard():
    user_id = session["user_id"]
    watchlist = get_watchlist(user_id)
    match_groups = get_matches_grouped(user_id)
    counts_by_yard = get_inventory_counts_by_yard()
    total_vehicles = sum(count for _, count in counts_by_yard)
    recent_vehicles = get_recent_vehicles(20)

    search_query = request.args.get("q", "").strip()
    search_results = search_vehicles(search_query) if search_query else None

    return render_template(
        "dashboard.html",
        email=session.get("user_email"),
        watchlist=watchlist,
        match_groups=match_groups,
        makes=ALL_MAKES,
        years=get_distinct_years(),
        counts_by_yard=counts_by_yard,
        total_vehicles=total_vehicles,
        recent_vehicles=recent_vehicles,
        is_admin=session.get("is_admin", False),
        search_query=search_query,
        search_results=search_results,
    )


@routes.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    user_id = session["user_id"]

    if request.method == "POST":
        update_notification_preferences(
            user_id,
            daily_summary="notify_daily_summary" in request.form,
            recently_found="notify_recently_found" in request.form,
            watchlist_matches="notify_watchlist_matches" in request.form,
        )
        flash("Preferences saved.")
        return redirect(url_for("routes.settings"))

    user = get_user_by_id(user_id)
    return render_template(
        "settings.html",
        email=session.get("user_email"),
        notify_daily_summary=bool(user[2]),
        notify_recently_found=bool(user[3]),
        notify_watchlist_matches=bool(user[4]),
    )


@routes.route("/admin")
@admin_required
def admin():
    users = get_all_users()
    counts_by_yard = get_inventory_counts_by_yard()
    total_vehicles = sum(count for _, count in counts_by_yard)
    return render_template(
        "admin.html",
        users=users,
        counts_by_yard=counts_by_yard,
        total_vehicles=total_vehicles,
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
    year_from = request.form.get("year_from", "").strip()
    year_to = request.form.get("year_to", "").strip()

    if not make:
        flash("Make is required.")
        return redirect(url_for("routes.dashboard"))

    if year_from and year_to and year_from > year_to:
        flash("Year From can't be after Year To.")
        return redirect(url_for("routes.dashboard"))

    added = add_watchlist_item(
        session["user_id"], make, model, datetime.now(timezone.utc).isoformat(), year_from, year_to
    )

    if not added:
        flash("That's already on your watchlist.")

    return redirect(url_for("routes.dashboard"))


@routes.route("/watchlist/remove/<int:item_id>", methods=["POST"])
@login_required
def watchlist_remove(item_id):
    remove_watchlist_item(item_id, session["user_id"])
    return redirect(url_for("routes.dashboard"))
