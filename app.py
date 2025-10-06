from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import sqlite3
import urllib.parse
from datetime import datetime, timedelta
import smtplib, ssl, random, string
from email.mime.text import MIMEText

app = Flask(__name__)
app.secret_key = "tingle_secret"

USER_DB = "users.db"
STOCK_DB = "trading_bot.db"

# ---------------- DB Helpers ----------------
def get_user_db():
    conn = sqlite3.connect(USER_DB)
    conn.row_factory = sqlite3.Row
    return conn

def get_stock_db():
    return sqlite3.connect(STOCK_DB)

def init_stock_db():
    conn = get_stock_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def add_stock_db(stock_name):
    conn = get_stock_db()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO stocks (name) VALUES (?)", (stock_name,))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    conn.close()

def get_all_stocks():
    conn = get_stock_db()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM stocks ORDER BY name COLLATE NOCASE")
    stocks = [row[0] for row in cursor.fetchall()]
    conn.close()
    return stocks

# ---------------- User Routes ----------------
@app.route("/")
def home():
    return render_template("login.html")

@app.route("/login", methods=["POST"])
def login():
    username = request.form["username"]
    password = request.form["password"]

    conn = get_user_db()
    user = conn.execute("SELECT * FROM users WHERE username=? AND password=?", 
                        (username, password)).fetchone()
    conn.close()

    if user:
        session["username"] = username
        flash("Login successful!", "success")
        return redirect(url_for("index"))
    else:
        flash("Invalid username or password", "danger")
        return redirect(url_for("home"))

@app.route("/register", methods=["POST"])
def register():
    username = request.form["username"]
    password = request.form["password"]
    confirm = request.form["confirm"]
    phone = request.form["phone"]
    email = request.form["email"]

    if password != confirm:
        flash("Passwords do not match", "danger")
        return redirect(url_for("home"))

    conn = get_user_db()
    try:
        conn.execute("INSERT INTO users (username, password, phone, email) VALUES (?, ?, ?,?)", 
                     (username, password, phone, email))
        conn.commit()
        flash("Registration successful! Please login.", "success")
    except sqlite3.IntegrityError:
        flash("Username already exists!", "danger")
    finally:
        conn.close()

    return redirect(url_for("home"))

@app.route("/logout")
def logout():
    session.pop("username", None)
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))

@app.route('/profile')
def profile():
    return render_template('profile.html')

# ---------------- Email Helper ----------------
def send_email(to_email, subject, body):
    sender_email = "tingletrade@gmail.com"
    sender_password = "jahobigzmiewnbff"  # Create app password in Gmail settings

    msg = MIMEText(body, "plain")
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = to_email

    context = ssl.create_default_context()
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls(context=context)
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, to_email, msg.as_string())

# ---------------- Forgot / Reset Password ----------------
@app.route("/forgot_password", methods=["POST"])
def forgot_password():
    email = request.form.get("email")
    if not email:
        flash("Email is required", "danger")
        return redirect(url_for("home"))

    conn = get_user_db()
    user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    if not user:
        conn.close()
        flash("No account with this email.", "danger")
        return redirect(url_for("home"))

    # Generate OTP
    otp = ''.join(random.choices(string.digits, k=6))
    expiry = datetime.utcnow() + timedelta(minutes=5)

    conn.execute("ALTER TABLE users ADD COLUMN otp TEXT") if "otp" not in [c[1] for c in conn.execute("PRAGMA table_info(users)").fetchall()] else None
    conn.execute("ALTER TABLE users ADD COLUMN otp_expiry TEXT") if "otp_expiry" not in [c[1] for c in conn.execute("PRAGMA table_info(users)").fetchall()] else None

    conn.execute("UPDATE users SET otp=?, otp_expiry=? WHERE email=?", (otp, expiry.isoformat(), email))
    conn.commit()
    conn.close()

    # Save email in session for reset step
    session["reset_email"] = email

    # Send OTP
    send_email(email, "Your Tingle OTP", f"Your OTP is {otp}. It will expire in 5 minutes.")

    flash("OTP sent to your email. Please check!", "info")
    return redirect(url_for("home")+"#forgot")

@app.route("/reset_password", methods=["POST"])
def reset_password():
    email = session.get("reset_email")   # get email from session
    otp = request.form.get("otp")
    new_password = request.form.get("new_password")

    if not email:
        flash("Session expired. Please request OTP again.", "danger")
        return redirect(url_for("home"))

    conn = get_user_db()
    user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()

    if not user:
        flash("Invalid request.", "danger")
        return redirect(url_for("home"))

    # Validate OTP
    if user["otp"] != otp or datetime.utcnow() > datetime.fromisoformat(user["otp_expiry"]):
        flash("Invalid or expired OTP.", "danger")
        return redirect(url_for("home"))

    # Update password & clear OTP
    conn.execute("UPDATE users SET password=?, otp=NULL, otp_expiry=NULL WHERE email=?", (new_password, email))
    conn.commit()
    conn.close()

    # Clear session
    session.pop("reset_email", None)

    flash("Password reset successful! Please login.", "success")
    return redirect(url_for("home"))


# ---------------- Stock Routes ----------------
@app.route("/index", methods=["GET", "POST"])
def index():
    if "username" not in session:
        return redirect(url_for("home"))

    if request.method == "POST":
        stock_name = request.form.get("stock_name") or (request.get_json() or {}).get("stock_name")
        if stock_name:
            stock_name = stock_name.strip()
            if stock_name:
                add_stock_db(stock_name)
        return redirect(url_for("index"))

    stocks = get_all_stocks()
    return render_template("index.html", stocks=stocks, username=session["username"])

@app.route("/stock/<stock_name>")
def stock_page(stock_name):
    stock_name = urllib.parse.unquote(stock_name)
    return render_template("stock.html", stock=stock_name)

# ---------------- API Routes ----------------
@app.route("/get_candles/<stock>")
def get_candles(stock):
    base_price = 100.0 + random.random() * 50
    candles = []
    now = datetime.utcnow()
    for i in range(30):
        t = now - timedelta(minutes=(30 - i) * 15)
        open_p = round(base_price + random.uniform(-3, 3), 2)
        high_p = round(open_p + random.uniform(0, 4), 2)
        low_p = round(open_p - random.uniform(0, 4), 2)
        close_p = round(random.uniform(low_p, high_p), 2)
        candles.append({
            "t": int(t.timestamp() * 1000),
            "o": open_p,
            "h": high_p,
            "l": low_p,
            "c": close_p
        })
        base_price = close_p
    return jsonify(candles)

@app.route("/go", methods=["POST"])
def go():
    payload = request.get_json() or {}
    stock = payload.get("stock") or request.form.get("stock")
    return jsonify({"status": "approved", "stock": stock or None, "message": "Trade approved (simulated)"}), 200

@app.route("/health")
def health():
    return "OK", 200

# ---------------- Main ----------------
if __name__ == "__main__":
    init_stock_db()
    app.run(debug=True)