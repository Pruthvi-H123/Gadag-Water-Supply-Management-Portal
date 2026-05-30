from flask import Flask, render_template, request, redirect, session, flash, url_for
import pymysql
import mysql.connector
from werkzeug.utils import secure_filename
import os
from werkzeug.security import generate_password_hash, check_password_hash
from apscheduler.schedulers.background import BackgroundScheduler 
from datetime import datetime, timedelta
import re 
app = Flask(__name__)
app.secret_key = "secret123"
from flask_mail import Mail, Message

from PIL import Image, ImageDraw, ImageFont
import random
import string
import io
from flask import send_file, session

# Email configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'gadagwatersupply@gmail.com'
app.config['MAIL_PASSWORD'] = 'jahwhizzcgcyiayi'  # paste your app password

mail = Mail(app)

def send_email(to_email, subject, body):
    msg = Message(
        subject,
        sender="gadagwatersupply@gmail.com",
        recipients=[to_email]
    )
    msg.body = body
    mail.send(msg)

def save_notification(user_id, message, notification_type):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO notification (user_id, message, notification_type, read_status, sent_date, created_at)
        VALUES (%s, %s, %s, 'Unread', NOW(), NOW())
    """, (user_id, message, notification_type))
    conn.commit()
    conn.close()

@app.context_processor
def inject_unread_count():
    if session.get("role") == "user":
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) as cnt FROM notification 
            WHERE user_id=%s AND read_status='Unread'
        """, (session["user_id"],))
        result = cursor.fetchone()
        conn.close()
        return {"unread_count": result["cnt"]}
    return {"unread_count": 0}
# ---------------- UPLOAD FOLDER ----------------
UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# ---------------- DATABASE CONNECTION ----------------
def get_connection():
    return pymysql.connect(
        host="localhost",
        user="root",
        password="",
        database="gadag_water_supply",
        cursorclass=pymysql.cursors.DictCursor
    )

# ---------------- HOME ----------------
@app.route("/")
def home():
    return render_template("home.html")

# Public pages
@app.route("/about")
def about():
    # Default content
    content = {"about": "Welcome to our About page."}
    
    # If admin has edited content in session (optional)
    if "content_updates" in session and "about" in session["content_updates"]:
        content["about"] = session["content_updates"]["about"]
    
    return render_template("about.html", content=content)

@app.route("/contact", methods=["GET", "POST"])
def contact():
    content = {"contact": "Contact us at XYZ."}
    if "content_updates" in session and "contact" in session["content_updates"]:
        content["contact"] = session["content_updates"]["contact"]

    if request.method == "POST":
        subject = request.form.get("subject")
        message = request.form.get("message")
        user_email = session.get("user_email", "gadagwatersupply@gmail.com")

        try:
            send_email(
                "gadagwatersupply@gmail.com",
                f"Contact Message: {subject}",
                f"""
Message from: {session.get('name', 'User')}
Email: {user_email}

{message}
"""
            )
            flash("Message sent successfully!", "success")
        except Exception as e:
            print("Email error:", e)
            flash("Message sent!", "success")

        return redirect("/contact")

    return render_template("contact.html", content=content)
