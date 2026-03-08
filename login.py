from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from db_config import get_db_conn_wrapped
import bcrypt, os, smtplib, ssl, uuid, datetime

login_bp = Blueprint('auth', __name__)


def init_db():
    conn = get_db_conn_wrapped()
    c = conn.cursor()

    
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(255) UNIQUE,
            password TEXT,
            role VARCHAR(50) DEFAULT 'child',
            parent_username VARCHAR(255)
        )
    ''')

    
    # add optional columns, ignore if already present
    try:
        c.execute("ALTER TABLE users ADD COLUMN points INT DEFAULT 0")
    except Exception as e:
        # 1060 = duplicate column name, ignore
        if hasattr(e, 'errno') and e.errno != 1060:
            raise
    try:
        c.execute("ALTER TABLE users ADD COLUMN role VARCHAR(50) DEFAULT 'child'")
    except Exception as e:
        if hasattr(e, 'errno') and e.errno != 1060:
            raise
    try:
        c.execute("ALTER TABLE users ADD COLUMN parent_username VARCHAR(255)")
    except Exception as e:
        if hasattr(e, 'errno') and e.errno != 1060:
            raise
    try:
        c.execute("ALTER TABLE users ADD COLUMN email VARCHAR(255)")
    except Exception as e:
        if hasattr(e, 'errno') and e.errno != 1060:
            raise
    try:
        c.execute("ALTER TABLE users ADD COLUMN email_verified INT DEFAULT 0")
    except Exception as e:
        if hasattr(e, 'errno') and e.errno != 1060:
            raise

    conn.commit()
    conn.close()

    # email verification tokens
    conn = get_db_conn_wrapped()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS email_verifications (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(255) NOT NULL,
            token VARCHAR(255) NOT NULL,
            expires_at VARCHAR(255) NOT NULL,
            used INT DEFAULT 0
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
        hashed_pw_bytes = bcrypt.hashpw(password, bcrypt.gensalt())
        # store as utf-8 string so MySQL doesn't convert to blob
        hashed_pw = hashed_pw_bytes.decode('utf-8')

        conn = get_db_conn_wrapped()
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", (username, hashed_pw, role))
            conn.commit()
            # Auto-login the user after successful registration
            session['user'] = username
            session['role'] = role
            return redirect(url_for('activities'))
        except Exception as e:
            if 'duplicate' in str(e).lower() or 'unique' in str(e).lower():
                return "Username already exists!"
            return f"Registration error: {str(e)}"
        finally:
            conn.close()

    return render_template('index.html')


@login_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password'].encode('utf-8')

        conn = get_db_conn_wrapped()
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=?", (username,))
        user = c.fetchone()
        conn.close()

        hashed = None
        if user:
            stored = user['password']
            if isinstance(stored, str):
                hashed = stored.encode('utf-8')
            else:
                hashed = stored
        if user and hashed and bcrypt.checkpw(password, hashed):
            session['user'] = username
            # store role in session
            try:
                role = user.get('role', 'child') if user else 'child'
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

    conn = get_db_conn_wrapped()
    c = conn.cursor()
    c.execute("SELECT password FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    if not row:
        conn.close()
        return redirect(url_for('auth.login'))

    stored = row['password']
    if isinstance(stored, str):
        stored = stored.encode('utf-8')
    if not bcrypt.checkpw(current, stored):
        conn.close()
        return "Current password incorrect", 400

    hashed_pw_bytes = bcrypt.hashpw(new_pw, bcrypt.gensalt())
    new_hashed = hashed_pw_bytes.decode('utf-8')
    c.execute("UPDATE users SET password = ? WHERE username = ?", (new_hashed, username))
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

    conn = get_db_conn_wrapped()
    c = conn.cursor()
    c.execute("SELECT email FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    if not row or not row['email']:
        conn.close()
        return "No email set for account", 400
    email = row['email']
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
    conn = get_db_conn_wrapped()
    c = conn.cursor()
    c.execute("SELECT id, username, expires_at, used FROM email_verifications WHERE token = ?", (token,))
    row = c.fetchone()
    if not row:
        conn.close()
        return "Invalid token", 400
    vid = row['id']
    username = row['username']
    expires_at = row['expires_at']
    used = row['used']
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
