from flask import Flask, render_template, request, redirect, url_for, session
from login import login_bp
import sqlite3
import datetime

DB_PATH = 'database.db'


# Task breakdown patterns for automatically decomposing tasks
TASK_BREAKDOWN_PATTERNS = {
    "write": [
        "Plan content/outline",
        "Write first draft",
        "Review and edit",
        "Finalize and proofread"
    ],
    "study": [
        "Gather materials",
        "Read/review content",
        "Take notes",
        "Practice problems",
        "Test yourself"
    ],
    "clean": [
        "Remove clutter",
        "Dust and organize",
        "Vacuum/sweep",
        "Final touches"
    ],
    "organize": [
        "Sort items",
        "Group by category",
        "Arrange neatly",
        "Review and adjust"
    ],
    "learn": [
        "Research topic",
        "Watch tutorials/read guides",
        "Take notes",
        "Practice",
        "Review progress"
    ],
    "exercise": [
        "Warm up",
        "Main workout",
        "Cool down/stretch"
    ],
    "cook": [
        "Gather ingredients",
        "Prep ingredients",
        "Cook",
        "Plate and serve"
    ],
    "project": [
        "Plan and research",
        "Gather resources",
        "Start working",
        "Progress check",
        "Finalize"
    ],
    "meeting": [
        "Prepare materials",
        "Set up space",
        "Conduct meeting",
        "Follow up"
    ],
    "homework": [
        "Read instructions",
        "Gather materials",
        "Complete work",
        "Review answers",
        "Submit"
    ],
    "shopping": [
        "Make list",
        "Check inventory",
        "Go shopping",
        "Unpack and store"
    ]
}


def auto_breakdown_task(task_name):
    """
    Automatically break down a task into subtasks based on keywords.
    Returns a list of subtask names.
    """
    task_lower = task_name.lower()
    
    # Check for matching keywords
    for keyword, steps in TASK_BREAKDOWN_PATTERNS.items():
        if keyword in task_lower:
            return steps
    
    # Generic breakdown for tasks that don't match patterns
    return [
        "Plan approach",
        "Gather resources",
        "Start working",
        "Make progress",
        "Complete and review"
    ]


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


def ensure_custom_rewards_table():
    
    conn = get_db_conn()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS custom_rewards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            title TEXT NOT NULL,
            cost INTEGER NOT NULL
        )
    ''')
    conn.commit()
    conn.close()


def ensure_subtasks_table():
    
    conn = get_db_conn()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS subtasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_task_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            completed INTEGER DEFAULT 0,
            completed_at TEXT,
            FOREIGN KEY (parent_task_id) REFERENCES tasks(id)
        )
    ''')
    conn.commit()
    conn.close()


def ensure_redemptions_table():
    
    conn = get_db_conn()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS redemptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            reward_type TEXT NOT NULL,
            reward_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            cost INTEGER NOT NULL,
            redeemed_at TEXT NOT NULL,
            FOREIGN KEY (username) REFERENCES users(username)
        )
    ''')
    conn.commit()
    conn.close()


def ensure_streaks_table():
    """Create the `streaks` table for tracking daily task completion streaks.

    Stores the current streak count, last completion date, and highest streak
    achieved for each user. Used on the Progress and Activities pages.
    """
    
    conn = get_db_conn()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS streaks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            current_streak INTEGER DEFAULT 0,
            last_completion_date TEXT,
            longest_streak INTEGER DEFAULT 0,
            FOREIGN KEY (username) REFERENCES users(username)
        )
    ''')
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
        
        # Get subtasks for this task
        conn_subtasks = get_db_conn()
        c_subtasks = conn_subtasks.cursor()
        c_subtasks.execute("SELECT id, name, completed FROM subtasks WHERE parent_task_id = ?", (r['id'],))
        subtasks = [{'id': st['id'], 'name': st['name'], 'completed': st['completed']} for st in c_subtasks.fetchall()]
        conn_subtasks.close()
        
        grouped[imp].append({
            "id": r['id'],
            "name": r['name'],
            "date": r['date'],
            "subtasks": subtasks
        })
    
    # Sort tasks within each importance category by due date (earliest first)
    for imp in grouped:
        grouped[imp].sort(key=lambda x: x['date'] if x['date'] else '9999-12-31')
    
    return grouped


