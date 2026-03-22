from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
import requests
from transformers import pipeline
from werkzeug.utils import secure_filename
import os
import logging  # <-- FIXED


app = Flask(__name__)
app.secret_key = "supersecretkey"

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="virtual_tutor_ai",
    autocommit=True
)

def get_cursor():
    if not db.is_connected():
        db.reconnect()
    return db.cursor(dictionary=True)

# ================== INDEX ==================
@app.route("/")
def index():
    return render_template("index.html")

# ================== REGISTER ==================
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        role = request.form.get("role")

        if not name or not email or not password or not role:
            flash("All fields are required!", "error")
            return redirect(url_for("register"))

        hashed_password = generate_password_hash(password)
        cursor = get_cursor()

        if role == "user":
            cursor.execute("SELECT id FROM users WHERE email=%s", (email,))
            if cursor.fetchone():
                flash("User already exists!", "error")
            else:
                cursor.execute(
                    "INSERT INTO users (name,email,password) VALUES (%s,%s,%s)",
                    (name, email, hashed_password)
                )
                flash("User registered successfully!", "success")
                return redirect(url_for("login"))

        elif role == "admin":
            cursor.execute("SELECT id FROM admins WHERE email=%s", (email,))
            if cursor.fetchone():
                flash("Admin already exists!", "error")
            else:
                cursor.execute(
                    "INSERT INTO admins (name,email,password) VALUES (%s,%s,%s)",
                    (name, email, hashed_password)
                )
                flash("Admin registered successfully!", "success")
                return redirect(url_for("login"))

        else:
            flash("Invalid role selected!", "error")

    return render_template("register.html")

# ================== LOGIN ==================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        role = request.form.get("role")

        if not email or not password or not role:
            flash("All fields are required!", "error")
            return redirect(url_for("login"))

        cursor = get_cursor()

        if role == "user":
            cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
            user = cursor.fetchone()

            if user and check_password_hash(user["password"], password):
                session.clear()
                session["user_id"] = user["id"]
                session["role"] = "user"
                return redirect(url_for("dashboard_user"))
            else:
                flash("Invalid user email or password!", "error")

        elif role == "admin":
            cursor.execute("SELECT * FROM admins WHERE email=%s", (email,))
            admin = cursor.fetchone()

            if admin and check_password_hash(admin["password"], password):
                session.clear()
                session["admin_id"] = admin["id"]
                session["role"] = "admin"
                return redirect(url_for("dashboard_admin"))
            else:
                flash("Invalid admin email or password!", "error")

        else:
            flash("Invalid role selected!", "error")

    return render_template("login.html")

# ================== LOGOUT ==================
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

# ================== Admin DASHBOARDS ==================
@app.route("/dashboard_admin")
def dashboard_admin():
    if session.get("role") == "admin":
        return render_template("dashboard_admin.html")
    return redirect(url_for("login"))

# ================== MANAGE USERS ==================
@app.route("/manage_users", methods=["GET", "POST"])
def manage_users():
    if session.get("role") != "admin":
        return redirect(url_for("login"))

    cursor = get_cursor()   # REQUIRED

    if request.method == "POST":
        action = request.form.get("action")
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")

        # ===== ADD USER =====
        if action == "add":
            if not name or not email or not password:
                flash("All fields are required!", "error")
                return redirect(url_for("manage_users"))

            cursor.execute(
                "SELECT id FROM users WHERE email=%s",
                (email,)
            )
            if cursor.fetchone():
                flash("Email already exists!", "error")
            else:
                hashed_password = generate_password_hash(password)

                cursor.execute(
                    "INSERT INTO users (name,email,password) VALUES (%s,%s,%s)",
                    (name, email, hashed_password)
                )
                flash("User added successfully!", "success")

    # Fetch all users
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()

    return render_template("manage_users.html", users=users)

# ================== EDIT USER ==================
@app.route("/edit_user/<int:user_id>", methods=["GET", "POST"])
def edit_user(user_id):
    if session.get("role") != "admin":
        return redirect(url_for("login"))

    cursor = get_cursor()   # REQUIRED

    # Fetch user
    cursor.execute(
        "SELECT * FROM users WHERE id=%s",
        (user_id,)
    )
    user = cursor.fetchone()

    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")

        # Check duplicate email
        cursor.execute(
            "SELECT id FROM users WHERE email=%s AND id!=%s",
            (email, user_id)
        )
        if cursor.fetchone():
            flash("Email already used by another user!", "error")
            return redirect(url_for("edit_user", user_id=user_id))

        # Update logic
        if password:
            hashed_password = generate_password_hash(password)
            cursor.execute(
                "UPDATE users SET name=%s, email=%s, password=%s WHERE id=%s",
                (name, email, hashed_password, user_id)
            )
        else:
            cursor.execute(
                "UPDATE users SET name=%s, email=%s WHERE id=%s",
                (name, email, user_id)
            )

        flash("User updated successfully!", "success")
        return redirect(url_for("manage_users"))

    return render_template("edit_user.html", user=user)


