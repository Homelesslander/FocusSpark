from flask import Blueprint, render_template, request, redirect, url_for, session, flash
import sqlite3, bcrypt, os, smtplib, ssl, uuid, datetime

login_bp = Blueprint('auth', __name__)


def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            role TEXT DEFAULT 'child',
            parent_username TEXT
        )
    ''')

    
    c.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in c.fetchall()]
    if "points" not in columns:
        c.execute("ALTER TABLE users ADD COLUMN points INTEGER DEFAULT 0")
    if "role" not in columns:
        c.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'child'")
    if "parent_username" not in columns:
        c.execute("ALTER TABLE users ADD COLUMN parent_username TEXT")
    # optional email fields for notifications and verification
    if "email" not in columns:
        c.execute("ALTER TABLE users ADD COLUMN email TEXT")
    if "email_verified" not in columns:
        c.execute("ALTER TABLE users ADD COLUMN email_verified INTEGER DEFAULT 0")

    conn.commit()
    conn.close()

    # email verification tokens
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS email_verifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            token TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            used INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@login_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password'].encode('utf-8')
        role = request.form.get('role', 'child').lower()
        if role not in ("parent", "child"):
            role = 'child'
        hashed_pw = bcrypt.hashpw(password, bcrypt.gensalt())

        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", (username, hashed_pw, role))
            conn.commit()
            # Auto-login the user after successful registration
            session['user'] = username
            session['role'] = role
            return redirect(url_for('activities'))
        except sqlite3.IntegrityError:
            return "Username already exists!"
        finally:
            conn.close()

    return render_template('index.html')


@login_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password'].encode('utf-8')

        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=?", (username,))
        user = c.fetchone()
        conn.close()

        if user and bcrypt.checkpw(password, user[2]):
            session['user'] = username
            # store role in session (table columns: id, username, password, role, ...)
            try:
                role = user[3] if len(user) > 3 else 'child'
            except Exception:
                role = 'child'
            session['role'] = role
            # Redirect parents to parent dashboard
            if role and str(role).lower() == 'parent':
                return redirect(url_for('parent_dashboard'))
            return redirect(url_for('activities'))
        else:
            return "Invalid username or password!"
    return render_template('index.html')


@login_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))


# Change password route
@login_bp.route('/change_password', methods=['POST'])
def change_password():
    username = session.get('user')
    if not username:
        return redirect(url_for('auth.login'))

    current = request.form.get('current_password', '').encode('utf-8')
    new_pw = request.form.get('new_password', '').encode('utf-8')
    confirm = request.form.get('confirm_password', '').encode('utf-8')

    if new_pw != confirm:
        return "New passwords do not match", 400

    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT password FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    if not row:
        conn.close()
        return redirect(url_for('auth.login'))

    if not bcrypt.checkpw(current, row[0]):
        conn.close()
        return "Current password incorrect", 400

    hashed = bcrypt.hashpw(new_pw, bcrypt.gensalt())
    c.execute("UPDATE users SET password = ? WHERE username = ?", (hashed, username))
    conn.commit()
    conn.close()
    return redirect(url_for('activities'))


# Send verification email
def _send_smtp_email(to_addr, subject, body):
    cfg = {
        'host': os.environ.get('SMTP_HOST', ''),
        'port': int(os.environ.get('SMTP_PORT', '465')),
        'user': os.environ.get('SMTP_USER', ''),
        'pass': os.environ.get('SMTP_PASS', ''),
        'from_addr': os.environ.get('FROM_EMAIL', os.environ.get('SMTP_USER', 'no-reply@example.com'))
    }
    if not cfg['host'] or not cfg['user'] or not cfg['pass']:
        print('SMTP not configured; cannot send verification to', to_addr)
        return False
    message = f"From: {cfg['from_addr']}\r\nTo: {to_addr}\r\nSubject: {subject}\r\n\r\n{body}"
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(cfg['host'], cfg['port'], context=context) as server:
            server.login(cfg['user'], cfg['pass'])
            server.sendmail(cfg['from_addr'], [to_addr], message.encode('utf-8'))
        return True
    except Exception as e:
        print('Error sending verification email', e)
        return False


@login_bp.route('/send_verification', methods=['POST'])
def send_verification():
    username = session.get('user')
    if not username:
        return redirect(url_for('auth.login'))

    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT email FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    if not row or not row[0]:
        conn.close()
        return "No email set for account", 400
    email = row[0]
    token = uuid.uuid4().hex
    expires = (datetime.datetime.utcnow() + datetime.timedelta(hours=24)).isoformat()
    c.execute("INSERT INTO email_verifications (username, token, expires_at) VALUES (?, ?, ?)", (username, token, expires))
    conn.commit()
    conn.close()

    verify_link = f"http://localhost:5050/verify_email?token={token}"
    subject = 'Verify your email for ADHD App'
    body = f"Hi {username},\n\nPlease verify your email by clicking the link below:\n{verify_link}\n\nThis link expires in 24 hours.\n"
    ok = _send_smtp_email(email, subject, body)
    if not ok:
        return "Failed to send verification email (SMTP not configured)", 500
    return redirect(url_for('settings'))


@login_bp.route('/verify_email')
def verify_email():
    token = request.args.get('token')
    if not token:
        return "Missing token", 400
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT id, username, expires_at, used FROM email_verifications WHERE token = ?", (token,))
    row = c.fetchone()
    if not row:
        conn.close()
        return "Invalid token", 400
    vid, username, expires_at, used = row
    if used:
        conn.close()
        return "Token already used", 400
    if datetime.datetime.fromisoformat(expires_at) < datetime.datetime.utcnow():
        conn.close()
        return "Token expired", 400
    # mark used and set user's email_verified
    c.execute("UPDATE email_verifications SET used = 1 WHERE id = ?", (vid,))
    c.execute("UPDATE users SET email_verified = 1 WHERE username = ?", (username,))
    conn.commit()
    conn.close()
    return redirect(url_for('settings'))