# ---------------- REGISTER ----------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if "role" in session:
        if session["role"] == "admin":
            return redirect("/admin_dashboard")
        return redirect("/user_dashboard")
    if request.method == "POST":

        name = request.form["name"]
        if not re.match(r'^[A-Za-z ]+$', name):
            flash("Name should contain only letters and spaces", "danger")
            return redirect("/register")

        email = request.form["email"].strip().lower()
        if " " in email:
            flash("Email must not contain spaces", "danger")
            return redirect("/register")

        phone = request.form["phone"]
        if not re.match(r'^[6-9]\d{9}$', phone):
            flash("Enter valid 10 digit Indian mobile number", "danger")
            return redirect("/register")

        phone = "+91" + phone

        address = request.form["address"]
        ward_id = request.form["ward_id"]
        aadhar_no = request.form["aadhar_no"]

        if not re.match(r'^\d{12}$', aadhar_no):
            flash("Aadhar number must be exactly 12 digits", "danger")
            return redirect("/register")

        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        aadhar_file = request.files["aadhar_file"]

        pattern = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*[@$#!%*?&]).{8,}$'
        if not re.match(pattern, password):
            flash("Password must include uppercase, lowercase and special character", "danger")
            return redirect("/register")

        if password != confirm_password:
            flash("Passwords do not match", "danger")
            return redirect("/register")

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM user WHERE email=%s", (email,))
        existing_user = cursor.fetchone()

        if existing_user:
            conn.close()
            flash("Email already registered!", "danger")
            return redirect("/register")

        hashed_password = generate_password_hash(password)

        filename = ""
        if aadhar_file and aadhar_file.filename != "":
            filename = secure_filename(aadhar_file.filename)
            aadhar_file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

        cursor.execute("""
            INSERT INTO user 
            (name,email,phone,password,address,ward_id,aadhar_no,aadhar_file,role)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,(name,email,phone,hashed_password,address,ward_id,aadhar_no,filename,"user"))

        conn.commit()

        # Get the inserted user's ID
        user_id = cursor.lastrowid

        # Send confirmation email
        try:
          send_email(email, "Registration Successful",
          f"Hello,\n\nYour account has been created successfully.\n\nGadag Water Supply")
        except Exception as e:
          print("Email error:", e)
        
        save_notification(user_id, "Your account has been created successfully.", "Registration")

        flash("Registration Successful! Please Login.", "success")
        return redirect("/login")

    
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT ward_id, ward_name FROM ward ORDER BY ward_id ASC")
    wards = cursor.fetchall()

    conn.close()

    return render_template("register.html", wards=wards)
# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET","POST"])
def login():
    if "user_id" in session:
        role = session.get("role")

        if role == "admin":
            return redirect("/admin_dashboard")
        elif role == "user":
            return redirect("/user_dashboard")
        else:
            session.clear()
            return redirect("/login")
        
    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        user_captcha = request.form.get("captcha_input")

        if user_captcha != session.get("captcha_text"):
          flash("Invalid CAPTCHA", "danger")
          return redirect("/login")

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM user WHERE email=%s",(email,))
        user = cursor.fetchone()

        if user and check_password_hash(user["password"],password):

            cursor.execute(
                "UPDATE user SET last_login = NOW() WHERE user_id=%s",
                (user["user_id"],)
            )

            cursor.execute(
                "INSERT INTO user_log (user_id,login_time) VALUES (%s,NOW())",
                (user["user_id"],)
            )

            conn.commit()

            session["user_id"] = user["user_id"]
            session["role"] = user["role"]
            session["name"] = user["name"]
            session["ward_id"]= user["ward_id"]
            session["show_welcome"]=True
            conn.close()

            if user["role"] == "admin":
                return redirect(url_for("admin_dashboard"))
            else:
                return redirect(url_for("user_dashboard"))

        else:
            conn.close()
            flash("Invalid Email or Password","danger")
            return redirect("/login")

    return render_template("login.html")

@app.route("/captcha")
def captcha():
    chars = string.ascii_uppercase + string.digits
    captcha_text = ''.join(random.choice(chars) for _ in range(5))

    session["captcha_text"] = captcha_text

    # Create image
    img = Image.new('RGB', (150, 50), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Draw text
    draw.text((20, 10), captcha_text, fill=(0, 0, 0))

    # Add noise lines
    for i in range(5):
        x1 = random.randint(0, 150)
        y1 = random.randint(0, 50)
        x2 = random.randint(0, 150)
        y2 = random.randint(0, 50)
        draw.line([(x1, y1), (x2, y2)], fill=(0, 0, 0), width=1)

    # Return image
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    return send_file(buffer, mimetype='image/png')

# ---------------- USER DASHBOARD ----------------
@app.route("/user_dashboard")
def user_dashboard():
    if "role" not in session or session["role"] != "user":
        return redirect("/login")
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user WHERE user_id=%s", (session["user_id"],))
    user = cursor.fetchone()
    conn.close()
    
    show_welcome = session.pop("show_welcome",False)

    return render_template("user_dashboard.html", user=user,show_welcome=show_welcome)

@app.route("/notifications")
def notifications():
    if "role" not in session or session["role"] != "user":
        return redirect("/login")
    
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM notification 
        WHERE user_id=%s 
        ORDER BY created_at DESC
    """, (session["user_id"],))
    notifications = cursor.fetchall()

    # Mark all as read
    cursor.execute("""
        UPDATE notification SET read_status='Read' 
        WHERE user_id=%s
    """, (session["user_id"],))
    conn.commit()
    conn.close()

    return render_template("notifications.html", notifications=notifications)
# ---------------- USER MODULES ----------------
# ---------------- REQUEST NEW CONNECTION ----------------
@app.route("/request_connection", methods=["GET", "POST"])
def request_connection():
    if "role" not in session or session["role"] != "user":
        return redirect("/login")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM user WHERE user_id=%s", (session["user_id"],))
    user = cursor.fetchone()  # fetch user for template

    if request.method == "POST":
        connection_type = request.form["connection_type"]
        
        import random
        meter_number = f"MTR-{random.randint(1000,9999)}"
        
        cursor.execute("""
            INSERT INTO connection_request (user_id, connection_type, request_status, created_at)
            VALUES (%s, %s, 'Pending', NOW())
        """, (session["user_id"], connection_type))
        conn.commit()

        request_id = cursor.lastrowid  # ✅ right after commit

        cursor.execute("""
          INSERT INTO water_connection (user_id, connection_type, meter_number, connection_status, connection_date)
          VALUES (%s, %s, %s, 'Pending', NOW())
        """, (session["user_id"], connection_type, meter_number))

        connection_id = cursor.lastrowid

        # ✅ Update water_connection with request_id
        cursor.execute("""
          UPDATE water_connection SET request_id=%s WHERE connection_id=%s
        """, (request_id, connection_id))
        conn.commit()

        return redirect(f"/pay_security_deposit/{request_id}")

    conn.close()
    return render_template("request_connection.html", user=user)


@app.route("/pay_security_deposit/<int:request_id>", methods=["GET", "POST"])
def pay_security_deposit(request_id):
    if "role" not in session or session["role"] != "user":
        return redirect("/login")

    conn = get_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    # STEP 1: Fetch connection request
    cursor.execute("""
        SELECT * FROM connection_request
        WHERE request_id=%s AND user_id=%s
    """, (request_id, session["user_id"]))
    req = cursor.fetchone()

    if not req:
        conn.close()
        flash("Request not found!", "danger")
        return redirect("/my_requests")

    # ✅ STEP 2: Dynamic amount based on connection type
    deposit_rates = {
        "Domestic": 20000,
        "Commercial": 25000
    }
    amount = deposit_rates.get(req["connection_type"], 20000)

    # STEP 3: Check if already paid
    cursor.execute("""
        SELECT * FROM payment
        WHERE request_id=%s 
        AND payment_type='Security Deposit'
        AND payment_status='Paid'
    """, (request_id,))
    paid = cursor.fetchone()

    if paid:
        conn.close()
        return render_template("pay_security.html",
                               request_id=request_id,
                               txn_id=paid["transaction_id"],
                               amount=amount,
                               qr_url="",
                               is_paid=True)

    # STEP 4: Check pending payment
    cursor.execute("""
        SELECT * FROM payment
        WHERE request_id=%s 
        AND payment_type='Security Deposit'
        AND payment_status='Pending'
    """, (request_id,))
    existing = cursor.fetchone()

    import random, string

    if existing:
        txn_id = existing["transaction_id"]
    else:
        txn_id = "SD" + "".join(random.choices(string.digits, k=10))

        cursor.execute("""
            INSERT INTO payment (
                bill_id,request_id,user_id, payment_date,
                payment_mode, amount_paid, payment_status,
                transaction_id, payment_type, created_at
            )
            VALUES (NULL,%s,%s,NOW(), 'QR Code', %s, 'Pending',
                    %s, 'Security Deposit', NOW())
        """, (request_id, session["user_id"], amount, txn_id))

        conn.commit()

    # STEP 5: Generate QR
    import socket
    def get_local_ip():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"

    local_ip = get_local_ip()

    verify_url = f"http://{local_ip}:5000/verify_security_deposit/{txn_id}"
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={verify_url}"

    conn.close()

    return render_template("pay_security.html",
                           request_id=request_id,
                           txn_id=txn_id,
                           amount=amount,
                           qr_url=qr_url,
                           is_paid=False)

@app.route("/check_deposit/<txn_id>")
def check_deposit(txn_id):
    conn = get_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    cursor.execute("""
        SELECT payment_status FROM payment
        WHERE transaction_id=%s
    """, (txn_id,))
    payment = cursor.fetchone()

    conn.close()

    if payment:
        return {"status": payment["payment_status"]}
    return {"status": "Pending"}

@app.route("/verify_security_deposit/<txn_id>", methods=["GET", "POST"])
def verify_security_deposit(txn_id):
    conn = get_connection()
    cursor = conn.cursor()

    # Get payment
    cursor.execute("""
        SELECT * FROM payment WHERE transaction_id=%s
    """, (txn_id,))
    payment = cursor.fetchone()

    if not payment:
        conn.close()
        return "<h3>Invalid Payment Link</h3>"

    # Already paid
    if payment["payment_status"] == "Paid":
        conn.close()
        return "<h3>Already Paid</h3>"

    # GET request → Show mobile payment UI
    if request.method == "GET":
        conn.close()
        return f"""
        <html>
        <head>
        <meta name="viewport" content="width=device-width,initial-scale=1.0"/>
        <title>Pay Security Deposit</title>
        <style>
            *{{margin:0;padding:0;box-sizing:border-box;}}
            body{{font-family:Arial,sans-serif;background:#f0f4ff;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px;}}
            .card{{background:#fff;border-radius:20px;padding:30px;max-width:380px;width:100%;box-shadow:0 10px 40px rgba(0,0,0,0.12);text-align:center;}}
            .logo{{width:60px;height:60px;background:linear-gradient(135deg,#0e63d2,#00b48c);border-radius:15px;display:flex;align-items:center;justify-content:center;margin:0 auto 15px;font-size:1.5rem;color:#fff;}}
            h2{{color:#0a1628;font-size:1.2rem;margin-bottom:5px;}}
            .sub{{color:#888;font-size:0.82rem;margin-bottom:20px;}}
            .amount-box{{background:linear-gradient(135deg,#0e63d2,#0047ab);border-radius:14px;padding:20px;color:#fff;margin-bottom:20px;}}
            .amount-box p{{font-size:0.72rem;opacity:0.8;margin-bottom:5px;text-transform:uppercase;letter-spacing:1px;}}
            .amount-box h1{{font-size:2.2rem;font-weight:900;}}
            .txn{{background:#f8faff;border:1px solid #e8eef8;border-radius:10px;padding:10px;margin-bottom:20px;font-size:0.75rem;color:#666;}}
            .btn-pay{{width:100%;padding:16px;background:linear-gradient(135deg,#00b48c,#007a60);color:#fff;border:none;border-radius:14px;font-size:1.1rem;font-weight:800;cursor:pointer;box-shadow:0 6px 20px rgba(0,180,140,0.4);}}
            .secure{{font-size:0.7rem;color:#aaa;margin-top:12px;}}
        </style>
        </head>
        <body>
          <div class="card">
            <div class="logo">💧</div>
            <h2>Gadag Water Supply</h2>
            <p class="sub">Security Deposit Payment</p>

            <div class="amount-box">
              <p>Amount to Pay</p>
              <h1>₹{payment['amount_paid']}</h1>
            </div>

            <div class="txn">
              Transaction ID: <b style="color:#0e63d2;">{txn_id}</b>
            </div>

            <form method="POST">
              <button type="submit" class="btn-pay">
                ✅ Pay Now
              </button>
            </form>

            <p class="secure">🔒 Simulated Secure Payment • Gadag Municipal</p>
          </div>
        </body>
        </html>
        """

    # POST → user clicks PAY NOW
    if request.method == "POST":
        cursor.execute("""
            UPDATE payment
            SET payment_status='Paid', payment_date=NOW()
            WHERE transaction_id=%s
        """, (txn_id,))

        # update connection_request table also
        cursor.execute("""
           UPDATE connection_request
           SET payment_mode=%s,
           payment_date=NOW()
           WHERE request_id=%s
        """, ("QR Code", payment["request_id"]))
        conn.commit()

        # Get user
        cursor.execute("""
            SELECT name, email FROM user WHERE user_id=%s
        """, (payment["user_id"],))
        user = cursor.fetchone()

        # EMAIL
        send_email(
            user["email"],
            "Security Deposit Payment Successful",
            f"""
Dear {user['name']},

Your security deposit has been successfully paid.

Amount: ₹{payment['amount_paid']}
Transaction ID: {txn_id}

Thank you for using Gadag Water Supply System.
"""
        )

        # NOTIFICATION
        save_notification(
            payment["user_id"],
            "Security Deposit Paid",
            f"Your security deposit of ₹{payment['amount_paid']} has been paid successfully."
        )

        conn.close()

        return """
        <h2 style='text-align:center;margin-top:50px;color:green;'>
        ✅ Payment Successful
        </h2>
        """
# ==========================
# New Connection Route (user submission)
# ==========================
@app.route("/new_connection", methods=["GET", "POST"])
def new_connection():
    if "role" not in session or session["role"] != "user":
        return redirect("/login")

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user WHERE user_id=%s", (session["user_id"],))
    user = cursor.fetchone()

    if request.method == "POST":
        connection_type = request.form["connection_type"]
        security_deposit = 20000
        import random
        request_number = f"REQ-{random.randint(1000,9999)}"

        cursor.execute("""
            INSERT INTO connection_request
            (user_id, connection_type, security_deposit, request_number, request_status,request_date, created_at)
            VALUES (%s, %s, %s, %s, 'Pending', NOW(),NOW())
        """, (session["user_id"], connection_type, security_deposit, request_number))

        conn.commit()
        request_id = cursor.lastrowid
        conn.close()

        flash("Request submitted. Pay security deposit to proceed.","success")
        return redirect(f"/pay_security_deposit/{request_id}")

    conn.close()
    return render_template("new_connection.html", user=user)
# ══════════════════VIEW SCHEDULE════════════════════

@app.route("/view_schedule")
def view_schedule():
    if "role" not in session or session["role"] != "user":
        return redirect("/login")

    import datetime

    conn = get_connection()
    cursor = conn.cursor()

    # Get today's day
    today = datetime.datetime.today().strftime('%A')

    ward_id = request.args.get("ward_id")

    if not ward_id:
      ward_id = session.get("ward_id")

    # Get ALL wards schedules
    cursor.execute("""
        SELECT ss.*, w.ward_name
        FROM supply_schedule ss
        LEFT JOIN ward w ON ss.ward_id = w.ward_id
        ORDER BY w.ward_name, ss.day_of_week
    """)
    schedules = cursor.fetchall()

    # Get all wards for dropdown
    cursor.execute("SELECT ward_id, ward_name FROM ward ORDER BY ward_id ASC")
    wards = cursor.fetchall()

    # Check today's supply for user's own ward
    ward_id = session.get("ward_id")
    today_supply = None
    if ward_id:
        cursor.execute("""
            SELECT ss.*, w.ward_name FROM supply_schedule ss
            LEFT JOIN ward w ON ss.ward_id = w.ward_id
            WHERE ss.ward_id = %s AND ss.day_of_week = %s
        """, (ward_id, today))
        today_supply = cursor.fetchone()

    conn.close()
    return render_template(
        "view_schedule.html",
        schedules=schedules,
        wards=wards,
        today=today,
        today_supply=today_supply
    )

# ---------------- ADD COMPLAINT ----------------
@app.route("/add_complaint", methods=["GET","POST"])
def add_complaint():

    if "role" not in session or session["role"] != "user":
        return redirect("/login")

    user_id = session["user_id"]

    if request.method == "POST":
        complaint_type = request.form["complaint_type"]
        description = request.form["description"]

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO complaint (user_id, complaint_date, complaint_type, description, complaint_status, created_at)
            VALUES (%s,NOW(),%s,%s,'Pending',NOW())
        """, (user_id, complaint_type, description))

        conn.commit()
        
        # fetch email
        cursor.execute("SELECT email FROM user WHERE user_id=%s", (user_id,))
        result = cursor.fetchone()
        user_email = result["email"]

        send_email(
            user_email,
            "Complaint Registered",
            """
        Hello,

        Your complaint has been registered successfully.

        We will resolve it soon.

        Gadag Water Supply
        """
        )

        save_notification(user_id, "Your complaint has been registered successfully.", "Complaint")

        conn.close()

        flash("Complaint added successfully","success")
        return redirect("/user_dashboard")

    return render_template("add_complaint.html")

# ---------------- ADD TANKER REQUEST ----------------
@app.route("/add_tanker_request", methods=["GET","POST"])
def add_tanker_request():

    if "role" not in session or session["role"] != "user":
        return redirect("/login")

    user_id = session["user_id"]

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
     SELECT ward_id, ward_name
     FROM ward
     ORDER BY CAST(REPLACE(ward_name, 'Ward ', '') AS UNSIGNED)
""")
    wards = cursor.fetchall()

    if request.method == "POST":
        ward_id = request.form["ward_id"]
        required_quantity = request.form["required_quantity"]
        request_month = request.form["request_month"]

        # Check if tanker already requested for this ward in this month
        cursor.execute("""
            SELECT * FROM tanker_request
            WHERE ward_id=%s AND request_month=%s
        """, (ward_id, request_month))

        existing = cursor.fetchone()
        if existing:
            conn.close()
            flash("Tanker already requested for this ward in this month","warning")
            return redirect("/add_tanker_request")

        cursor.execute("""
            INSERT INTO tanker_request (ward_id, request_date, required_quantity, status, request_month, created_at)
            VALUES (%s,NOW(),%s,'Pending',%s,NOW())
        """, (ward_id, required_quantity, request_month))

        conn.commit()
        conn.close()

        flash("Tanker request submitted successfully","success")
        return redirect("/user_dashboard")

    conn.close()
    return render_template("add_tanker_request.html", wards=wards)