# ================== DELETE USER ==================
@app.route("/delete_user/<int:user_id>")
def delete_user(user_id):
    if session.get("role") != "admin":
        return redirect(url_for("login"))

    cursor = get_cursor()   

    cursor.execute(
        "DELETE FROM users WHERE id=%s",
        (user_id,)
    )

    flash("User deleted successfully!", "success")
    return redirect(url_for("manage_users"))

# ================== MANAGE SUBSCRIPTIONS ==================
@app.route("/manage_subscriptions", methods=["GET", "POST"])
def manage_subscriptions():
    if session.get("role") != "admin":
        return redirect(url_for("login"))

    cursor = get_cursor()   # REQUIRED

    if request.method == "POST":
        action = request.form.get("action")
        name = request.form.get("name")
        price = request.form.get("price")
        duration_days = request.form.get("duration_days")

        # ===== ADD SUBSCRIPTION =====
        if action == "add":
            cursor.execute(
                "SELECT id FROM subscriptions WHERE name=%s",
                (name,)
            )
            if cursor.fetchone():
                flash("Error: Subscription already exists!", "error")
            else:
                cursor.execute(
                    "INSERT INTO subscriptions (name, price, duration_days) VALUES (%s,%s,%s)",
                    (name, price, duration_days)
                )
                flash("Subscription added successfully!", "success")

    # Fetch all subscriptions
    cursor.execute("SELECT * FROM subscriptions")
    subscriptions = cursor.fetchall()

    return render_template(
        "manage_subscriptions.html",
        subscriptions=subscriptions
    )

# ================== EDIT SUBSCRIPTION ==================
@app.route("/edit_subscription/<int:sub_id>", methods=["GET", "POST"])
def edit_subscription(sub_id):
    if session.get("role") != "admin":
        return redirect(url_for("login"))

    cursor = get_cursor()   # REQUIRED

    cursor.execute(
        "SELECT * FROM subscriptions WHERE id=%s",
        (sub_id,)
    )
    subscription = cursor.fetchone()

    if request.method == "POST":
        name = request.form["name"]
        price = request.form["price"]
        duration_days = request.form["duration_days"]

        cursor.execute(
            "SELECT id FROM subscriptions WHERE name=%s AND id!=%s",
            (name, sub_id)
        )
        if cursor.fetchone():
            flash("Error: Subscription name already used!", "error")
        else:
            cursor.execute(
                """
                UPDATE subscriptions
                SET name=%s, price=%s, duration_days=%s
                WHERE id=%s
                """,
                (name, price, duration_days, sub_id)
            )
            flash("Subscription updated successfully!", "success")
            return redirect(url_for("manage_subscriptions"))

    return render_template(
        "edit_subscription.html",
        subscription=subscription
    )


# ================== DELETE SUBSCRIPTION ==================
@app.route("/delete_subscription/<int:sub_id>")
def delete_subscription(sub_id):
    if session.get("role") != "admin":
        return redirect(url_for("login"))

    cursor = get_cursor()   

    cursor.execute(
        "DELETE FROM subscriptions WHERE id=%s",
        (sub_id,)
    )

    flash("Success: Subscription deleted successfully!", "success")
    return redirect(url_for("manage_subscriptions"))


# ================== USER DASHBOARD ==================
@app.route("/dashboard_user")
def dashboard_user():
    if session.get("role") != "user":
        return redirect(url_for("login"))

    cursor = get_cursor()   # REQUIRED

    # Fetch user profile
    cursor.execute(
        "SELECT id, name FROM users WHERE id=%s",
        (session["user_id"],)
    )
    user = cursor.fetchone()

    # Fetch user's active subscription
    cursor.execute("""
        SELECT s.name, s.price, s.duration_days
        FROM subscriptions s
        JOIN user_subscriptions us ON s.id = us.subscription_id
        WHERE us.user_id = %s AND us.status='active'
    """, (session["user_id"],))
    subscription = cursor.fetchone()

    return render_template(
        "dashboard_user.html",
        user=user,
        subscription=subscription
    )


# ================== UPDATE USER PROFILE ==================
@app.route("/profile_user", methods=["GET", "POST"])
def profile_user():
    if session.get("role") != "user":
        return redirect(url_for("login"))

    cursor = get_cursor()   

    # Fetch current user info
    cursor.execute(
        "SELECT * FROM users WHERE id=%s",
        (session["user_id"],)
    )
    user = cursor.fetchone()

    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")

        # Email uniqueness check
        cursor.execute(
            "SELECT id FROM users WHERE email=%s AND id!=%s",
            (email, session["user_id"])
        )
        if cursor.fetchone():
            flash("Email already exists!", "error")
            return redirect(url_for("profile_user"))

        # Hash password ONLY if user entered new one
        if password:
            from werkzeug.security import generate_password_hash
            hashed_password = generate_password_hash(password)

            cursor.execute(
                "UPDATE users SET name=%s, email=%s, password=%s WHERE id=%s",
                (name, email, hashed_password, session["user_id"])
            )
        else:
            cursor.execute(
                "UPDATE users SET name=%s, email=%s WHERE id=%s",
                (name, email, session["user_id"])
            )

        flash("Profile updated successfully!", "success")
        return redirect(url_for("profile_user"))

    return render_template("profile_user.html", user=user)

