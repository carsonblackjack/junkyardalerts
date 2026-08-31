from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database.database import (
    SPOTTED_EXPIRY_DAYS,
    add_watchlist_item,
    create_password_reset_token,
    create_user,
    delete_user_account,
    generate_invite_code_for_email,
    generate_invite_codes,
    get_all_users,
    get_invite_codes,
    get_distinct_models_for_make,
    get_distinct_yards,
    get_distinct_years,
    get_explore_vehicle_count,
    get_explore_vehicles,
    get_inventory_counts_by_yard,
    get_matches_grouped,
    get_recent_vehicles,
    get_user_by_email,
    get_user_by_id,
    get_top_searches,
    get_top_watchlist_demand,
    get_unmet_searches,
    get_unmet_watchlist_demand,
    get_valid_reset_token_user,
    get_watchlist,
    get_yard_sync_times,
    log_login,
    log_search,
    redeem_invite_code,
    remove_watchlist_item,
    search_vehicles,
    set_admin_status,
    toggle_spotted,
    unsubscribe_by_token,
    update_first_name,
    update_notification_preferences,
    update_password_hash,
    use_reset_token,
)
from notifications.notifier import WEBSITE_URL, render_invite_email_html, send_email
from scraper.jalopy import ALL_MAKES as JALOPY_MAKES
from scraper.trusty_pap import ALL_MAKES as TRUSTY_MAKES
from web.turnstile import TURNSTILE_SITE_KEY, verify_turnstile

routes = Blueprint("routes", __name__)

# Every make either yard's website lets you search for, combined.
ALL_MAKES = sorted(set(JALOPY_MAKES) | set(TRUSTY_MAKES))


def spotted_cutoff():
    return (datetime.now(timezone.utc) - timedelta(days=SPOTTED_EXPIRY_DAYS)).isoformat()


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