# ---------------- MY REQUESTS ----------------
@app.route("/my_requests")
def my_requests():

    if "role" not in session or session["role"] != "user":
        return redirect("/login")

    user_id = session["user_id"]

    conn = get_connection()
    cursor = conn.cursor()

    # User complaints
    cursor.execute("SELECT * FROM complaint WHERE user_id=%s ORDER BY created_at DESC", (user_id,))
    complaints = cursor.fetchall()

    # User connections
    cursor.execute("SELECT * FROM water_connection WHERE user_id=%s ORDER BY connection_date DESC", (user_id,))
    connections = cursor.fetchall()

    # User tanker requests (based on ward)
    cursor.execute("""
        SELECT tr.*, w.ward_name 
        FROM tanker_request tr
        JOIN ward w ON tr.ward_id = w.ward_id
        WHERE tr.ward_id IN (SELECT ward_id FROM user WHERE user_id=%s)
        ORDER BY tr.created_at DESC
    """, (user_id,))
    tanker_requests = cursor.fetchall()

    conn.close()

    return render_template("my_requests.html", complaints=complaints, connections=connections, tanker_requests=tanker_requests)

# ── USER: VIEW BILLS ──
@app.route("/my_bills")
def my_bills():
    if "role" not in session or session["role"] != "user":
        return redirect("/login")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT b.*, wc.connection_type, wc.meter_number
        FROM bill b
        LEFT JOIN water_connection wc ON b.connection_id = wc.connection_id
        WHERE b.user_id = %s
        ORDER BY b.created_at DESC
    """, (session["user_id"],))
    bills = cursor.fetchall()
    # Stats
    total = len(bills)
    unpaid = sum(1 for b in bills if b["bill_status"] == "Unpaid")
    paid = sum(1 for b in bills if b["bill_status"] == "Paid")
    conn.close()
    return render_template("my_bills.html", bills=bills, total=total, unpaid=unpaid, paid=paid)


# ── USER: PAY BILL (QR) ──
# ══════════════════════════════════════
# PAYMENT ROUTES — Add to your app.py
# ══════════════════════════════════════
import socket

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

@app.route("/pay_bill/<int:bill_id>", methods=["GET", "POST"])
def pay_bill(bill_id):
    if "role" not in session or session["role"] != "user":
        return redirect("/login")

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT b.*, wc.connection_type, wc.meter_number
        FROM bill b
        LEFT JOIN water_connection wc ON b.connection_id = wc.connection_id
        WHERE b.bill_id = %s AND b.user_id = %s
    """, (bill_id, session["user_id"]))
    bill = cursor.fetchone()

    if not bill:
        conn.close()
        flash("Bill not found!", "danger")
        return redirect("/my_bills")

    if bill["bill_status"] == "Paid":
        conn.close()
        flash("This bill is already paid!", "warning")
        return redirect("/my_bills")

    if request.method == "POST":
        payment_mode = request.form.get("payment_mode", "QR Code")
        txn_id = request.form.get("txn_id")
        cursor.execute("""
            UPDATE payment SET payment_mode = %s
            WHERE transaction_id = %s
        """, (payment_mode, txn_id))
        conn.commit()
    
        conn.close()
        return {"success": True}

    # Generate txn_id
    import random, string
    txn_id = "TXN" + "".join(random.choices(string.digits, k=10))

    # Check if pending payment already exists
    cursor.execute("""
        SELECT * FROM payment
        WHERE bill_id=%s AND payment_status='Pending'
    """, (bill_id,))
    existing = cursor.fetchone()

    if existing:
        txn_id = existing["transaction_id"]
    else:
        cursor.execute("""
            INSERT INTO payment (bill_id, user_id, payment_date, payment_mode,
                                amount_paid, payment_status, transaction_id, created_at)
            VALUES (%s, %s, NOW(), 'QR Code', %s, 'Pending', %s, NOW())
        """, (bill_id, session["user_id"], bill["amount_due"], txn_id))
        conn.commit()

        cursor.execute("""
          SELECT email, name FROM user WHERE user_id=%s
          """, (session["user_id"],))
        user = cursor.fetchone()

        send_email(
           user["email"],
           "New Water Bill Generated",
           f"""
           Dear {user['name']},

            A new water bill has been generated.

        Amount Due: ₹{bill['amount_due']}
        Transaction ID: {txn_id}

        Please complete your payment.

        Gadag Water Supply System
        """
    )

    save_notification(
    session["user_id"],
    "Bill Generated",
    f"A new bill of ₹{bill['amount_due']} has been generated."
    )

    conn.close()

    # Generate QR code URL with local IP
    local_ip = get_local_ip()
    verify_url = f"http://{local_ip}:5000/verify_payment/{txn_id}"
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={verify_url}"

    return render_template("pay_bill.html", bill=bill, txn_id=txn_id, qr_url=qr_url)