# ================== UPDATE Subscription User ==================

@app.route("/subscription_user", methods=["GET", "POST"])
def subscription_user():
    if session.get("role") != "user":
        return redirect(url_for("login"))

    cursor = get_cursor()   


    # Fetch all subscription plans
    cursor.execute("SELECT * FROM subscriptions")
    plans = cursor.fetchall()

    # Fetch user's current subscription
    cursor.execute("""
        SELECT s.id AS subscription_id, s.name, s.price, s.duration_days, us.start_date, us.end_date
        FROM subscriptions s
        JOIN user_subscriptions us ON s.id = us.subscription_id
        WHERE us.user_id=%s AND us.status='active'
    """, (session["user_id"],))
    current_subscription = cursor.fetchone()

    message = None

    if request.method == "POST":
        selected_plan_id = request.form.get("plan")
        if selected_plan_id:
            # Deactivate previous subscription
            cursor.execute("""
                UPDATE user_subscriptions 
                SET status='inactive' 
                WHERE user_id=%s AND status='active'
            """, (session["user_id"],))

            # Add new subscription
            cursor.execute("""
                INSERT INTO user_subscriptions (user_id, subscription_id, status, start_date, end_date)
                VALUES (%s, %s, 'active', CURDATE(), DATE_ADD(CURDATE(), INTERVAL (SELECT duration_days FROM subscriptions WHERE id=%s) DAY))
            """, (session["user_id"], selected_plan_id, selected_plan_id))

            db.commit()
            message = "Success: Subscription updated successfully!"

            # Refresh current_subscription
            cursor.execute("""
                SELECT s.id AS subscription_id, s.name, s.price, s.duration_days, us.start_date, us.end_date
                FROM subscriptions s
                JOIN user_subscriptions us ON s.id = us.subscription_id
                WHERE us.user_id=%s AND us.status='active'
            """, (session["user_id"],))
            current_subscription = cursor.fetchone()

    return render_template("subscription_user.html", plans=plans, current_subscription=current_subscription, message=message)


from gtts import gTTS
from flask import jsonify

@app.route("/tts_ur", methods=["POST"])
def tts_ur():
    text = request.form.get("text", "")
    if not text:
        return jsonify({"error": "No text provided"}), 400

    try:
        # Urdu TTS
        tts = gTTS(text=text, lang="ur")  
        tts_file = "static/tts.mp3"
        tts.save(tts_file)

        return jsonify({"audio": "/" + tts_file})
    except Exception as e:
        return jsonify({"error": f"TTS generation failed: {e}"}), 500


# ================== AVATARS & CONFIG ==================
from deep_translator import GoogleTranslator
import logging

avatars = [
    {"name": "Business Avatar", "filename": "business"},
    {"name": "Healthcare Avatar", "filename": "healthcare"},
    {"name": "Tour Guide Avatar", "filename": "tourguide"}
]

languages = {
    "en-US": "English",
    "ur-PK": "Urdu",
    "es-ES": "Spanish",
    "fr-FR": "French",
    "de-DE": "German"
}

voices = ["male", "female"]

# ================== AI RESPONSE FUNCTION ==================
def lang_map(lang):
    return {
        "en-US": "en",
        "ur-PK": "ur",
        "es-ES": "es",
        "fr-FR": "fr",
        "de-DE": "de"
    }.get(lang, "en")


def generate_ai_response(user_input, avatar_role, selected_language):
    """
    Returns response in selected language (Urdu + 5 languages)
    """
    try:
        target_lang = lang_map(selected_language)

        response = GoogleTranslator(
            source="auto",
            target=target_lang
        ).translate(user_input)

    except Exception as e:
        logging.error(f"Translation failed: {e}")
        response = user_input

    return response

# ================== AVATAR PAGE ==================
@app.route("/avatars_user", methods=["GET", "POST"])
def avatars_user():

    if session.get("role") != "user":
        return redirect(url_for("login"))

    ai_response = None
    selected_avatar = avatars[0]["filename"]
    selected_language = "en-US"
    selected_voice = "female"

    if request.method == "POST":
        user_input = request.form.get("user_input", "").strip()
        selected_avatar = request.form.get("avatar_image", selected_avatar)
        selected_language = request.form.get("language", selected_language)
        selected_voice = request.form.get("voice", selected_voice)

        if user_input:
            ai_response = generate_ai_response(
                user_input,
                selected_avatar,
                selected_language
            )

    return render_template(
        "avatars_user.html",
        avatars=avatars,
        ai_response=ai_response,
        selected_avatar=selected_avatar,
        selected_language=selected_language,
        selected_voice=selected_voice,
        languages=languages,
        voices=voices
    )



# ================== RUN APP ==================
if __name__ == "__main__":
    app.run(debug=True)
