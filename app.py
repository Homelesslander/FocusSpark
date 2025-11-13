from flask import Flask, render_template, request, redirect, url_for, session
from login import login_bp
import sqlite3
import datetime

DB_PATH = 'database.db'



def get_db_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_users_table():
    
    conn = get_db_conn()
    c = conn.cursor()
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')

    c.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in c.fetchall()]
    if "points" not in columns:
        c.execute("ALTER TABLE users ADD COLUMN points INTEGER DEFAULT 0")

    conn.commit()
    conn.close()


def ensure_tasks_table():
    
    conn = get_db_conn()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            date TEXT,
            importance TEXT NOT NULL,
            user TEXT
        )
    ''')
    # Ensure 'completed' and 'completed_at' columns exist for tracking progress without deleting rows
    c.execute("PRAGMA table_info(tasks)")
    existing_cols = [row[1] for row in c.fetchall()]
    if "completed" not in existing_cols:
        c.execute("ALTER TABLE tasks ADD COLUMN completed INTEGER DEFAULT 0")
    if "completed_at" not in existing_cols:
        c.execute("ALTER TABLE tasks ADD COLUMN completed_at TEXT")
    conn.commit()
    conn.close()



def get_tasks_grouped():
    
    conn = get_db_conn()
    c = conn.cursor()
    # Only select tasks that are not completed so completed tasks disappear from the Activities page
    c.execute("SELECT id, name, date, importance FROM tasks WHERE completed = 0 OR completed IS NULL ORDER BY id")
    rows = c.fetchall()
    conn.close()

    grouped = {"Major": [], "Medium": [], "Minor": []}
    for r in rows:
        imp = r['importance']
        if imp not in grouped:
            grouped.setdefault(imp, [])
        grouped[imp].append({
            "id": r['id'],
            "name": r['name'],
            "date": r['date']
        })
    return grouped


POINTS = {"Major": 100, "Medium": 50, "Minor": 20}

# Weights used to calculate progress percentage. Minor = 1.0, Medium = 1.5 (50% more),
# Major = Medium * 1.5 = 2.25 (50% more than medium).
WEIGHTS = {"Major": 2.25, "Medium": 1.5, "Minor": 1.0}


def compute_progress(username=None):
    """Compute progress percentage for a given user (or global if username is None).

    Returns a dict with percent (int) and breakdown counts and weights.
    """
    conn = get_db_conn()
    c = conn.cursor()

    params = []
    where = ""
    if username:
        where = "WHERE user = ?"
        params = [username]

    c.execute(f"SELECT importance, completed FROM tasks {where}", params)
    rows = c.fetchall()
    conn.close()

    completed_weight = 0.0
    pending_weight = 0.0
    breakdown = {
        "completed": {"Major": 0, "Medium": 0, "Minor": 0},
        "pending": {"Major": 0, "Medium": 0, "Minor": 0},
    }

    for r in rows:
        imp = r[0]
        completed = r[1]
        weight = WEIGHTS.get(imp, 1.0)
        if completed:
            completed_weight += weight
            breakdown["completed"].setdefault(imp, 0)
            breakdown["completed"][imp] += 1
        else:
            pending_weight += weight
            breakdown["pending"].setdefault(imp, 0)
            breakdown["pending"][imp] += 1

    total = completed_weight + pending_weight
    percent = int(round((completed_weight / total) * 100)) if total > 0 else 0

    return {
        "percent": percent,
        "completed_weight": completed_weight,
        "pending_weight": pending_weight,
        "breakdown": breakdown,
    }


def insert_task_db(name, date, importance, user=None):
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("INSERT INTO tasks (name, date, importance, user) VALUES (?, ?, ?, ?)",
              (name, date, importance, user))
    conn.commit()
    conn.close()


def delete_task_db(task_id):
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()


def complete_task_and_award(task_id, username):
    
    conn = get_db_conn()
    c = conn.cursor()

  
    c.execute("SELECT importance FROM tasks WHERE id = ?", (task_id,))
    row = c.fetchone()
    if row:
        importance = row['importance']
        points = POINTS.get(importance, 0)

        
        c.execute("PRAGMA table_info(users)")
        cols = [r[1] for r in c.fetchall()]
        if "points" not in cols:
            c.execute("ALTER TABLE users ADD COLUMN points INTEGER DEFAULT 0")

       
        # award points
        c.execute("UPDATE users SET points = points + ? WHERE username = ?", (points, username))

        # mark task as completed instead of deleting it so we can compute progress
        completed_at = datetime.datetime.now().isoformat()
        c.execute("UPDATE tasks SET completed = 1, completed_at = ? WHERE id = ?", (completed_at, task_id))
        conn.commit()

    conn.close()




app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.register_blueprint(login_bp)

ensure_users_table()
ensure_tasks_table()




@app.route("/")
def home():
    return render_template("index.html")


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/symptoms")
def symptoms():
    return render_template("symptoms.html")


@app.route("/activities")
def activities():
    tasks = get_tasks_grouped()
    username = session.get('user') if session else None

    points = 0
    if username:
        conn = get_db_conn()
        c = conn.cursor()
        c.execute("SELECT points FROM users WHERE username = ?", (username,))
        row = c.fetchone()
        if row:
            points = row['points']
        conn.close()

    return render_template("activities.html", tasks=tasks, username=username, points=points)


@app.route('/viewtasks')
def view_tasks():
    """Render a focused view of pending tasks grouped by importance."""
    tasks = get_tasks_grouped()
    username = session.get('user') if session else None

    points = 0
    if username:
        conn = get_db_conn()
        c = conn.cursor()
        c.execute("SELECT points FROM users WHERE username = ?", (username,))
        row = c.fetchone()
        if row:
            points = row['points']
        conn.close()

    return render_template('viewtasks.html', tasks=tasks, username=username, points=points)


def clear_completed_tasks(username=None):
    """Delete all completed tasks from the database for the given user (or all users if None)."""
    conn = get_db_conn()
    c = conn.cursor()
    if username:
        c.execute("DELETE FROM tasks WHERE completed = 1 AND user = ?", (username,))
    else:
        c.execute("DELETE FROM tasks WHERE completed = 1")
    conn.commit()
    conn.close()


@app.route("/progress")
def progress():
    username = session.get('user') if session else None
    prog = compute_progress(username)
    # pass breakdown in a simple object that Jinja can access with dot notation
    breakdown = prog.get('breakdown', {})
    class AttrDict(dict):
        def __getattr__(self, name):
            return self.get(name, {})

    return render_template("progress.html", percent=prog.get('percent', 0), breakdown=AttrDict({
        'completed': AttrDict(breakdown.get('completed', {})),
        'pending': AttrDict(breakdown.get('pending', {})),
    }), username=username)


@app.route("/clear_completed", methods=['POST'])
def handle_clear_completed():
    username = session.get('user') if session else None
    if username or request.form.get('all') == '1':
        clear_completed_tasks(username)
    return redirect(url_for('settings'))


@app.route('/settings')
def settings():
    username = session.get('user') if session else None
    return render_template('settings.html', username=username)


@app.route('/reset_points', methods=['POST'])
def reset_points():
    username = session.get('user') if session else None
    conn = get_db_conn()
    c = conn.cursor()
    # If a user is signed in, reset only their points. If not and the form includes 'all', reset everyone.
    if username:
        c.execute("UPDATE users SET points = 0 WHERE username = ?", (username,))
    else:
        if request.form.get('all') == '1':
            c.execute("UPDATE users SET points = 0")
    conn.commit()
    conn.close()
    return redirect(url_for('settings'))

@app.route("/add_task", methods=["POST"])
def add_task():
    task_name = request.form.get("task_name")
    task_date = request.form.get("task_date")
    importance = request.form.get("importance")

    if task_name and task_date and importance in ("Major", "Medium", "Minor"):
        insert_task_db(task_name, task_date, importance, session.get('user') if session else None)

    return redirect(url_for("activities"))


@app.route("/delete_task/<importance>/<int:task_index>", methods=["POST"])
def delete_task(importance, task_index):
    grouped = get_tasks_grouped()
    if importance in grouped and 0 <= task_index < len(grouped[importance]):
        task_id = grouped[importance][task_index].get('id')
        if task_id:
            delete_task_db(task_id)
    return redirect(url_for("activities"))


@app.route("/complete_task/<importance>/<int:task_index>", methods=["POST"])
def complete_task(importance, task_index):
    grouped = get_tasks_grouped()
    username = session.get('user')
    if importance in grouped and 0 <= task_index < len(grouped[importance]) and username:
        task_id = grouped[importance][task_index].get('id')
        if task_id:
            complete_task_and_award(task_id, username)
    return redirect(url_for("activities"))


DEFAULT_REWARDS = [
    
    (1, "5 minute phone break", 20),
    (2, "30 minute TV", 60),
    (3, "Snack of choice", 40),
    (4, "Buy something small", 150),
    (5, "Game time 1 hour", 100),
]

def get_user_points(username):
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT points FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    conn.close()
    return row['points'] if row and row['points'] is not None else 0

def add_points(username, amount):
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("UPDATE users SET points = COALESCE(points,0) + ? WHERE username = ?", (amount, username))
    conn.commit()
    conn.close()

def deduct_points(username, amount):
    conn = get_db_conn()
    c = conn.cursor()
    # ensure non-negative
    c.execute("SELECT points FROM users WHERE username = ?", (username,))
    r = c.fetchone()
    current = r['points'] if r and r['points'] is not None else 0
    if current < amount:
        conn.close()
        return False
    c.execute("UPDATE users SET points = points - ? WHERE username = ?", (amount, username))
    conn.commit()
    conn.close()
    return True

def get_default_rewards_for_display(username):
    points = get_user_points(username)
    rewards = []
    for rid, title, cost in DEFAULT_REWARDS:
        rewards.append({
            'id': rid,
            'title': title,
            'cost': cost,
            'claimable': points >= cost
        })
    return rewards

def get_custom_rewards_for_user(username):
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT id, title, cost FROM custom_rewards WHERE username = ? ORDER BY cost ASC", (username,))
    rows = c.fetchall()
    conn.close()
    return [{'id': r['id'], 'title': r['title'], 'cost': r['cost'], 'claimable': get_user_points(username) >= r['cost']} for r in rows]

def log_redemption(username, reward_type, reward_id, title, cost):
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("INSERT INTO redemptions (username, reward_type, reward_id, title, cost) VALUES (?, ?, ?, ?, ?)", (username, reward_type, reward_id, title, cost))
    conn.commit()
    conn.close()

def nearest_reward_info(rewards, username):
    """Given a list of reward dicts (with cost), return the nearest non-claimable reward and pts needed."""
    points = get_user_points(username)
    non_claimable = [r for r in rewards if not r.get('claimable')]
    if not non_claimable:
        return None
    # nearest by cost difference
    nearest = min(non_claimable, key=lambda r: r['cost'] - points)
    return {
        'reward': nearest,
        'points_needed': max(0, nearest['cost'] - points)
    }

# Route: display redeem page
@app.route('/redeem', methods=['GET'])
def redeem():
    username = session.get('user')
    if not username:
        return redirect(url_for('home'))  # or login
    points = get_user_points(username)
    default_rewards = get_default_rewards_for_display(username)
    custom_rewards = get_custom_rewards_for_user(username)
    nearest_default = nearest_reward_info(default_rewards, username)
    nearest_custom = nearest_reward_info(custom_rewards, username)
    # determine which "nearest" to show (closest in points needed)
    nearest = None
    if nearest_default and nearest_custom:
        if nearest_default['points_needed'] <= nearest_custom['points_needed']:
            nearest = ('default', nearest_default)
        else:
            nearest = ('custom', nearest_custom)
    elif nearest_default:
        nearest = ('default', nearest_default)
    elif nearest_custom:
        nearest = ('custom', nearest_custom)

    return render_template('redeem.html',
                           username=username,
                           points=points,
                           default_rewards=default_rewards,
                           custom_rewards=custom_rewards,
                           nearest=nearest)

# Route: redeem a default reward
@app.route('/redeem/default/<int:reward_id>', methods=['POST'])
def redeem_default(reward_id):
    username = session.get('user')
    if not username:
        return redirect(url_for('home'))
    # find reward in DEFAULT_REWARDS
    matched = next((r for r in DEFAULT_REWARDS if r[0] == reward_id), None)
    if not matched:
        return "Unknown reward", 400
    _, title, cost = matched
    if not deduct_points(username, cost):
        return "Not enough points", 400
    log_redemption(username, 'default', reward_id, title, cost)
    # optional: do something else (notify, etc.)
    return redirect(url_for('redeem'))

# Route: redeem a custom reward
@app.route('/redeem/custom/<int:reward_id>', methods=['POST'])
def redeem_custom(reward_id):
    username = session.get('user')
    if not username:
        return redirect(url_for('home'))
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT id, title, cost FROM custom_rewards WHERE id = ? AND username = ?", (reward_id, username))
    r = c.fetchone()
    conn.close()
    if not r:
        return "Reward not found", 404
    title = r['title']
    cost = r['cost']
    if not deduct_points(username, cost):
        return "Not enough points", 400
    log_redemption(username, 'custom', reward_id, title, cost)
    # Optionally delete the custom reward after redemption or keep it
    # c.execute("DELETE FROM custom_rewards WHERE id = ?", (reward_id,))
    # commit if you choose to delete
    return redirect(url_for('redeem'))

# Route: add a custom reward
@app.route('/redeem/add_custom', methods=['POST'])
def add_custom_reward():
    username = session.get('user')
    if not username:
        return redirect(url_for('home'))
    title = request.form.get('title', '').strip()
    cost = request.form.get('cost', '').strip()
    try:
        cost = int(cost)
    except:
        return "Invalid cost", 400
    if not title or cost <= 0:
        return "Invalid input", 400
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("INSERT INTO custom_rewards (username, title, cost) VALUES (?, ?, ?)", (username, title, cost))
    conn.commit()
    conn.close()
    return redirect(url_for('redeem'))



if __name__ == "__main__":
    app.run(debug=True, port=5050)