def get_calendar_tasks():
    """Get tasks organized by date for calendar view"""
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT id, name, date, importance FROM tasks WHERE completed = 0 OR completed IS NULL ORDER BY date")
    rows = c.fetchall()
    conn.close()
    
    # Organize tasks by date
    tasks_by_date = {}
    for r in rows:
        date = r['date']
        if date not in tasks_by_date:
            tasks_by_date[date] = []
        tasks_by_date[date].append({
            'id': r['id'],
            'name': r['name'],
            'importance': r['importance']
        })
    
    return tasks_by_date


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


def insert_subtask_db(parent_task_id, name):
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("INSERT INTO subtasks (parent_task_id, name) VALUES (?, ?)", (parent_task_id, name))
    conn.commit()
    task_id = c.lastrowid
    conn.close()
    return task_id


def delete_subtask_db(subtask_id):
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("DELETE FROM subtasks WHERE id = ?", (subtask_id,))
    conn.commit()
    conn.close()


def complete_subtask_db(subtask_id):
    conn = get_db_conn()
    c = conn.cursor()
    completed_at = datetime.datetime.now().isoformat()
    c.execute("UPDATE subtasks SET completed = 1, completed_at = ? WHERE id = ?", (completed_at, subtask_id))
    conn.commit()
    conn.close()


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


def edit_task_db(task_id, name, date, importance):
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("UPDATE tasks SET name = ?, date = ?, importance = ? WHERE id = ?", 
              (name, date, importance, task_id))
    conn.commit()
    conn.close()


def clear_subtasks_db(task_id):
    """Delete all subtasks for a given task"""
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("DELETE FROM subtasks WHERE parent_task_id = ?", (task_id,))
    conn.commit()
    conn.close()


def update_user_streak(username):
    """Update the user's daily streak when they complete a task.
    
    If the user completed a task today → streak continues.
    If last completion was yesterday → streak increases by 1.
    If last completion was before yesterday → streak resets to 1.
    """
    conn = get_db_conn()
    c = conn.cursor()
    
    today = datetime.datetime.now().date().isoformat()
    
    # Get or create streak record
    c.execute("SELECT current_streak, last_completion_date, longest_streak FROM streaks WHERE username = ?", (username,))
    row = c.fetchone()
    
    if not row:
        # New user - initialize streak
        c.execute("INSERT INTO streaks (username, current_streak, last_completion_date, longest_streak) VALUES (?, 1, ?, 1)",
                  (username, today))
        conn.commit()
        conn.close()
        return 1
    
    current_streak = row['current_streak'] or 0
    last_date = row['last_completion_date']
    longest_streak = row['longest_streak'] or 0
    
    # Calculate yesterday's date
    yesterday = (datetime.datetime.now().date() - datetime.timedelta(days=1)).isoformat()
    
    # Determine new streak
    if last_date == today:
        # Already completed today - don't change streak
        new_streak = current_streak
    elif last_date == yesterday:
        # Completed yesterday - continue the streak
        new_streak = current_streak + 1
    else:
        # Missed a day - reset to 1
        new_streak = 1
    
    # Update longest streak if new streak is better
    new_longest = max(longest_streak, new_streak)
    
    # Update streak record
    c.execute("UPDATE streaks SET current_streak = ?, last_completion_date = ?, longest_streak = ? WHERE username = ?",
              (new_streak, today, new_longest, username))
    conn.commit()
    conn.close()
    
    return new_streak


def get_user_streak(username):
    """Return the user's current and longest streak.
    
    Returns dict with 'current' and 'longest' keys.
    If no streak exists, returns {'current': 0, 'longest': 0}.
    """
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT current_streak, longest_streak FROM streaks WHERE username = ?", (username,))
    row = c.fetchone()
    conn.close()
    
    if not row:
        return {'current': 0, 'longest': 0}
    
    return {
        'current': row['current_streak'] or 0,
        'longest': row['longest_streak'] or 0
    }