@app.route("/verify_payment/<txn_id>", methods=["GET", "POST"])
def verify_payment(txn_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM payment WHERE transaction_id = %s
    """, (txn_id,))
    payment = cursor.fetchone()

    if not payment:
        conn.close()
        return "<h3>Invalid Payment Link</h3>"

    if payment["payment_status"] == "Paid":
        conn.close()
        return "<h3>Already Paid</h3>"

    if request.method == "POST":
        cursor.execute("""
            UPDATE payment SET payment_status='Paid', payment_date=NOW()
            WHERE transaction_id=%s
        """, (txn_id,))

        cursor.execute("""
            UPDATE bill b JOIN payment p ON b.bill_id = p.bill_id
            SET b.bill_status = 'Paid'
            WHERE p.transaction_id = %s
        """, (txn_id,))

        conn.commit()

        cursor.execute("""
            SELECT u.email, u.name, p.amount_paid, p.user_id
            FROM payment p
            JOIN user u ON u.user_id = p.user_id
            WHERE p.transaction_id=%s
        """, (txn_id,))
        user = cursor.fetchone()

        send_email(
            user["email"],
            "Water Bill Payment Successful",
            f"""
Dear {user['name']},

Your water bill payment has been successfully completed.

Amount Paid: ₹{user['amount_paid']}
Transaction ID: {txn_id}

Thank you for using Gadag Water Supply System.
"""
        )

        save_notification(
            user["user_id"],
            "Bill Paid Successfully",
            f"Your payment of ₹{user['amount_paid']} has been completed successfully."
        )
        conn.close()

        return """
        <h2>Payment Successful</h2>
        <p>Your water bill has been paid.</p>
        """

    # GET request
    amount = payment["amount_paid"]
    conn.close()

    return f"""
    <html>
    <head>
    <meta name="viewport" content="width=device-width,initial-scale=1.0"/>
    <title>Pay Water Bill</title>
    <style>
        *{{margin:0;padding:0;box-sizing:border-box;}}
        body{{font-family:Arial,sans-serif;background:#f0f4ff;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px;}}
        .card{{background:#fff;border-radius:20px;padding:30px;max-width:380px;width:100%;box-shadow:0 10px 40px rgba(0,0,0,0.12);text-align:center;}}
        .logo{{width:60px;height:60px;background:linear-gradient(135deg,#0e63d2,#00b48c);border-radius:15px;display:flex;align-items:center;justify-content:center;margin:0 auto 15px;font-size:1.5rem;color:#fff;}}
        h2{{color:#0a1628;font-size:1.2rem;margin-bottom:5px;}}
        .sub{{color:#888;font-size:0.82rem;margin-bottom:20px;}}
        .amount-box{{background:linear-gradient(135deg,#0e63d2,#0047ab);border-radius:14px;padding:20px;color:#fff;margin-bottom:20px;}}
        .amount-box p{{font-size:0.72rem;opacity:0.8;margin-bottom:5px;text-transform:uppercase;letter-spacing:1px;}}
        .amount-box h1{{font-size:2.2rem;font-weight:900;}}
        .txn{{background:#f8faff;border:1px solid #e8eef8;border-radius:10px;padding:10px;margin-bottom:20px;font-size:0.75rem;color:#666;}}
        .btn-pay{{width:100%;padding:16px;background:linear-gradient(135deg,#00b48c,#007a60);color:#fff;border:none;border-radius:14px;font-size:1.1rem;font-weight:800;cursor:pointer;box-shadow:0 6px 20px rgba(0,180,140,0.4);}}
        .secure{{font-size:0.7rem;color:#aaa;margin-top:12px;}}
      </style>
    </head>
    <body>
      <div class="card">
        <div class="logo">💧</div>
        <h2>Gadag Water Supply</h2>
        <p class="sub">Water Bill Payment</p>
        <div class="amount-box">
          <p>Amount to Pay</p>
          <h1>₹{amount}</h1>
        </div>
        <div class="txn">
          Transaction ID: <b style="color:#0e63d2;">{txn_id}</b>
        </div>
        <form method="POST">
          <button type="submit" class="btn-pay">
            ✅ Pay Now
          </button>
        </form>
        <p class="secure">🔒 Simulated Secure Payment • Gadag Municipal</p>
      </div>
    </body>
    </html>
    """




@app.route("/check_payment/<txn_id>")
def check_payment(txn_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT payment_status FROM payment
        WHERE transaction_id = %s
    """, (txn_id,))
    payment = cursor.fetchone()
    conn.close()
    if payment and payment["payment_status"] == "Paid":
        return {"status": "Paid"}
    return {"status": "Pending"}


# ── USER: BILL RECEIPT ──
@app.route("/bill_receipt/<int:bill_id>")
def bill_receipt(bill_id):
    if "role" not in session or session["role"] != "user":
        return redirect("/login")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT b.*, u.name, u.email, u.phone, u.address,
               wc.connection_type, wc.meter_number,
               w.ward_name,
               p.payment_id, p.payment_date, p.payment_mode,
               p.amount_paid, p.payment_status
        FROM bill b
        LEFT JOIN user u ON b.user_id = u.user_id
        LEFT JOIN water_connection wc ON b.connection_id = wc.connection_id
        LEFT JOIN ward w ON u.ward_id = w.ward_id
        LEFT JOIN payment p ON b.bill_id = p.bill_id
        WHERE b.bill_id = %s AND b.user_id = %s
    """, (bill_id, session["user_id"]))
    bill = cursor.fetchone()
    conn.close()
    if not bill:
        flash("Receipt not found!", "danger")
        return redirect("/my_bills")
    return render_template("bill_receipt.html", bill=bill)

# ---------------- USER PROFILE ----------------
@app.route("/profile", methods=["GET","POST"])
def profile():

    if "role" not in session or session["role"] != "user":
        return redirect("/login")

    user_id = session["user_id"]

    conn = get_connection()
    cursor = conn.cursor()

    if request.method == "POST":
        # Get form values
        phone = request.form["phone"]
        phone = phone.replace("+91","").strip()
        address = request.form["address"]
        new_password = request.form.get("new_password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()

        # Validate phone
        import re
        if not re.match(r'^[6-9]\d{9}$', phone):
            flash("Enter valid 10 digit Indian mobile number")
            return redirect("/profile")

        # Update fields
        if new_password:
            # Check password strength
            pattern = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*[@$!%*?&]).{8,}$'
            if not re.match(pattern, new_password):
                flash("Password must include uppercase, lowercase and special character")
                return redirect("/profile")
            if new_password != confirm_password:
                flash("Passwords do not match")
                return redirect("/profile")
            from werkzeug.security import generate_password_hash
            hashed_password = generate_password_hash(new_password)
            cursor.execute("UPDATE user SET phone=%s, address=%s, password=%s WHERE user_id=%s", 
                           (phone, address, hashed_password, user_id))
        else:
            cursor.execute("UPDATE user SET phone=%s, address=%s WHERE user_id=%s", 
                           ("+91"+ phone, address, user_id))

        conn.commit()
        flash("Profile updated successfully","success")
        return redirect("/profile")

    # Fetch user info
    cursor.execute("SELECT u.*, w.ward_name FROM user u LEFT JOIN ward w ON u.ward_id=w.ward_id WHERE u.user_id=%s", (user_id,))
    user = cursor.fetchone()
    conn.close()

    return render_template("profile.html", user=user)

# ---------------- ADMIN DASHBOARD ----------------
@app.route("/admin_dashboard")
def admin_dashboard():

    if "role" not in session or session["role"] != "admin":
        return redirect("/login")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) AS total FROM user WHERE role='user'")
    total_users = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS total FROM water_connection")
    total_connections = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS total FROM complaint")
    total_complaints = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS total FROM complaint WHERE complaint_status='Pending'")
    pending_complaints = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS total FROM tanker_request")
    total_tanker = cursor.fetchone()["total"]

    conn.close()

    show_welcome = session.pop("show_welcome",False)

    return render_template(
        "admin_dashboard.html",
        total_users=total_users,
        total_connections=total_connections,
        total_complaints=total_complaints,
        pending_complaints=pending_complaints,
        total_tanker=total_tanker,
        show_welcome=show_welcome
    )

# ---------------- ADMIN MODULES ----------------
@app.route("/manage_users")
def manage_users():

    if "role" not in session or session["role"] != "admin":
        return redirect("/login")

    search = request.args.get("search")

    conn = get_connection()
    cursor = conn.cursor()

    if search:
        cursor.execute("""
        SELECT u.user_id, u.name, u.email, u.phone, u.user_status, w.ward_name
        FROM user u
        LEFT JOIN ward w ON u.ward_id = w.ward_id
        WHERE u.role='user' AND (u.name LIKE %s OR u.email LIKE %s)
        """, ("%"+search+"%","%"+search+"%"))
    else:
        cursor.execute("""
        SELECT u.user_id, u.name, u.email, u.phone, u.user_status, w.ward_name
        FROM user u
        LEFT JOIN ward w ON u.ward_id = w.ward_id
        WHERE u.role='user'
        """)

    users = cursor.fetchall()

    conn.close()

    return render_template("manage_users.html", users=users)

# ---------------- DELETE USER ----------------
@app.route("/delete_user/<int:user_id>")
def delete_user(user_id):

    if "role" not in session or session["role"] != "admin":
        return redirect("/login")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM user WHERE user_id=%s", (user_id,))

    conn.commit()
    conn.close()

    flash("User deleted successfully","success")

    return redirect(url_for("manage_users"))

# ---------------- WARD MANAGEMENT ----------------
@app.route("/manage_wards")
def manage_wards():

    if "role" not in session or session["role"] != "admin":
        return redirect("/login")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM ward")
    wards = cursor.fetchall()

    conn.close()

    return render_template("manage_wards.html", wards=wards)


# ---------------- ADD WARD PAGE ----------------
@app.route('/add_ward_page')
def add_ward_page():

    if "role" not in session or session["role"] != "admin":
        return redirect("/login")

    return render_template("add_ward.html")


# ---------------- ADD WARD ----------------
@app.route('/add_ward', methods=['POST'])
def add_ward():

    if "role" not in session or session["role"] != "admin":
        return redirect("/login")

    ward_name = request.form['ward_name']
    population = request.form['population']

    conn = get_connection()
    cursor = conn.cursor()
    
    # Check if ward already exists
    cursor.execute(
        "SELECT * FROM ward WHERE ward_name = %s",
        (ward_name,)
    )

    existing_ward = cursor.fetchone()

    if existing_ward:
        flash("Ward already exists!", "danger")
        conn.close()
        return redirect(url_for('manage_wards'))

    cursor.execute(
        "INSERT INTO ward (ward_name, population) VALUES (%s, %s)",
        (ward_name, population)
    )

    conn.commit()
    conn.close()

    flash("Ward added successfully","success")
    return redirect(url_for('manage_wards'))


# ---------------- EDIT WARD PAGE ----------------
@app.route('/edit_ward/<int:ward_id>')
def edit_ward(ward_id):

    if "role" not in session or session["role"] != "admin":
        return redirect("/login")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM ward WHERE ward_id=%s", (ward_id,))
    ward = cursor.fetchone()

    conn.close()

    return render_template("edit_ward.html", ward=ward)


# ---------------- UPDATE WARD ----------------
@app.route('/update_ward/<int:ward_id>', methods=['POST'])
def update_ward(ward_id):

    if "role" not in session or session["role"] != "admin":
        return redirect("/login")

    ward_name = request.form['ward_name']
    population = request.form['population']

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE ward 
        SET ward_name=%s, population=%s 
        WHERE ward_id=%s
    """,(ward_name, population, ward_id))

    conn.commit()
    conn.close()

    flash("Ward updated successfully","success")
    return redirect(url_for("manage_wards"))


# ---------------- DELETE WARD ----------------
@app.route("/delete_ward/<int:ward_id>")
def delete_ward(ward_id):

    if "role" not in session or session["role"] != "admin":
        return redirect("/login")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM ward WHERE ward_id=%s", (ward_id,))

    conn.commit()
    conn.close()

    flash("Ward deleted successfully","success")

    return redirect(url_for("manage_wards"))

# ══════════════════════════════════════
# SUPPLY SCHEDULE ROUTES
# ══════════════════════════════════════

@app.route("/add_schedule", methods=["GET", "POST"])
def add_schedule():
    if "role" not in session or session["role"] != "admin":
        return redirect("/login")

    conn = get_connection()
    cursor = conn.cursor()

    if request.method == "POST":
        ward_id     = request.form["ward_id"]
        day_of_week = request.form["day_of_week"]
        start_time  = request.form["start_time"]
        end_time    = request.form["end_time"]

        cursor.execute("""
            INSERT INTO supply_schedule
            (ward_id, day_of_week, start_time, end_time,created_at)
            VALUES (%s, %s, %s, %s,NOW())
        """, (ward_id, day_of_week, start_time, end_time))
        conn.commit()



        cursor.execute("SELECT email FROM user WHERE ward_id=%s", (ward_id,))
        users = cursor.fetchall()

        # ✅ SEND EMAIL TO ALL USERS
        for u in users:
            send_email(
                u["email"],
                "Water Supply Schedule Update",
                f"""
        Hello,

        Water supply will be available on {day_of_week}
        from {start_time} to {end_time}.

        Gadag Water Supply
        """
        )

        conn.close()
        flash("Schedule added successfully!", "success")
        return redirect("/add_schedule")
    
    # Get all wards
    cursor.execute("SELECT ward_id, ward_name FROM ward ORDER BY ward_id ASC")
    wards = cursor.fetchall()


    # Get all schedules with ward name
    cursor.execute("""
        SELECT ss.*, w.ward_name
        FROM supply_schedule ss
        LEFT JOIN ward w ON ss.ward_id = w.ward_id
        ORDER BY w.ward_name, ss.day_of_week
    """)
    schedules = cursor.fetchall()
    conn.close()
    return render_template("add_schedule.html", wards=wards, schedules=schedules)


@app.route("/delete_schedule/<int:schedule_id>")
def delete_schedule(schedule_id):
    if "role" not in session or session["role"] != "admin":
        return redirect("/login")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM supply_schedule WHERE schedule_id=%s", (schedule_id,))
    conn.commit()
    conn.close()
    flash("Schedule deleted!", "success")
    return redirect("/add_schedule")
# ---------------- VIEW USER DETAILS ----------------
@app.route("/view_user/<int:user_id>")
def view_user(user_id):

    if "role" not in session or session["role"] != "admin":
        return redirect("/login")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT u.*, w.ward_name
        FROM user u
        LEFT JOIN ward w ON u.ward_id = w.ward_id
        WHERE u.user_id=%s
    """, (user_id,))

    user = cursor.fetchone()

    conn.close()

    return render_template("view_user.html", user=user)

# ---------------- BLOCK / UNBLOCK USER ----------------
@app.route("/toggle_user_status/<int:user_id>")
def toggle_user_status(user_id):

    if "role" not in session or session["role"] != "admin":
        return redirect("/login")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT user_status FROM user WHERE user_id=%s",(user_id,))
    user = cursor.fetchone()

    if user["user_status"] == "Active":
        cursor.execute("UPDATE user SET user_status='Blocked' WHERE user_id=%s",(user_id,))
    else:
        cursor.execute("UPDATE user SET user_status='Active' WHERE user_id=%s",(user_id,))

    conn.commit()
    conn.close()

    return redirect(url_for("manage_users"))
#-------------------WATER CONNECTIONS---------------------
@app.route("/connections")
def connections():

    if "role" not in session or session["role"] != "admin":
        return redirect("/login")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT wc.connection_id,
           u.name,
           wc.connection_type,
           wc.meter_number,
           wc.connection_status,
           wc.connection_date
    FROM water_connection wc
    JOIN user u ON wc.user_id = u.user_id
    """)

    connections = cursor.fetchall()

    conn.close()

    return render_template("connections.html", connections=connections)

@app.route("/approve_connection/<int:connection_id>")
def approve_connection(connection_id):
    if "role" not in session or session["role"] != "admin":
        return redirect("/login")

    conn = get_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    # 1. Approve connection
    cursor.execute("""
        UPDATE water_connection
        SET connection_status='Approved'
        WHERE connection_id=%s
    """, (connection_id,))
    conn.commit()

    # 2. Get user details
    cursor.execute("""
        SELECT u.user_id, u.email 
        FROM user u
        JOIN water_connection wc ON u.user_id = wc.user_id
        WHERE wc.connection_id = %s
    """, (connection_id,))
    result = cursor.fetchone()

    user_id = result["user_id"]
    user_email = result["email"]

    # 3. Send email
    send_email(
        user_email,
        "Connection Approved",
        """
Hello,

Your water connection has been approved.

You can now use water services.

Gadag Water Supply
"""
    )

    # 4. Notification
    save_notification(
        user_id,
        "Your water connection has been approved.",
        "Connection"
    )

    conn.close()
    flash("Connection approved successfully!", "success")
    return redirect(url_for("connections"))


@app.route("/reject_connection/<int:connection_id>")
def reject_connection(connection_id):
    if "role" not in session or session["role"] != "admin":
        return redirect("/login")

    conn = get_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    # 1. Reject connection
    cursor.execute("""
        UPDATE water_connection
        SET connection_status='Rejected'
        WHERE connection_id=%s
    """, (connection_id,))

    # 2. Get request_id from water_connection
    cursor.execute("""
        SELECT request_id FROM water_connection
        WHERE connection_id=%s
    """, (connection_id,))
    wc = cursor.fetchone()

    # 3. Update connection_request
    if wc and wc["request_id"]:
        cursor.execute("""
            UPDATE connection_request
            SET request_status='Rejected'
            WHERE request_id=%s
        """, (wc["request_id"],))

    conn.commit()

    # 4. Get user details
    cursor.execute("""
        SELECT u.user_id, u.email 
        FROM user u
        JOIN water_connection wc ON u.user_id = wc.user_id
        WHERE wc.connection_id = %s
    """, (connection_id,))
    result = cursor.fetchone()

    user_id = result["user_id"]
    user_email = result["email"]

    # 5. Send email
    send_email(
        user_email,
        "Connection Rejected",
        """
Hello,

Your water connection request has been rejected.

Please contact office for more details.

Gadag Water Supply
"""
    )

    # 6. Notification
    save_notification(
        user_id,
        "Your water connection has been rejected.",
        "Connection"
    )

    conn.close()
    flash("Connection rejected successfully!", "success")
    return redirect(url_for("connections"))
# ---------------- COMPLAINTS ----------------
@app.route("/complaints")
def complaints():

    if "role" not in session or session["role"] != "admin":
        return redirect("/login")

    conn = get_connection()
    cursor = conn.cursor()

    # Fetch complaints along with user name
    cursor.execute("""
        SELECT c.complaint_id, u.name AS user_name, c.complaint_date,
               c.complaint_type, c.description, c.complaint_status,
               c.resolution_date, c.created_at
        FROM complaint c
        JOIN user u ON c.user_id = u.user_id
    """)
    complaints = cursor.fetchall()
    conn.close()

    return render_template("complaints.html", complaints=complaints)

@app.route("/resolve_complaint/<int:complaint_id>")
def resolve_complaint(complaint_id):

    if "role" not in session or session["role"] != "admin":
        return redirect("/login")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE complaint
        SET complaint_status='Resolved', resolution_date=CURDATE()
        WHERE complaint_id=%s
    """, (complaint_id,))

    conn.commit()
    
    # fetch email via complaint_id
    cursor.execute("""
        SELECT u.email FROM user u
        JOIN complaint c ON u.user_id = c.user_id
        WHERE c.complaint_id = %s
    """, (complaint_id,))
    result = cursor.fetchone()
    user_email = result["email"]

    send_email(
        user_email,
        "Complaint Resolved",
        """
    Hello,

    Your complaint has been resolved.

    Thank you for your patience.

    Gadag Water Supply
    """
    )
    
    save_notification(complaint_id, "Your complaint has been resolved.", "Complaint")

    conn.close()

    return redirect(url_for("complaints"))

@app.route("/tanker_requests")
def tanker_requests():
    if "role" not in session or session["role"] != "admin":
        return redirect("/login")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT tr.tanker_request_id, w.ward_name, tr.request_date, tr.supply_date,
               tr.required_quantity, tr.status, tr.Request_month
        FROM tanker_request tr
        JOIN ward w ON tr.ward_id = w.ward_id
        ORDER BY tr.request_date DESC
    """)
    requests = cursor.fetchall()
    conn.close()

    return render_template("tanker_request.html", requests=requests)

@app.route("/approve_tanker/<int:tanker_request_id>")
def approve_tanker(tanker_request_id):
    if "role" not in session or session["role"] != "admin":
        return redirect("/login")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT ward_id, Request_month 
        FROM tanker_request 
        WHERE tanker_request_id=%s
    """, (tanker_request_id,))

    tr = cursor.fetchone()

    cursor.execute("""
        SELECT * FROM tanker_request
        WHERE ward_id=%s AND Request_month=%s AND status='Approved'
    """, (tr["ward_id"], tr["Request_month"]))

    existing = cursor.fetchone()

    if existing:
        conn.close()
        flash("A tanker is already approved for this ward in this month!","warning")
        return redirect(url_for("tanker_requests"))

    cursor.execute("""
        UPDATE tanker_request 
        SET status='Approved', supply_date=CURDATE()
        WHERE tanker_request_id=%s
    """, (tanker_request_id,))

    conn.commit()
    conn.close()

    flash("Tanker request approved successfully","success")
    return redirect(url_for("tanker_requests"))

@app.route("/reject_tanker/<int:tanker_request_id>")
def reject_tanker(tanker_request_id):
    if "role" not in session or session["role"] != "admin":
        return redirect("/login")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE tanker_request 
        SET status='Rejected'
        WHERE tanker_request_id=%s
    """, (tanker_request_id,))

    conn.commit()
    conn.close()

    flash("Tanker request rejected","danger")
    return redirect(url_for("tanker_requests"))
# ── ADMIN: VIEW ALL BILLS ──
@app.route("/admin/bills")
def admin_bills():
    if "role" not in session or session["role"] != "admin":
        return redirect("/login")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT b.*, u.name, u.phone,
               wc.connection_type, wc.meter_number
        FROM bill b
        LEFT JOIN user u ON b.user_id = u.user_id
        LEFT JOIN water_connection wc ON b.connection_id = wc.connection_id
        ORDER BY b.created_at DESC
    """)
    bills = cursor.fetchall()
    # Stats
    total = len(bills)
    unpaid = sum(1 for b in bills if b["bill_status"] == "Unpaid")
    paid = sum(1 for b in bills if b["bill_status"] == "Paid")
    total_amount = sum(b["amount_due"] for b in bills if b["bill_status"] == "Paid")
    conn.close()
    return render_template("admin_bills.html", bills=bills,
                           total=total, unpaid=unpaid, paid=paid,
                           total_amount=total_amount)


# ── ADMIN: GENERATE BILL ──
@app.route("/admin/generate_bill", methods=["GET", "POST"])
def generate_bill():
    if "role" not in session or session["role"] != "admin":
        return redirect("/login")
    conn = get_connection()
    cursor = conn.cursor()
    if request.method == "POST":
        user_id       = request.form["user_id"]
        connection_id = request.form["connection_id"]
        billing_month = request.form["billing_month"]
        total_units   = float(request.form["total_units"])
        from datetime import datetime, timedelta
        due_date      = (datetime.now()+timedelta(days=15)).strftime("%Y-%m-%d")
        connection_type = request.form.get("connection_type", "Domestic")
        # Fetch slab rate from database
        cursor.execute("""
            SELECT rate_per_unit FROM slab_rate
            WHERE connection_type = %s
            AND %s >= min_units AND %s <= max_units
            LIMIT 1
        """, (connection_type, total_units, total_units))
        slab = cursor.fetchone()
        rate = float(slab["rate_per_unit"]) if slab else 10.0
        amount_due = round(total_units * rate, 2)
        # Check duplicate bill for same month
        billing_month_date = billing_month + "-01"
        cursor.execute("""
        SELECT * FROM bill
        WHERE user_id=%s AND billing_month=%s
        """, (user_id, billing_month_date))
        existing = cursor.fetchone()
        if existing:
            conn.close()
            flash("Bill already generated for this user for this month!", "warning")
            return redirect("/admin/generate_bill")
        # Convert 2026-03 to 2026-03-01
        billing_month_date = billing_month + "-01"

        cursor.execute("""
        INSERT INTO bill (connection_id, user_id, billing_month, total_units,
                      amount_due, due_date, bill_status, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, 'Unpaid', NOW())
        """, (connection_id, user_id, billing_month_date, total_units, amount_due, due_date))
        conn.commit()

        # ✅ fetch user email and send notification
        cursor.execute("SELECT email FROM user WHERE user_id=%s", (user_id,))
        result = cursor.fetchone()
        user_email = result["email"]

        from datetime import datetime
        month_display = datetime.strptime(billing_month, "%Y-%m").strftime("%B %Y")

        send_email(
            user_email,
            "Monthly Water Bill Generated",
            f"""
        Hello,

        Your water bill for {month_display} has been generated.

        Total Units: {total_units}
        Amount Due: ₹{amount_due}
        Due Date: {due_date}

        Please pay before the due date to avoid penalties.

        Gadag Water Supply
        """
        )

        save_notification(user_id, f"Your water bill of ₹{amount_due} has been generated.", "Bill")

        conn.close()
        flash(f"Bill generated successfully! Amount: ₹{amount_due} (₹{rate}/unit × {total_units} units)", "success")
        return redirect("/admin/bills")
    # Get users with approved connections only
    cursor.execute("""
        SELECT u.user_id, u.name, u.phone,
               wc.connection_id, wc.connection_type, wc.meter_number
        FROM user u
        JOIN water_connection wc ON u.user_id = wc.user_id
        WHERE wc.connection_status = 'Approved'
        ORDER BY u.name
    """)
    users = cursor.fetchall()
    # Get slab rates from DB
    cursor.execute("SELECT * FROM slab_rate ORDER BY connection_type, min_units")
    slab_rates = cursor.fetchall()
    conn.close()
    return render_template("generate_bill.html", users=users, slab_rates=slab_rates)

# ── ADMIN: VIEW PAYMENTS ──
@app.route("/admin/payments")
def admin_payments():
    if "role" not in session or session["role"] != "admin":
        return redirect("/login")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.*, u.name, u.phone,
               b.billing_month, b.amount_due
        FROM payment p
        LEFT JOIN user u ON p.user_id = u.user_id
        LEFT JOIN bill b ON p.bill_id = b.bill_id
        ORDER BY p.created_at DESC
    """)
    payments = cursor.fetchall()
    total_collected = sum(p["amount_paid"] for p in payments if p["payment_status"] in ["Paid" , "Partial"])
    conn.close()
    return render_template("admin_payments.html", payments=payments,
                           total_collected=total_collected)

@app.route("/admin/notifications")
def admin_notifications():
    if "role" not in session or session["role"] != "admin":
        return redirect("/login")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT n.*, u.name, u.email
        FROM notification n
        JOIN user u ON n.user_id = u.user_id
        ORDER BY n.created_at DESC
    """)
    notifications = cursor.fetchall()
    conn.close()

    return render_template("admin_notifications.html", notifications=notifications)
# ---------------- REPORTS ----------------
@app.route("/reports")
def reports():
    if "role" not in session or session["role"] != "admin":
        return redirect("/login")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) AS total FROM complaint")
    total_complaints = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS total FROM complaint WHERE complaint_status='Pending'")
    pending_complaints = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS total FROM water_connection")
    total_connections = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS total FROM tanker_request")
    total_tanker = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS total FROM tanker_request WHERE status='Pending'")
    pending_tanker = cursor.fetchone()["total"]

    conn.close()

    return render_template(
        "reports.html",
        total_complaints=total_complaints,
        pending_complaints=pending_complaints,
        total_connections=total_connections,
        total_tanker=total_tanker,
        pending_tanker=pending_tanker
    )
# ---------------- FORGOT PASSWORD ----------------
@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    step = session.get("fp_step", 1)  # 1=email, 2=otp, 3=reset

    if request.method == "POST":
        action = request.form.get("action")

        # STEP 1 — Send OTP
        if action == "send_otp":
            email = request.form["email"].strip()
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM user WHERE email=%s", (email,))
                user = cursor.fetchone()
                conn.close()

                if not user:
                    flash("No account found with this email.", "danger")
                    return redirect("/forgot_password")

                otp = str(random.randint(100000, 999999))
                session["reset_email"] = email
                session["reset_otp"] = otp
                session["otp_expires"] = (datetime.now() + timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
                session["fp_step"] = 2

                send_email(
                    to_email=email,
                    subject="Password Reset OTP - Gadag Water Supply",
                    body=f"""
                    <h3>Password Reset OTP</h3>
                    <p>Your OTP is: <strong style="font-size:1.5rem;color:#7c3aed;letter-spacing:6px;">{otp}</strong></p>
                    <p>Valid for <strong>5 minutes</strong>. Do not share with anyone.</p>
                    """
                )

                flash("OTP sent to your email!", "success")
                return redirect("/forgot_password")

            except Exception as e:
                flash(f"Error: {str(e)}", "danger")
                return redirect("/forgot_password")

        # STEP 2 — Verify OTP
        elif action == "verify_otp":
            entered_otp = request.form["otp"].strip()
            try:
                expires = datetime.strptime(session.get("otp_expires",""), "%Y-%m-%d %H:%M:%S")
                if datetime.now() > expires:
                    session.pop("fp_step", None)
                    session.pop("reset_otp", None)
                    flash("OTP expired. Please request again.", "danger")
                    return redirect("/forgot_password")

                if entered_otp != session.get("reset_otp"):
                    flash("Incorrect OTP. Try again.", "danger")
                    return redirect("/forgot_password")

                session["fp_step"] = 3
                session.pop("reset_otp", None)
                flash("OTP verified! Now set your new password.", "success")
                return redirect("/forgot_password")

            except Exception as e:
                flash(f"Error: {str(e)}", "danger")
                return redirect("/forgot_password")

        # STEP 3 — Reset Password
        elif action == "reset_password":
            new_password = request.form["new_password"]
            confirm_password = request.form["confirm_password"]
            email = session.get("reset_email")
            try:
                pattern = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*[@$!%*?&]).{8,}$'
                if not re.match(pattern, new_password):
                    flash("Password must include uppercase, lowercase and special character.", "danger")
                    return redirect("/forgot_password")

                if new_password != confirm_password:
                    flash("Passwords do not match.", "danger")
                    return redirect("/forgot_password")

                hashed_password = generate_password_hash(new_password)
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("UPDATE user SET password=%s WHERE email=%s", (hashed_password, email))
                conn.commit()
                conn.close()

                # Clear all session data
                session.pop("fp_step", None)
                session.pop("reset_email", None)
                session.pop("otp_expires", None)

                flash("Password reset successfully! Please login.", "success")
                return redirect("/login")

            except Exception as e:
                flash(f"Error: {str(e)}", "danger")
                return redirect("/forgot_password")

    return render_template("forgot_password.html", step=session.get("fp_step", 1))

# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():

    if "user_id" in session:

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE user SET last_logout = NOW() WHERE user_id=%s",
            (session["user_id"],)
        )

        cursor.execute("""
        UPDATE user_log 
        SET logout_time = NOW()
        WHERE user_id=%s
        ORDER BY log_id DESC
        LIMIT 1
        """,(session["user_id"],))

        conn.commit()
        conn.close()

    session.clear()
    #flash("Logged out successfully")
    return redirect("/")


def send_payment_reminders():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT b.*, u.name, u.email
        FROM bill b
        JOIN user u ON b.user_id = u.user_id
        WHERE b.bill_status = 'Unpaid'
        AND b.due_date = DATE_ADD(CURDATE(), INTERVAL 3 DAY)
    """)
    unpaid_bills = cursor.fetchall()
    conn.close()

    for bill in unpaid_bills:
        month_display = bill["billing_month"].strftime("%B %Y")
        send_email(
            bill["email"],
            "Payment Reminder — Water Bill Due in 3 Days",
            f"""
        Hello {bill['name']},

        Your water bill is due in 3 days!

        Billing Month : {month_display}
        Amount Due    : ₹{bill['amount_due']}
        Due Date      : {bill['due_date']}

        Please pay before due date to avoid penalties.

        Gadag Water Supply
        """
        )

scheduler = BackgroundScheduler()
scheduler.add_job(send_payment_reminders, 'cron', hour=9, minute=0)
scheduler.start()

if __name__ == "__main__":
    app.run(debug=True,host='0.0.0.0',port=5000)