def super_admin_required(view):
    """Redirect non-super-admins back to the dashboard. Super-admins get
    the analytics view and the ability to grant/revoke admin access."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("routes.login"))
        if not session.get("is_super_admin"):
            flash("You don't have access to that page.")
            return redirect(url_for("routes.dashboard"))
        return view(*args, **kwargs)
    return wrapped


@routes.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("routes.dashboard"))
    return render_template("landing.html")


@routes.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        if not verify_turnstile(request.form.get("cf-turnstile-response"), request.remote_addr):
            flash("Please complete the security check and try again.")
            return render_template("register.html", turnstile_site_key=TURNSTILE_SITE_KEY)

        email = request.form["email"].strip().lower()
        password = request.form["password"]
        first_name = request.form.get("first_name", "").strip()
        invite_code = request.form.get("invite_code", "").strip().upper()

        if not email or not password:
            flash("Email and password are required.")
            return render_template("register.html", turnstile_site_key=TURNSTILE_SITE_KEY)

        if "agree_to_terms" not in request.form:
            flash("You need to agree to the Terms of Service and Privacy Policy to sign up.")
            return render_template("register.html", turnstile_site_key=TURNSTILE_SITE_KEY)

        if not invite_code:
            flash("An invite code is required to sign up during the beta.")
            return render_template("register.html", turnstile_site_key=TURNSTILE_SITE_KEY)

        password_hash = generate_password_hash(password)
        user_id = create_user(email, password_hash, datetime.now(timezone.utc).isoformat(), first_name)

        if not user_id:
            flash("An account with that email already exists.")
            return render_template("register.html", turnstile_site_key=TURNSTILE_SITE_KEY)

        if not redeem_invite_code(invite_code, email, datetime.now(timezone.utc).isoformat()):
            delete_user_account(user_id)
            flash("That invite code isn't valid or has already been used.")
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
        session["first_name"] = user[8]
        session["is_super_admin"] = bool(user[9])
        log_login(user[0], datetime.now(timezone.utc).isoformat())
        return redirect(url_for("routes.dashboard"))

    return render_template("login.html", turnstile_site_key=TURNSTILE_SITE_KEY)


RESET_TOKEN_LIFETIME = timedelta(hours=1)


@routes.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        if not verify_turnstile(request.form.get("cf-turnstile-response"), request.remote_addr):
            flash("Please complete the security check and try again.")
            return render_template("forgot_password.html", turnstile_site_key=TURNSTILE_SITE_KEY)

        email = request.form.get("email", "").strip().lower()
        user = get_user_by_email(email)

        if user:
            token = create_password_reset_token(user[0], datetime.now(timezone.utc).isoformat())
            reset_url = f"{WEBSITE_URL}/reset-password/{token}"
            body = (
                "Someone (hopefully you) asked to reset the password on your YardWatch account.\n\n"
                f"Reset it here: {reset_url}\n\n"
                "This link works once and expires in an hour. If you didn't request this, you can "
                "safely ignore this email - your password won't change unless you use the link above."
            )
            send_email(email, "Reset your YardWatch password", body, include_link_footer=False)

        # Same message whether or not the email matched an account, so this
        # can't be used to check which emails are registered.
        flash("If that email is registered, we've sent a link to reset your password.")
        return redirect(url_for("routes.login"))

    return render_template("forgot_password.html", turnstile_site_key=TURNSTILE_SITE_KEY)


@routes.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    cutoff = (datetime.now(timezone.utc) - RESET_TOKEN_LIFETIME).isoformat()
    user_id = get_valid_reset_token_user(token, cutoff)

    if request.method == "POST":
        if not user_id:
            flash("That reset link is invalid or has expired.")
            return render_template("reset_password.html", valid=False)

        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not password or password != confirm_password:
            flash("Passwords must match and can't be blank.")
            return render_template("reset_password.html", valid=True)

        if not use_reset_token(token, datetime.now(timezone.utc).isoformat()):
            flash("That reset link was already used.")
            return render_template("reset_password.html", valid=False)

        update_password_hash(user_id, generate_password_hash(password))
        flash("Password updated. Please log in.")
        return redirect(url_for("routes.login"))

    return render_template("reset_password.html", valid=bool(user_id))


@routes.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("routes.login"))


@routes.route("/terms")
def terms():
    return render_template("terms.html")


@routes.route("/eula")
def eula():
    return render_template("eula.html")


@routes.route("/feedback")
@login_required
def feedback():
    return render_template("feedback.html")


@routes.route("/privacy")
def privacy():
    return render_template("privacy.html")


@routes.route("/unsubscribe/<token>")
def unsubscribe(token):
    """One click from an email, no login required - turns off every
    email type for whoever owns this token."""
    email = unsubscribe_by_token(token)
    return render_template("unsubscribe.html", email=email)


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
    if search_query:
        search_results = search_vehicles(search_query)
        log_search(search_query, datetime.now(timezone.utc).isoformat())
    else:
        search_results = None

    return render_template(
        "dashboard.html",
        email=session.get("user_email"),
        display_name=session.get("first_name") or session.get("user_email"),
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
        yard_sync_times=get_yard_sync_times(),
    )


@routes.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    user_id = session["user_id"]

    if request.method == "POST":
        first_name = request.form.get("first_name", "").strip()
        update_first_name(user_id, first_name)
        session["first_name"] = first_name

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
        first_name=user[5],
        notify_daily_summary=bool(user[2]),
        notify_recently_found=bool(user[3]),
        notify_watchlist_matches=bool(user[4]),
    )


@routes.route("/settings/change-password", methods=["POST"])
@login_required
def change_password():
    user = get_user_by_email(session["user_email"])
    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirm_new_password = request.form.get("confirm_new_password", "")

    if not check_password_hash(user[2], current_password):
        flash("Current password is incorrect.")
    elif not new_password or new_password != confirm_new_password:
        flash("New passwords must match and can't be blank.")
    else:
        update_password_hash(user[0], generate_password_hash(new_password))
        flash("Password updated.")

    return redirect(url_for("routes.settings"))


@routes.route("/account/delete", methods=["POST"])
@login_required
def account_delete():
    if session.get("is_super_admin"):
        flash("Admin accounts can't be deleted this way - contact yardwatchadmin@gmail.com.")
        return redirect(url_for("routes.settings"))

    delete_user_account(session["user_id"])
    session.clear()
    flash("Your account and all its data have been deleted.")
    return redirect(url_for("routes.login"))


EXPLORE_PAGE_SIZE = 200


@routes.route("/explore")
@login_required
def explore():
    user_id = session["user_id"]

    yard = request.args.get("yard", "")
    make = request.args.get("make", "").strip().upper()
    model = request.args.get("model", "").strip().upper()
    year_from = request.args.get("year_from", "").strip()
    year_to = request.args.get("year_to", "").strip()

    page = max(request.args.get("page", 1, type=int), 1)
    offset = (page - 1) * EXPLORE_PAGE_SIZE

    total_count = get_explore_vehicle_count(yard=yard, make=make, model=model, year_from=year_from, year_to=year_to)
    total_pages = max((total_count + EXPLORE_PAGE_SIZE - 1) // EXPLORE_PAGE_SIZE, 1)
    page = min(page, total_pages)
    offset = (page - 1) * EXPLORE_PAGE_SIZE

    vehicles = get_explore_vehicles(
        user_id, spotted_cutoff(), yard=yard, make=make, model=model, year_from=year_from, year_to=year_to,
        limit=EXPLORE_PAGE_SIZE, offset=offset,
    )

    return render_template(
        "explore.html",
        email=session.get("user_email"),
        vehicles=vehicles,
        yards=get_distinct_yards(),
        makes=ALL_MAKES,
        years=get_distinct_years(),
        selected_yard=yard,
        selected_make=make,
        selected_model=model,
        selected_year_from=year_from,
        selected_year_to=year_to,
        page=page,
        total_pages=total_pages,
        total_count=total_count,
        range_start=offset + 1 if total_count else 0,
        range_end=min(offset + EXPLORE_PAGE_SIZE, total_count),
    )


@routes.route("/spotted/toggle/<int:vehicle_id>", methods=["POST"])
@login_required
def spotted_toggle(vehicle_id):
    now_spotted = toggle_spotted(session["user_id"], vehicle_id, datetime.now(timezone.utc).isoformat())
    return jsonify({"spotted": now_spotted})


@routes.route("/admin")
@admin_required
def admin():
    users = get_all_users()
    counts_by_yard = get_inventory_counts_by_yard()
    total_vehicles = sum(count for _, count in counts_by_yard)
    viewer_is_super_admin = session.get("is_super_admin", False)

    context = {
        "users": users,
        "counts_by_yard": counts_by_yard,
        "total_vehicles": total_vehicles,
        "viewer_is_super_admin": viewer_is_super_admin,
    }

    if viewer_is_super_admin:
        context.update(
            top_searches=get_top_searches(),
            top_watchlist_demand=get_top_watchlist_demand(),
            unmet_searches=get_unmet_searches(),
            unmet_watchlist_demand=get_unmet_watchlist_demand(),
            invite_codes=get_invite_codes(),
        )

    return render_template("admin.html", **context)


@routes.route("/admin/set-admin/<int:user_id>", methods=["POST"])
@super_admin_required
def admin_set_admin(user_id):
    make_admin = request.form.get("make_admin") == "1"
    set_admin_status(user_id, make_admin)
    return redirect(url_for("routes.admin"))


@routes.route("/admin/generate-codes", methods=["POST"])
@super_admin_required
def admin_generate_codes():
    count = request.form.get("count", type=int) or 0
    count = max(min(count, 100), 1)
    generate_invite_codes(count, datetime.now(timezone.utc).isoformat())
    return redirect(url_for("routes.admin"))


@routes.route("/admin/invite", methods=["POST"])
@super_admin_required
def admin_invite():
    email = request.form.get("email", "").strip().lower()
    if not email:
        flash("Enter an email to send an invite.")
        return redirect(url_for("routes.admin"))

    code = generate_invite_code_for_email(email, datetime.now(timezone.utc).isoformat())
    body = (
        "You've been invited to an exclusive beta test of YardWatch - it checks Idaho "
        "junkyard inventory several times a day and emails you the moment a car you're "
        "after shows up, so you don't have to keep checking yourself.\n\n"
        f"Your invite code: {code}\n\n"
        f"Sign up here: {WEBSITE_URL}/register\n"
        "Paste that code in when you register.\n\n"
        "Thanks for being part of the beta - your feedback matters more than almost "
        "anything else right now. Good, bad, or just confusing, I want to hear it.\n\n"
        "- Carson, Founder"
    )
    send_email(
        email, "You're invited to the YardWatch beta", body,
        include_link_footer=False, html_body=render_invite_email_html(code),
    )
    flash(f"Invite sent to {email}.")
    return redirect(url_for("routes.admin"))


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