def complete_task_and_award(task_id, username):
    """Mark a task completed and award points to the user.

    This is the function responsible for assigning points based on task
    importance and updating the user's `points` field. It also marks the
    task as completed (and saves `completed_at`) so progress can be computed.
    Called when a task is completed from the Activities UI.
    Also updates the user's daily streak.
    """
    
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
        
        # Update user's daily streak
        update_user_streak(username)

    conn.close()




app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.register_blueprint(login_bp)

ensure_users_table()
ensure_tasks_table()
ensure_custom_rewards_table()
ensure_subtasks_table()
ensure_redemptions_table()
ensure_streaks_table()




@app.route("/")
def home():
    username = session.get('user') if session else None
    upcoming_tasks = get_upcoming_tasks(username) if username else []
    return render_template("index.html", upcoming_tasks=upcoming_tasks, username=username)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/symptoms")
def symptoms():
    return render_template("symptoms.html")


@app.route("/activities")
def activities():
    """Render the main Activities page.

    Loads grouped tasks, calendar snippet data, user points and upcoming tasks
    to render the activities dashboard where users add/edit/complete tasks.
    """
    tasks = get_tasks_grouped()
    calendar_tasks = get_calendar_tasks()
    username = session.get('user') if session else None
    upcoming_tasks = get_upcoming_tasks(username) if username else []

    points = 0
    streak = {'current': 0, 'longest': 0}
    if username:
        conn = get_db_conn()
        c = conn.cursor()
        c.execute("SELECT points FROM users WHERE username = ?", (username,))
        row = c.fetchone()
        if row:
            points = row['points']
        conn.close()
        streak = get_user_streak(username)

    return render_template("activities.html", tasks=tasks, calendar_tasks=calendar_tasks, username=username, points=points, upcoming_tasks=upcoming_tasks, streak=streak, today=datetime.datetime.now(), timedelta=datetime.timedelta)


@app.route('/calendar')
def calendar():
    """Render the standalone calendar page (14-day view)."""
    calendar_tasks = get_calendar_tasks()
    username = session.get('user') if session else None
    upcoming_tasks = get_upcoming_tasks(username) if username else []

    points = 0
    if username:
        conn = get_db_conn()
        c = conn.cursor()
        c.execute("SELECT points FROM users WHERE username = ?", (username,))
        row = c.fetchone()
        if row:
            points = row['points']
        conn.close()

    return render_template('calendar.html', calendar_tasks=calendar_tasks, username=username, points=points, upcoming_tasks=upcoming_tasks, today=datetime.datetime.now(), timedelta=datetime.timedelta)


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
    """Render the progress page displaying completion percent and breakdown.

    Uses `compute_progress` to calculate a weighted progress percentage.
    Also passes streak data for display.
    """
    username = session.get('user') if session else None
    prog = compute_progress(username)
    # pass breakdown in a simple object that Jinja can access with dot notation
    breakdown = prog.get('breakdown', {})
    class AttrDict(dict):
        def __getattr__(self, name):
            return self.get(name, {})
    
    streak = {'current': 0, 'longest': 0}
    if username:
        streak = get_user_streak(username)

    return render_template("progress.html", percent=prog.get('percent', 0), breakdown=AttrDict({
        'completed': AttrDict(breakdown.get('completed', {})),
        'pending': AttrDict(breakdown.get('pending', {})),
    }), username=username, streak=streak)


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


@app.route("/add_subtask/<int:parent_task_id>", methods=["POST"])
def add_subtask(parent_task_id):
    subtask_name = request.form.get("subtask_name")
    if subtask_name:
        insert_subtask_db(parent_task_id, subtask_name)
    return redirect(url_for("activities"))


@app.route("/auto_breakdown_task/<int:parent_task_id>", methods=["POST"])
def auto_breakdown_task_route(parent_task_id):
    """Automatically break down a task into subtasks based on task name"""
    conn = get_db_conn()
    c = conn.cursor()
    
    # Get the parent task name
    c.execute("SELECT name FROM tasks WHERE id = ?", (parent_task_id,))
    task_row = c.fetchone()
    conn.close()
    
    if not task_row:
        return redirect(url_for("activities"))
    
    # Clear existing subtasks first
    clear_subtasks_db(parent_task_id)
    
    task_name = task_row['name']
    subtasks = auto_breakdown_task(task_name)
    
    # Insert all subtasks
    for subtask in subtasks:
        insert_subtask_db(parent_task_id, subtask)
    
    return redirect(url_for("activities"))


@app.route("/edit_task/<int:task_id>", methods=["POST"])
def edit_task(task_id):
    """Edit an existing task"""
    task_name = request.form.get("task_name")
    task_date = request.form.get("task_date")
    importance = request.form.get("importance")
    
    if task_name and task_date and importance in ("Major", "Medium", "Minor"):
        edit_task_db(task_id, task_name, task_date, importance)
    
    return redirect(url_for("activities"))


@app.route("/complete_subtask/<int:subtask_id>", methods=["POST"])
def complete_subtask(subtask_id):
    complete_subtask_db(subtask_id)
    return redirect(url_for("activities"))


@app.route("/delete_subtask/<int:subtask_id>", methods=["POST"])
def delete_subtask(subtask_id):
    delete_subtask_db(subtask_id)
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


def get_upcoming_tasks(username=None, days=7):
    """
    Get tasks due within the next X days.
    Returns list of tasks sorted by due date.
    """
    conn = get_db_conn()
    c = conn.cursor()
    
    today = datetime.datetime.now().date()
    future_date = today + datetime.timedelta(days=days)
    
    if username:
        c.execute("""
            SELECT id, name, date, importance 
            FROM tasks 
            WHERE user = ? 
            AND (completed = 0 OR completed IS NULL)
            AND date BETWEEN ? AND ?
            ORDER BY date ASC
        """, (username, today.isoformat(), future_date.isoformat()))
    else:
        c.execute("""
            SELECT id, name, date, importance, user 
            FROM tasks 
            WHERE (completed = 0 OR completed IS NULL)
            AND date BETWEEN ? AND ?
            ORDER BY date ASC
        """, (today.isoformat(), future_date.isoformat()))
    
    rows = c.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


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
    redeemed_at = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    c.execute("INSERT INTO redemptions (username, reward_type, reward_id, title, cost, redeemed_at) VALUES (?, ?, ?, ?, ?, ?)", (username, reward_type, reward_id, title, cost, redeemed_at))
    conn.commit()
    conn.close()

def get_redeemed_rewards(username):
    """Get all redeemed rewards for a user, ordered by most recent first."""
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT id, title, cost, redeemed_at FROM redemptions WHERE username = ? ORDER BY redeemed_at DESC LIMIT 10", (username,))
    rewards = [{'id': r['id'], 'title': r['title'], 'cost': r['cost'], 'redeemed_at': r['redeemed_at']} for r in c.fetchall()]
    conn.close()
    return rewards

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


@app.route('/redeem', methods=['GET'])
def redeem():
    username = session.get('user')
    if not username:
        return redirect(url_for('home'))  
    points = get_user_points(username)
    default_rewards = get_default_rewards_for_display(username)
    custom_rewards = get_custom_rewards_for_user(username)
    redeemed_rewards = get_redeemed_rewards(username)
    nearest_default = nearest_reward_info(default_rewards, username)
    nearest_custom = nearest_reward_info(custom_rewards, username)
   
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
                           redeemed_rewards=redeemed_rewards,
                           nearest=nearest)


@app.route('/redeem/default/<int:reward_id>', methods=['POST'])
def redeem_default(reward_id):
    username = session.get('user')
    if not username:
        return redirect(url_for('home'))
  
    matched = next((r for r in DEFAULT_REWARDS if r[0] == reward_id), None)
    if not matched:
        return "Unknown reward", 400
    _, title, cost = matched
    if not deduct_points(username, cost):
        return "Not enough points", 400
    log_redemption(username, 'default', reward_id, title, cost)
    
    return redirect(url_for('redeem'))


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