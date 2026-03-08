from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from login import login_bp
import sqlite3
import datetime
import os
import smtplib
import ssl
import threading
import time

DB_PATH = 'database.db'

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
    task_lower = task_name.lower()
    for keyword, steps in TASK_BREAKDOWN_PATTERNS.items():
        if keyword in task_lower:
            return steps
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
    if "total_earned" not in columns:
        c.execute("ALTER TABLE users ADD COLUMN total_earned INTEGER DEFAULT 0")
    # Add optional email and reminder preferences columns if missing
    if "email" not in columns:
        c.execute("ALTER TABLE users ADD COLUMN email TEXT")
    if "reminders_enabled" not in columns:
        c.execute("ALTER TABLE users ADD COLUMN reminders_enabled INTEGER DEFAULT 0")
    if "reminder_frequency" not in columns:
        c.execute("ALTER TABLE users ADD COLUMN reminder_frequency TEXT DEFAULT 'weekly'")

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
            time TEXT,
            importance TEXT NOT NULL,
            user TEXT
        )
    ''')
   
    c.execute("PRAGMA table_info(tasks)")
    existing_cols = [row[1] for row in c.fetchall()]
    if "completed" not in existing_cols:
        c.execute("ALTER TABLE tasks ADD COLUMN completed INTEGER DEFAULT 0")
    if "completed_at" not in existing_cols:
        c.execute("ALTER TABLE tasks ADD COLUMN completed_at TEXT")
    if "time" not in existing_cols:
        c.execute("ALTER TABLE tasks ADD COLUMN time TEXT")
    # Add box-related columns for Option B
    if "in_box" not in existing_cols:
        c.execute("ALTER TABLE tasks ADD COLUMN in_box INTEGER DEFAULT 0")
    if "box_count" not in existing_cols:
        c.execute("ALTER TABLE tasks ADD COLUMN box_count INTEGER DEFAULT 0")
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
            cost INTEGER NOT NULL,
            duration_minutes INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

    # ensure duration column exists for older DBs
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("PRAGMA table_info(custom_rewards)")
    cols = [r[1] for r in c.fetchall()]
    if 'duration_minutes' not in cols:
        c.execute("ALTER TABLE custom_rewards ADD COLUMN duration_minutes INTEGER DEFAULT 0")
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
            expires_at TEXT,
            FOREIGN KEY (username) REFERENCES users(username)
        )
    ''')
    conn.commit()
    conn.close()
    # ensure expires_at column exists for older DBs
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("PRAGMA table_info(redemptions)")
    cols = [r[1] for r in c.fetchall()]
    if 'expires_at' not in cols:
        c.execute("ALTER TABLE redemptions ADD COLUMN expires_at TEXT")
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


def ensure_box_moves_table():
    """Create the `box_moves` table to store move history for analytics."""
    conn = get_db_conn()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS box_moves (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            username TEXT,
            moved_at TEXT NOT NULL,
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        )
    ''')
    conn.commit()
    conn.close()


def move_task_to_box(task_id, username):
    """Mark a task as moved to the box and record the move for analytics."""
    conn = get_db_conn()
    c = conn.cursor()
    # verify task exists and not completed
    c.execute("SELECT id, completed, user FROM tasks WHERE id = ?", (task_id,))
    r = c.fetchone()
    if not r:
        conn.close()
        return False
    if r['completed']:
        conn.close()
        return False

    # update task to be in the box and increment counter
    c.execute("UPDATE tasks SET in_box = 1, box_count = COALESCE(box_count,0) + 1 WHERE id = ?", (task_id,))
    moved_at = datetime.datetime.now().isoformat()
    c.execute("INSERT INTO box_moves (task_id, username, moved_at) VALUES (?, ?, ?)", (task_id, username, moved_at))
    conn.commit()
    conn.close()
    return True


def restore_task_from_box(task_id, username):
    """Restore a task from the box back to active tasks."""
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT id, completed FROM tasks WHERE id = ?", (task_id,))
    r = c.fetchone()
    if not r:
        conn.close()
        return False
    if r['completed']:
        conn.close()
        return False
    c.execute("UPDATE tasks SET in_box = 0 WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()
    return True


def get_box_items(username):
    """Return tasks currently in the box for the given username."""
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT id, name, date, time, importance, box_count, user FROM tasks WHERE in_box = 1 AND user = ? ORDER BY id DESC", (username,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_box_stats(username=None, limit=10):
    """Return aggregated box move counts for tasks (most-boxed). If username provided, filter to that user's tasks."""
    conn = get_db_conn()
    c = conn.cursor()
    if username:
        c.execute("SELECT bm.task_id, t.name, COUNT(*) as moves FROM box_moves bm JOIN tasks t ON t.id = bm.task_id WHERE t.user = ? GROUP BY bm.task_id ORDER BY moves DESC LIMIT ?", (username, limit))
    else:
        c.execute("SELECT bm.task_id, t.name, COUNT(*) as moves FROM box_moves bm JOIN tasks t ON t.id = bm.task_id GROUP BY bm.task_id ORDER BY moves DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_tasks_grouped():
    
    conn = get_db_conn()
    c = conn.cursor()
    
    # Exclude tasks currently placed in the box
    c.execute("SELECT id, name, date, time, importance FROM tasks WHERE (completed = 0 OR completed IS NULL) AND (in_box = 0 OR in_box IS NULL) ORDER BY id")
    rows = c.fetchall()
    conn.close()

    grouped = {"Major": [], "Medium": [], "Minor": []}
    for r in rows:
        imp = r['importance']
        if imp not in grouped:
            grouped.setdefault(imp, [])
        
        conn_subtasks = get_db_conn()
        c_subtasks = conn_subtasks.cursor()
        c_subtasks.execute("SELECT id, name, completed FROM subtasks WHERE parent_task_id = ?", (r['id'],))
        subtasks = [{'id': st['id'], 'name': st['name'], 'completed': st['completed']} for st in c_subtasks.fetchall()]
        conn_subtasks.close()
        
        grouped[imp].append({
            "id": r['id'],
            "name": r['name'],
            "date": r['date'],
            "time": r['time'] if 'time' in r.keys() else None,
            "subtasks": subtasks
        })
    
    
    for imp in grouped:
        grouped[imp].sort(key=lambda x: x['date'] if x['date'] else '9999-12-31')
    
    return grouped


def get_calendar_tasks():
    """Get tasks organized by date for calendar view"""
    conn = get_db_conn()
    c = conn.cursor()
    # Exclude boxed tasks from calendar view
    c.execute("SELECT id, name, date, time, importance FROM tasks WHERE (completed = 0 OR completed IS NULL) AND (in_box = 0 OR in_box IS NULL) ORDER BY date")
    rows = c.fetchall()
    conn.close()
    
    
    tasks_by_date = {}
    for r in rows:
        date = r['date']
        if date not in tasks_by_date:
            tasks_by_date[date] = []
        tasks_by_date[date].append({
            'id': r['id'],
            'name': r['name'],
            'importance': r['importance'],
            'time': r['time'] if 'time' in r.keys() else None
        })
    
    return tasks_by_date


POINTS = {"Major": 100, "Medium": 50, "Minor": 20}


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

    # ignore tasks that are in the box when computing progress
    if where:
        where = where + " AND (in_box = 0 OR in_box IS NULL)"
    else:
        where = "WHERE (in_box = 0 OR in_box IS NULL)"
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


def insert_task_db_with_time(name, date, time_str, importance, user=None):
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("INSERT INTO tasks (name, date, time, importance, user) VALUES (?, ?, ?, ?, ?)",
              (name, date, time_str, importance, user))
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


def edit_task_db_with_time(task_id, name, date, time_str, importance):
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("UPDATE tasks SET name = ?, date = ?, time = ?, importance = ? WHERE id = ?", 
              (name, date, time_str, importance, task_id))
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
    
   
    c.execute("SELECT current_streak, last_completion_date, longest_streak FROM streaks WHERE username = ?", (username,))
    row = c.fetchone()
    
    if not row:
        
        c.execute("INSERT INTO streaks (username, current_streak, last_completion_date, longest_streak) VALUES (?, 1, ?, 1)",
                  (username, today))
        conn.commit()
        conn.close()
        return 1
    
    current_streak = row['current_streak'] or 0
    last_date = row['last_completion_date']
    longest_streak = row['longest_streak'] or 0
    
    
    yesterday = (datetime.datetime.now().date() - datetime.timedelta(days=1)).isoformat()
    
    
    if last_date == today:
        
        new_streak = current_streak
    elif last_date == yesterday:
       
        new_streak = current_streak + 1
    else:
       
        new_streak = 1
    
    new_longest = max(longest_streak, new_streak)
    
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

       
        c.execute("UPDATE users SET points = points + ? WHERE username = ?", (points, username))
        # also increment historical total earned for badges tracking
        c.execute("UPDATE users SET total_earned = COALESCE(total_earned,0) + ? WHERE username = ?", (points, username))

        completed_at = datetime.datetime.now().isoformat()
        c.execute("UPDATE tasks SET completed = 1, completed_at = ? WHERE id = ?", (completed_at, task_id))
        conn.commit()
        
        update_user_streak(username)

    conn.close()




app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.register_blueprint(login_bp)

# File upload configuration
UPLOAD_FOLDER = os.path.join('static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

ensure_users_table()
ensure_tasks_table()
ensure_custom_rewards_table()
ensure_subtasks_table()
ensure_redemptions_table()
ensure_box_moves_table()
ensure_streaks_table()
ensure_attitude_table_called = False


def ensure_attitude_table():
    conn = get_db_conn()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS attitude_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_username TEXT NOT NULL,
            child_username TEXT NOT NULL,
            rating TEXT NOT NULL,
            points_awarded INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()


def ensure_emotion_logs_table():
    conn = get_db_conn()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS emotion_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            child_username TEXT NOT NULL,
            emotion TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()


def ensure_visual_task_cards_table():
    conn = get_db_conn()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS visual_task_cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_username TEXT NOT NULL,
            title TEXT NOT NULL,
            image_path TEXT NOT NULL,
            points INTEGER NOT NULL,
            is_recommended INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()


def ensure_task_completions_table():
    conn = get_db_conn()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS task_completions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_id INTEGER NOT NULL,
            child_username TEXT NOT NULL,
            completed_at TEXT NOT NULL,
            FOREIGN KEY (card_id) REFERENCES visual_task_cards(id)
        )
    ''')
    conn.commit()
    conn.close()


# ensure tables exist
ensure_attitude_table()
ensure_emotion_logs_table()
ensure_visual_task_cards_table()
ensure_task_completions_table()





@app.route("/")
def home():
    username = session.get('user') if session else None
    return render_template("index.html", username=username)


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
    # determine whether the current user is a parent (used to show parent-specific UI)
    is_parent = False
    if username:
        conn = get_db_conn()
        c = conn.cursor()
        try:
            c.execute("SELECT role FROM users WHERE username = ?", (username,))
            row = c.fetchone()
            if row and ('role' in row.keys() and row['role'] == 'parent'):
                is_parent = True
        finally:
            conn.close()
    # this week (0-7 days)
    upcoming_tasks = get_upcoming_tasks(username, days=7) if username else []
    # next week: days 8-14
    upcoming_all_14 = get_upcoming_tasks(username, days=14) if username else []
    today = datetime.datetime.now().date()
    upcoming_tasks_next = [t for t in upcoming_all_14 if t.get('date') and datetime.datetime.fromisoformat(t['date']).date() > (today + datetime.timedelta(days=7))]

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

    return render_template("activities.html", tasks=tasks, calendar_tasks=calendar_tasks, username=username, points=points, upcoming_tasks=upcoming_tasks, upcoming_tasks_next=upcoming_tasks_next, streak=streak, today=datetime.datetime.now(), timedelta=datetime.timedelta, is_parent=is_parent)


@app.route('/calm_room')
def calm_room():
    """Render the calm room page with breathing exercises."""
    username = session.get('user') if session else None
    return render_template("calm_room.html", username=username)


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

    # determine parent role so template can show parent-only links
    is_parent = False
    if username:
        conn = get_db_conn()
        c = conn.cursor()
        try:
            c.execute("SELECT role FROM users WHERE username = ?", (username,))
            row = c.fetchone()
            if row and ('role' in row.keys() and row['role'] == 'parent'):
                is_parent = True
        finally:
            conn.close()

    return render_template('calendar.html', calendar_tasks=calendar_tasks, username=username, points=points, upcoming_tasks=upcoming_tasks, today=datetime.datetime.now(), timedelta=datetime.timedelta, is_parent=is_parent)


@app.route('/focus-timer')
def focus_timer():
    """Render the dedicated focus timer page (Pomodoro-style)."""
    username = session.get('user') if session else None
    
    conn = get_db_conn()
    c = conn.cursor()
    
    # Get ALL incomplete tasks (not just today's), ordered by importance
    if username:
        c.execute("""
            SELECT id, name, date, time, importance, completed 
            FROM tasks 
            WHERE (completed = 0 OR completed IS NULL) 
            AND (in_box = 0 OR in_box IS NULL)
            AND user = ?
            ORDER BY 
              CASE importance 
                WHEN 'Major' THEN 1 
                WHEN 'Medium' THEN 2 
                WHEN 'Minor' THEN 3 
                ELSE 4 
              END, 
              date, 
              time
        """, (username,))
    else:
        c.execute("""
            SELECT id, name, date, time, importance, completed 
            FROM tasks 
            WHERE (completed = 0 OR completed IS NULL) 
            AND (in_box = 0 OR in_box IS NULL)
            ORDER BY 
              CASE importance 
                WHEN 'Major' THEN 1 
                WHEN 'Medium' THEN 2 
                WHEN 'Minor' THEN 3 
                ELSE 4 
              END, 
              date, 
              time
        """)
    all_tasks_rows = c.fetchall()
    conn.close()
    
    # Convert Row objects to dictionaries
    all_tasks = [
        {
            'id': row['id'],
            'name': row['name'],
            'date': row['date'],
            'time': row['time'] if 'time' in row.keys() else None,
            'importance': row['importance'],
            'completed': row['completed'] if 'completed' in row.keys() else 0
        }
        for row in all_tasks_rows
    ]
    
    # Get the highest priority incomplete task (for "Now Working On")
    current_task = None
    incomplete_tasks = [t for t in all_tasks if not t['completed']]
    if incomplete_tasks:
        current_task = {
            'id': incomplete_tasks[0]['id'],
            'name': incomplete_tasks[0]['name'],
            'importance': incomplete_tasks[0]['importance']
        }
    
    points = 0
    if username:
        conn = get_db_conn()
        c = conn.cursor()
        c.execute("SELECT points FROM users WHERE username = ?", (username,))
        row = c.fetchone()
        if row:
            points = row['points']
        conn.close()
    
    # Determine parent role
    is_parent = False
    if username:
        conn = get_db_conn()
        c = conn.cursor()
        try:
            c.execute("SELECT role FROM users WHERE username = ?", (username,))
            row = c.fetchone()
            if row and ('role' in row.keys() and row['role'] == 'parent'):
                is_parent = True
        finally:
            conn.close()
    
    return render_template('focus_timer.html', 
                          username=username, 
                          current_task=current_task,
                          all_tasks=all_tasks,
                          points=points, 
                          is_parent=is_parent)


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

    # compute is_parent for conditional tabs
    is_parent = False
    if username:
        conn = get_db_conn()
        c = conn.cursor()
        try:
            c.execute("SELECT role FROM users WHERE username = ?", (username,))
            row = c.fetchone()
            if row and ('role' in row.keys() and row['role'] == 'parent'):
                is_parent = True
        finally:
            conn.close()

    return render_template('viewtasks.html', tasks=tasks, username=username, points=points, is_parent=is_parent)


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
    breakdown = prog.get('breakdown', {})
    class AttrDict(dict):
        def __getattr__(self, name):
            return self.get(name, {})
    
    streak = {'current': 0, 'longest': 0}
    if username:
        streak = get_user_streak(username)

    # show parent-only tabs when appropriate
    is_parent = False
    if username:
        conn = get_db_conn(); c = conn.cursor()
        try:
            c.execute("SELECT role FROM users WHERE username = ?", (username,))
            row = c.fetchone()
            if row and ('role' in row.keys() and row['role'] == 'parent'):
                is_parent = True
        finally:
            conn.close()

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
    email = None
    reminders_enabled = 0
    reminder_frequency = 'weekly'
    email_verified = 0
    if username:
        conn = get_db_conn()
        c = conn.cursor()
        c.execute("PRAGMA table_info(users)")
        cols = [r[1] for r in c.fetchall()]
        if 'email' in cols:
            c.execute("SELECT email, reminders_enabled, reminder_frequency, email_verified FROM users WHERE username = ?", (username,))
            row = c.fetchone()
            if row:
                email = row['email']
                reminders_enabled = row['reminders_enabled'] or 0
                reminder_frequency = row['reminder_frequency'] or 'weekly'
                email_verified = row['email_verified'] or 0
        conn.close()
    # pass parent flag to settings template so parent link can appear in tabs
    is_parent = False
    if username:
        conn = get_db_conn(); c = conn.cursor()
        try:
            c.execute("SELECT role FROM users WHERE username = ?", (username,))
            row = c.fetchone()
            if row and ('role' in row.keys() and row['role'] == 'parent'):
                is_parent = True
        finally:
            conn.close()

    return render_template('settings.html', username=username, email=email, reminders_enabled=reminders_enabled, reminder_frequency=reminder_frequency, email_verified=email_verified, is_parent=is_parent)


@app.route('/settings/update', methods=['POST'])
def update_settings():
    username = session.get('user') if session else None
    if not username:
        return redirect(url_for('settings'))

    email = request.form.get('email', '').strip() or None
    reminders_enabled = 1 if request.form.get('reminders_enabled') == 'on' else 0
    reminder_frequency = request.form.get('reminder_frequency', 'weekly')

    conn = get_db_conn()
    c = conn.cursor()
    # ensure columns exist (in case DB predates migration)
    c.execute("PRAGMA table_info(users)")
    cols = [r[1] for r in c.fetchall()]
    if 'email' not in cols:
        c.execute("ALTER TABLE users ADD COLUMN email TEXT")
    if 'reminders_enabled' not in cols:
        c.execute("ALTER TABLE users ADD COLUMN reminders_enabled INTEGER DEFAULT 0")
    if 'reminder_frequency' not in cols:
        c.execute("ALTER TABLE users ADD COLUMN reminder_frequency TEXT DEFAULT 'weekly'")

    c.execute("UPDATE users SET email = ?, reminders_enabled = ?, reminder_frequency = ? WHERE username = ?",
              (email, reminders_enabled, reminder_frequency, username))
    conn.commit()
    conn.close()

    return redirect(url_for('settings'))


# --- Email reminders implementation ---
def _get_smtp_config():
    return {
        'host': os.environ.get('SMTP_HOST', ''),
        'port': int(os.environ.get('SMTP_PORT', '465')),
        'user': os.environ.get('SMTP_USER', ''),
        'pass': os.environ.get('SMTP_PASS', ''),
        'from_addr': os.environ.get('FROM_EMAIL', os.environ.get('SMTP_USER', 'no-reply@example.com'))
    }


def send_email(to_addr, subject, body):
    cfg = _get_smtp_config()
    if not cfg['host'] or not cfg['user'] or not cfg['pass']:
        print('SMTP not configured; skipping email to', to_addr)
        return False

    message = f"From: {cfg['from_addr']}\r\nTo: {to_addr}\r\nSubject: {subject}\r\n\r\n{body}"
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(cfg['host'], cfg['port'], context=context) as server:
            server.login(cfg['user'], cfg['pass'])
            server.sendmail(cfg['from_addr'], [to_addr], message.encode('utf-8'))
        print('Sent reminder to', to_addr)
        return True
    except Exception as e:
        print('Error sending email to', to_addr, e)
        return False


def build_reminder_for_user(username, tasks):
    if not tasks:
        return None
    lines = [f"Hi {username},", "\nHere are your upcoming tasks:\n"]
    for t in tasks:
        date = t.get('date') or 'No date'
        lines.append(f"- {t.get('name')} (Due: {date}) Importance: {t.get('importance')}")
    lines.append("\nOpen your tasks: http://localhost:5050/activities")
    return '\n'.join(lines)


def send_reminders(dry_run=True):
    """Query users who enabled reminders and send emails based on their frequency.

    If `dry_run` is True, do not actually send emails; return a report list instead.
    Returns list of report dicts for each user considered.
    """
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT username, email, reminders_enabled, reminder_frequency FROM users WHERE reminders_enabled = 1 AND email IS NOT NULL AND email != ''")
    rows = c.fetchall()
    report = []
    for r in rows:
        username = r['username']
        email = r['email']
        freq = r['reminder_frequency'] or 'weekly'

        days = 7 if freq == 'weekly' else 1
        tasks = get_upcoming_tasks(username, days=days)
        if not tasks:
            report.append({'username': username, 'email': email, 'tasks': 0, 'sent': False, 'note': 'no upcoming tasks'})
            continue
        body = build_reminder_for_user(username, tasks)
        subject = f"Reminder: {len(tasks)} upcoming task(s)"
        if dry_run:
            report.append({'username': username, 'email': email, 'tasks': len(tasks), 'sent': False, 'note': 'dry-run'})
        else:
            ok = send_email(email, subject, body)
            report.append({'username': username, 'email': email, 'tasks': len(tasks), 'sent': bool(ok), 'note': None if ok else 'send-failed'})

    conn.close()
    return report


def _reminder_worker(interval_seconds=60*60):
    """Background thread that runs send_reminders periodically."""
    print('Reminder worker started; interval', interval_seconds)
    while True:
        try:
            # run actual sends (not dry-run) in background worker
            send_reminders(dry_run=False)
        except Exception as e:
            print('Error in reminder worker:', e)
        time.sleep(interval_seconds)


def start_reminder_scheduler():
    # Start the background thread to run reminders periodically.
    # Some Flask environments may not provide `before_first_request`,
    # so this function can be called manually from the __main__ block.
    interval = int(os.environ.get('REMINDER_INTERVAL_SECONDS', str(60*60)))
    t = threading.Thread(target=_reminder_worker, args=(interval,), daemon=True)
    t.start()


@app.route('/debug/send_reminders', methods=['GET', 'POST'])
def debug_send_reminders():
    # allow in debug mode or with a secret query param
    secret_ok = os.environ.get('REMINDER_DEBUG_SECRET') and request.args.get('secret') == os.environ.get('REMINDER_DEBUG_SECRET')
    if not app.debug and not secret_ok:
        return "Not allowed", 403

    dry = True
    if request.method == 'POST':
        # POST without dry param will perform actual send; use ?dry=0 for immediate send
        dry = request.args.get('dry', '1') != '0'
    else:
        dry = request.args.get('dry', '1') != '0'

    report = send_reminders(dry_run=dry)
    return jsonify({'dry_run': dry, 'report': report})


@app.route('/reset_points', methods=['POST'])
def reset_points():
    username = session.get('user') if session else None
    conn = get_db_conn()
    c = conn.cursor()
    if username:
        c.execute("UPDATE users SET points = 0 WHERE username = ?", (username,))
    else:
        if request.form.get('all') == '1':
            c.execute("UPDATE users SET points = 0")
    conn.commit()
    conn.close()
    return redirect(url_for('settings'))


@app.route('/reset_rewards', methods=['POST'])
def reset_rewards():
    """Remove active redeemed rewards for the current user (or all users if not signed in and `all=1`)."""
    username = session.get('user') if session else None
    conn = get_db_conn()
    c = conn.cursor()
    if username:
        c.execute("DELETE FROM redemptions WHERE username = ?", (username,))
    else:
        if request.form.get('all') == '1':
            c.execute("DELETE FROM redemptions")
    conn.commit()
    conn.close()
    return redirect(url_for('settings'))


@app.route('/reset_custom_rewards', methods=['POST'])
def reset_custom_rewards():
    """Delete custom rewards added by the current user (or all users if `all=1`)."""
    username = session.get('user') if session else None
    conn = get_db_conn()
    c = conn.cursor()
    if username:
        c.execute("DELETE FROM custom_rewards WHERE username = ?", (username,))
    else:
        if request.form.get('all') == '1':
            c.execute("DELETE FROM custom_rewards")
    conn.commit()
    conn.close()
    return redirect(url_for('settings'))

@app.route("/add_task", methods=["POST"])
def add_task():
    task_name = request.form.get("task_name")
    task_date = request.form.get("task_date")
    task_time = request.form.get("task_time")
    importance = request.form.get("importance")

    if task_name and task_date and importance in ("Major", "Medium", "Minor"):
        # allow optional time
        if task_time:
            insert_task_db_with_time(task_name, task_date, task_time, importance, session.get('user') if session else None)
        else:
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
            # Always award points to the task's owner if set; otherwise award to the current user.
            conn = get_db_conn()
            c = conn.cursor()
            c.execute("SELECT user FROM tasks WHERE id = ?", (task_id,))
            trow = c.fetchone()
            conn.close()

            target_username = username
            if trow and 'user' in trow.keys() and trow['user']:
                # prefer the task's assigned user
                target_username = trow['user']

            complete_task_and_award(task_id, target_username)
    return redirect(url_for("activities"))


@app.route("/complete_task_by_id/<int:task_id>", methods=["POST"])
def complete_task_by_id(task_id):
    """Complete a task by ID and return JSON (for AJAX requests)."""
    username = session.get('user')
    
    if not username:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        # Get task to verify it belongs to the user
        conn = get_db_conn()
        c = conn.cursor()
        c.execute("SELECT user FROM tasks WHERE id = ?", (task_id,))
        task_row = c.fetchone()
        conn.close()
        
        if not task_row:
            return jsonify({'success': False, 'error': 'Task not found'}), 404
        
        # Determine who to award points to
        target_username = username
        if task_row and 'user' in task_row.keys() and task_row['user']:
            target_username = task_row['user']
        
        # Complete the task
        complete_task_and_award(task_id, target_username)
        
        return jsonify({'success': True, 'message': 'Task completed'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/get_all_tasks', methods=["GET"])
def get_all_tasks_json():
    """Get all incomplete tasks for the current user as JSON."""
    username = session.get('user')
    
    if not username:
        return jsonify({'success': False, 'error': 'Not authenticated', 'tasks': []}), 401
    
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("""
        SELECT id, name, date, time, importance, completed 
        FROM tasks 
        WHERE (completed = 0 OR completed IS NULL) 
        AND (in_box = 0 OR in_box IS NULL)
        AND user = ?
        ORDER BY 
          CASE importance 
            WHEN 'Major' THEN 1 
            WHEN 'Medium' THEN 2 
            WHEN 'Minor' THEN 3 
            ELSE 4 
          END, 
          date, 
          time
    """, (username,))
    tasks_rows = c.fetchall()
    conn.close()
    
    # Convert to dictionaries
    tasks = [
        {
            'id': row['id'],
            'name': row['name'],
            'date': row['date'],
            'time': row['time'] if 'time' in row.keys() else None,
            'importance': row['importance'],
            'completed': row['completed'] if 'completed' in row.keys() else 0
        }
        for row in tasks_rows
    ]
    
    return jsonify({'success': True, 'tasks': tasks})


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
    
    c.execute("SELECT name FROM tasks WHERE id = ?", (parent_task_id,))
    task_row = c.fetchone()
    conn.close()
    
    if not task_row:
        return redirect(url_for("activities"))
    
    clear_subtasks_db(parent_task_id)
    
    task_name = task_row['name']
    subtasks = auto_breakdown_task(task_name)
    
    for subtask in subtasks:
        insert_subtask_db(parent_task_id, subtask)
    
    return redirect(url_for("activities"))


@app.route("/edit_task/<int:task_id>", methods=["POST"])
def edit_task(task_id):
    """Edit an existing task"""
    task_name = request.form.get("task_name")
    task_date = request.form.get("task_date")
    task_time = request.form.get("task_time")
    importance = request.form.get("importance")
    
    if task_name and task_date and importance in ("Major", "Medium", "Minor"):
        if task_time is not None:
            edit_task_db_with_time(task_id, task_name, task_date, task_time, importance)
        else:
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


@app.route('/box/add/<int:task_id>', methods=['POST'])
def box_add(task_id):
    username = session.get('user') if session else None
    if not username:
        return redirect(url_for('home'))
    move_task_to_box(task_id, username)
    return redirect(url_for('view_tasks'))


@app.route('/box/remove/<int:task_id>', methods=['POST'])
def box_remove(task_id):
    username = session.get('user') if session else None
    if not username:
        return redirect(url_for('home'))
    restore_task_from_box(task_id, username)
    return redirect(url_for('view_tasks'))


@app.route('/box/items')
def box_items():
    username = session.get('user') if session else None
    if not username:
        return jsonify([])
    items = get_box_items(username)
    return jsonify(items)


@app.route('/box/stats')
def box_stats():
    username = session.get('user') if session else None
    stats = get_box_stats(username)
    return jsonify(stats)


DEFAULT_REWARDS = [
    (1, "5 minute phone break", 20, 5),
    (2, "30 minute TV", 60, 30),
    (3, "Snack of choice", 40, 10),
    (4, "Buy something small", 150, 10),
    (5, "Game time 1 hour", 100, 60),
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
            SELECT id, name, date, time, importance 
            FROM tasks 
            WHERE user = ? 
            AND (completed = 0 OR completed IS NULL)
            AND (in_box = 0 OR in_box IS NULL)
            AND date BETWEEN ? AND ?
            ORDER BY date ASC
        """, (username, today.isoformat(), future_date.isoformat()))
    else:
        c.execute("""
            SELECT id, name, date, time, importance, user 
            FROM tasks 
            WHERE (completed = 0 OR completed IS NULL)
            AND (in_box = 0 OR in_box IS NULL)
            AND date BETWEEN ? AND ?
            ORDER BY date ASC
        """, (today.isoformat(), future_date.isoformat()))
    
    rows = c.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


def add_points(username, amount):
    conn = get_db_conn()
    c = conn.cursor()
    # increase current available points
    c.execute("UPDATE users SET points = COALESCE(points,0) + ? WHERE username = ?", (amount, username))
    # also track historical total earned (not reduced when spending)
    c.execute("UPDATE users SET total_earned = COALESCE(total_earned,0) + ? WHERE username = ?", (amount, username))
    conn.commit()
    conn.close()


def get_user_total_earned(username):
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT total_earned FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    conn.close()
    return row['total_earned'] if row and row['total_earned'] is not None else 0


def has_claimed_badge(username, badge_id):
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT 1 FROM redemptions WHERE username = ? AND reward_type = 'badge' AND reward_id = ? LIMIT 1", (username, badge_id))
    r = c.fetchone()
    conn.close()
    return bool(r)

def deduct_points(username, amount):
    conn = get_db_conn()
    c = conn.cursor()
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
    for rid, title, cost, duration in DEFAULT_REWARDS:
        rewards.append({
            'id': rid,
            'title': title,
            'cost': cost,
            'duration_minutes': duration,
            'claimable': points >= cost
        })
    return rewards

def get_custom_rewards_for_user(username):
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT id, title, cost, duration_minutes FROM custom_rewards WHERE username = ? ORDER BY cost ASC", (username,))
    rows = c.fetchall()
    conn.close()
    return [{'id': r['id'], 'title': r['title'], 'cost': r['cost'], 'duration_minutes': r['duration_minutes'] if 'duration_minutes' in r.keys() else 0, 'claimable': get_user_points(username) >= r['cost']} for r in rows]

def log_redemption(username, reward_type, reward_id, title, cost, expires_at=None):
    conn = get_db_conn()
    c = conn.cursor()
    redeemed_at = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    c.execute("INSERT INTO redemptions (username, reward_type, reward_id, title, cost, redeemed_at, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?)", (username, reward_type, reward_id, title, cost, redeemed_at, expires_at))
    conn.commit()
    conn.close()

def get_redeemed_rewards(username):
    """Get all redeemed rewards for a user, ordered by most recent first."""
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT id, reward_type, reward_id, title, cost, redeemed_at, expires_at FROM redemptions WHERE username = ? ORDER BY redeemed_at DESC LIMIT 50", (username,))
    rows = c.fetchall()
    conn.close()

    active = []
    now = datetime.datetime.now()
    for r in rows:
        expires = r['expires_at'] if 'expires_at' in r.keys() else None
        # keep reward if no expires_at (permanent) or expires in the future
        if not expires:
            rec = {'id': r['id'], 'reward_type': r['reward_type'] if 'reward_type' in r.keys() else None, 'reward_id': r['reward_id'] if 'reward_id' in r.keys() else None, 'title': r['title'], 'cost': r['cost'], 'redeemed_at': r['redeemed_at'], 'expires_at': None}
            # attach badge icon when applicable
            if rec.get('reward_type') == 'badge':
                bid = rec.get('reward_id')
                icon = next((b[3] for b in BADGES if b[0] == bid), None)
                rec['icon'] = icon
            active.append(rec)
            continue
        try:
            exp_dt = datetime.datetime.fromisoformat(expires)
        except Exception:
            # fallback to parsing common format
            try:
                exp_dt = datetime.datetime.strptime(expires, '%Y-%m-%d %H:%M:%S')
            except Exception:
                continue
        if exp_dt > now:
            rec = {'id': r['id'], 'reward_type': r['reward_type'] if 'reward_type' in r.keys() else None, 'reward_id': r['reward_id'] if 'reward_id' in r.keys() else None, 'title': r['title'], 'cost': r['cost'], 'redeemed_at': r['redeemed_at'], 'expires_at': exp_dt.isoformat()}
            if rec.get('reward_type') == 'badge':
                bid = rec.get('reward_id')
                icon = next((b[3] for b in BADGES if b[0] == bid), None)
                rec['icon'] = icon
            active.append(rec)

    return active

def nearest_reward_info(rewards, username):
    """Given a list of reward dicts (with cost), return the nearest non-claimable reward and pts needed."""
    points = get_user_points(username)
    non_claimable = [r for r in rewards if not r.get('claimable')]
    if not non_claimable:
        return None
    nearest = min(non_claimable, key=lambda r: r['cost'] - points)
    return {
        'reward': nearest,
        'points_needed': max(0, nearest['cost'] - points)
    }


@app.route('/rewards')
def rewards():
    username = session.get('user')
    if not username:
        return redirect(url_for('home'))
    points = get_user_points(username)
    total_earned = get_user_total_earned(username)
    badges = get_badges_for_display(username)
    redeemed_rewards = get_redeemed_rewards(username)

    # determine parent role so template can show/hide tabs
    is_parent = False
    if username:
        conn = get_db_conn(); c = conn.cursor()
        try:
            c.execute("SELECT role FROM users WHERE username = ?", (username,))
            row = c.fetchone()
            if row and ('role' in row.keys() and row['role'] == 'parent'):
                is_parent = True
        finally:
            conn.close()

    return render_template('rewards.html', username=username, points=points, total_earned=total_earned, badges=badges, redeemed_rewards=redeemed_rewards, is_parent=is_parent)


@app.route('/rewards/redeem/<int:badge_id>', methods=['POST'])
def redeem_badge(badge_id):
    username = session.get('user')
    if not username:
        return redirect(url_for('home'))
    matched = next((b for b in BADGES if b[0] == badge_id), None)
    if not matched:
        return "Unknown badge", 400
    _, title, cost, icon = matched
    # Check historical total earned points (not current balance)
    total_earned = get_user_total_earned(username)
    if total_earned < cost:
        return "Not enough total points earned to claim this badge", 400
    # Ensure badge not already claimed
    if has_claimed_badge(username, badge_id):
        return "Badge already claimed", 400
    # Claim the badge (no point deduction) and log redemption for record
    log_redemption(username, 'badge', badge_id, title, cost)
    return redirect(url_for('rewards'))


# Simple badges available for children on the Rewards tab
BADGES = [
    (1, "Star", 1000, "⭐"),
    (2, "Shield", 2000, "🛡️"),
    (3, "Gold Trophy", 3000, "🏆"),
    (4, "Platinum Crown", 5000, "👑"),
]

def get_badges_for_display(username):
    total_earned = get_user_total_earned(username)
    badges = []
    for bid, title, cost, icon in BADGES:
        already = has_claimed_badge(username, bid)
        badges.append({'id': bid, 'title': title, 'cost': cost, 'icon': icon, 'claimable': (not already) and (total_earned >= cost), 'claimed': already})
    return badges


@app.route('/attitude', methods=['GET', 'POST'])
def attitude():
    username = session.get('user')
    if not username:
        return redirect(url_for('home'))
    
    # Get user role to determine if parent or child
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT role FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    
    if not row:
        conn.close()
        return redirect(url_for('home'))
    
    is_parent = row['role'] == 'parent'
    
    # Parent can't access this route, redirect to parent attitude
    if is_parent:
        conn.close()
        return redirect(url_for('parent_attitude'))
    
    # Handle POST request: child submitting emotion
    if request.method == 'POST':
        emotion = request.form.get('emotion', '').strip()
        valid_emotions = ['furious', 'mad', 'worried', 'happy', 'sad']
        
        if emotion not in valid_emotions:
            conn.close()
            return redirect(url_for('attitude'))
        
        # Check if child already logged emotion today
        today = datetime.datetime.now().date().isoformat()
        c.execute("""
            SELECT created_at FROM emotion_logs 
            WHERE child_username = ? AND DATE(created_at) = ?
            ORDER BY created_at DESC LIMIT 1
        """, (username, today))
        last_emotion = c.fetchone()
        
        if last_emotion:
            # Already logged today, redirect (optional: could allow one update per day)
            conn.close()
            return redirect(url_for('attitude'))
        
        # Log the emotion
        created_at = datetime.datetime.now().isoformat()
        c.execute(
            "INSERT INTO emotion_logs (child_username, emotion, created_at) VALUES (?, ?, ?)",
            (username, emotion, created_at)
        )
        conn.commit()
        conn.close()
        return redirect(url_for('attitude'))
    
    # GET request: show emotion picker
    # Get today's emotion if any
    today = datetime.datetime.now().date().isoformat()
    c.execute("""
        SELECT emotion, created_at FROM emotion_logs 
        WHERE child_username = ? AND DATE(created_at) = ?
        ORDER BY created_at DESC LIMIT 1
    """, (username, today))
    today_emotion = c.fetchone()
    
    # Get recent emotions history
    c.execute("""
        SELECT emotion, created_at 
        FROM emotion_logs 
        WHERE child_username = ? 
        ORDER BY created_at DESC 
        LIMIT 30
    """, (username,))
    emotion_history = c.fetchall()
    
    conn.close()
    
    return render_template('child_attitude.html',
                           username=username,
                           today_emotion=today_emotion,
                           emotion_history=emotion_history,
                           is_parent=False)


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

    # detect parent role so UI can show parent-only tabs
    is_parent = False
    if username:
        conn = get_db_conn(); c = conn.cursor()
        try:
            c.execute("SELECT role FROM users WHERE username = ?", (username,))
            row = c.fetchone()
            if row and ('role' in row.keys() and row['role'] == 'parent'):
                is_parent = True
        finally:
            conn.close()

    return render_template('redeem.html',
                           username=username,
                           points=points,
                           default_rewards=default_rewards,
                           custom_rewards=custom_rewards,
                           redeemed_rewards=redeemed_rewards,
                           nearest=nearest,
                           is_parent=is_parent)


@app.route('/redeem/default/<int:reward_id>', methods=['POST'])
def redeem_default(reward_id):
    username = session.get('user')
    if not username:
        return redirect(url_for('home'))
  
    matched = next((r for r in DEFAULT_REWARDS if r[0] == reward_id), None)
    if not matched:
        return "Unknown reward", 400
    _, title, cost, duration = matched
    if not deduct_points(username, cost):
        return "Not enough points", 400
    expires_at = None
    if duration and duration > 0:
        expires_at = (datetime.datetime.now() + datetime.timedelta(minutes=duration)).isoformat()
    log_redemption(username, 'default', reward_id, title, cost, expires_at)
    
    return redirect(url_for('redeem'))


@app.route('/redeem/custom/<int:reward_id>', methods=['POST'])
def redeem_custom(reward_id):
    username = session.get('user')
    if not username:
        return redirect(url_for('home'))
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT id, title, cost, duration_minutes FROM custom_rewards WHERE id = ? AND username = ?", (reward_id, username))
    r = c.fetchone()
    conn.close()
    if not r:
        return "Reward not found", 404
    title = r['title']
    cost = r['cost']
    duration = r['duration_minutes'] if 'duration_minutes' in r.keys() else 0
    if not deduct_points(username, cost):
        return "Not enough points", 400
    expires_at = None
    if duration and duration > 0:
        expires_at = (datetime.datetime.now() + datetime.timedelta(minutes=duration)).isoformat()
    log_redemption(username, 'custom', reward_id, title, cost, expires_at)
    return redirect(url_for('redeem'))

@app.route('/redeem/add_custom', methods=['POST'])
def add_custom_reward():
    username = session.get('user')
    if not username:
        return redirect(url_for('home'))
    title = request.form.get('title', '').strip()
    cost = request.form.get('cost', '').strip()
    duration_raw = request.form.get('duration', '').strip() or '0'
    try:
        cost = int(cost)
        duration = int(duration_raw)
    except:
        return "Invalid cost", 400
    if not title or cost <= 0:
        return "Invalid input", 400
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("INSERT INTO custom_rewards (username, title, cost, duration_minutes) VALUES (?, ?, ?, ?)", (username, title, cost, duration))
    conn.commit()
    conn.close()
    return redirect(url_for('redeem'))


@app.route('/parent_dashboard')
def parent_dashboard():
    username = session.get('user') if session else None
    if not username:
        return redirect(url_for('home'))

    # ensure user is a parent
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT role FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    # sqlite3.Row does not implement .get(); use indexing by column name
    if not row or row['role'] != 'parent':
        conn.close()
        return redirect(url_for('activities'))

    # list children assigned to this parent
    c.execute("SELECT username, points FROM users WHERE parent_username = ?", (username,))
    children = [{'username': r['username'], 'points': r['points'] if r['points'] is not None else 0} for r in c.fetchall()]
    conn.close()
    return render_template('parent_dashboard.html', username=username, children=children)


@app.route('/parent/add_child', methods=['POST'])
def parent_add_child():
    parent = session.get('user') if session else None
    if not parent:
        return redirect(url_for('home'))

    child_username = request.form.get('child_username', '').strip()
    if not child_username:
        return redirect(url_for('parent_dashboard'))

    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE username = ?", (child_username,))
    if not c.fetchone():
        conn.close()
        return "Child not found", 404

    c.execute("UPDATE users SET parent_username = ? WHERE username = ?", (parent, child_username))
    conn.commit()
    conn.close()
    return redirect(url_for('parent_dashboard'))


@app.route('/parent/attitude', methods=['GET', 'POST'])
def parent_attitude():
    parent = session.get('user') if session else None
    if not parent:
        return redirect(url_for('home'))

    # verify parent role
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT role FROM users WHERE username = ?", (parent,))
    row = c.fetchone()
    if not row or row['role'] != 'parent':
        conn.close()
        return redirect(url_for('activities'))

    # list children assigned to this parent
    c.execute("SELECT username, points FROM users WHERE parent_username = ?", (parent,))
    children = [{'username': r['username'], 'points': r['points'] if r['points'] is not None else 0} for r in c.fetchall()]

    if request.method == 'POST':
        child_username = request.form.get('child_username', '').strip()
        rating = request.form.get('rating')
        mapping = {
            'struggled': 5,
            'mixed': 10,
            'good': 15,
            'excellent': 20
        }
        points = mapping.get(rating, 0)

        if not child_username or rating not in mapping:
            conn.close()
            return redirect(url_for('parent_attitude'))

        # prevent more than once per day for the same parent-child pair
        today = datetime.datetime.now().date().isoformat()
        c.execute("SELECT created_at FROM attitude_logs WHERE parent_username = ? AND child_username = ? ORDER BY created_at DESC LIMIT 1", (parent, child_username))
        last = c.fetchone()
        if last:
            try:
                last_date = datetime.datetime.fromisoformat(last['created_at']).date().isoformat()
            except Exception:
                last_date = None
            if last_date == today:
                conn.close()
                return redirect(url_for('parent_attitude'))

        created_at = datetime.datetime.now().isoformat()
        c.execute("INSERT INTO attitude_logs (parent_username, child_username, rating, points_awarded, created_at) VALUES (?, ?, ?, ?, ?)", (parent, child_username, rating, points, created_at))
        # award points to child and increment their historical total earned
        c.execute("UPDATE users SET points = COALESCE(points,0) + ? WHERE username = ?", (points, child_username))
        c.execute("UPDATE users SET total_earned = COALESCE(total_earned,0) + ? WHERE username = ?", (points, child_username))
        conn.commit()
        conn.close()
        return redirect(url_for('parent_attitude'))

    # GET request: show page
    conn = get_db_conn()
    c = conn.cursor()
    
    # Get child emotions for today
    today = datetime.datetime.now().date().isoformat()
    child_emotions = {}
    for child in children:
        c.execute("""
            SELECT emotion, created_at FROM emotion_logs 
            WHERE child_username = ? AND DATE(created_at) = ?
            ORDER BY created_at DESC LIMIT 1
        """, (child['username'], today))
        emotion_row = c.fetchone()
        if emotion_row:
            child_emotions[child['username']] = emotion_row
    
    conn.close()
    # determine if any children already logged today for display (optional)
    return render_template('attitude.html', username=parent, children=children, child_emotions=child_emotions)


@app.route('/parent/add_custom_reward_child', methods=['POST'])
def parent_add_custom_reward_child():
    parent = session.get('user') if session else None
    if not parent:
        return redirect(url_for('home'))

    child_username = request.form.get('child_username', '').strip()
    title = request.form.get('title', '').strip()
    cost_raw = request.form.get('cost', '').strip()
    try:
        cost = int(cost_raw)
    except Exception:
        return "Invalid cost", 400

    duration_raw = request.form.get('duration', '').strip() or '0'
    try:
        duration = int(duration_raw)
    except Exception:
        return "Invalid duration", 400

    if not child_username or not title or cost <= 0:
        return "Invalid input", 400

    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT parent_username FROM users WHERE username = ?", (child_username,))
    row = c.fetchone()
    if not row:
        conn.close()
        return "Child not found", 404

    # optionally verify parent owns this child (if assigned). We'll allow creation even if unassigned.
    c.execute("INSERT INTO custom_rewards (username, title, cost, duration_minutes) VALUES (?, ?, ?, ?)", (child_username, title, cost, duration))
    conn.commit()
    conn.close()
    return redirect(url_for('parent_dashboard'))


@app.route('/upload-task-card', methods=['POST'])
def upload_task_card():
    parent = session.get('user') if session else None
    if not parent:
        return redirect(url_for('home'))
    
    # Check if file and other fields are present
    if 'image' not in request.files:
        return "No image file provided", 400
    
    file = request.files['image']
    title = request.form.get('title', '').strip()
    points_str = request.form.get('points', '').strip()
    
    if not file or file.filename == '':
        return "No file selected", 400
    
    if not title:
        return "Title is required", 400
    
    try:
        points = int(points_str)
    except ValueError:
        return "Points must be a number", 400
    
    if file and allowed_file(file.filename):
        # Generate unique filename
        import uuid
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{uuid.uuid4()}.{ext}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Store in database
        conn = get_db_conn()
        c = conn.cursor()
        created_at = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        c.execute(
            "INSERT INTO visual_task_cards (parent_username, title, image_path, points, created_at) VALUES (?, ?, ?, ?, ?)",
            (parent, title, f"/static/uploads/{filename}", points, created_at)
        )
        conn.commit()
        conn.close()
        
        return redirect(url_for('visual_task_cards'))
    else:
        return "File type not allowed. Use PNG, JPG, JPEG, or GIF", 400


@app.route('/visual-task-cards', methods=['GET'])
def visual_task_cards():
    parent = session.get('user') if session else None
    if not parent:
        return redirect(url_for('home'))
    
    conn = get_db_conn()
    c = conn.cursor()
    
    # Get parent's custom cards
    c.execute(
        "SELECT id, title, image_path, points, created_at FROM visual_task_cards WHERE parent_username = ? AND is_recommended = 0 ORDER BY created_at DESC",
        (parent,)
    )
    custom_cards = [dict(row) for row in c.fetchall()]
    
    # Get recommended cards
    c.execute(
        "SELECT id, title, image_path, points FROM visual_task_cards WHERE is_recommended = 1 ORDER BY title"
    )
    recommended_cards = [dict(row) for row in c.fetchall()]
    
    conn.close()
    
    return render_template('visual_task_cards.html', custom_cards=custom_cards, recommended_cards=recommended_cards)


@app.route('/delete-task-card/<int:card_id>', methods=['POST'])
def delete_task_card(card_id):
    parent = session.get('user') if session else None
    if not parent:
        return redirect(url_for('home'))
    
    conn = get_db_conn()
    c = conn.cursor()
    
    # Verify ownership
    c.execute("SELECT image_path FROM visual_task_cards WHERE id = ? AND parent_username = ?", (card_id, parent))
    row = c.fetchone()
    
    if not row:
        conn.close()
        return "Card not found or not owned by you", 403
    
    # Delete image file
    image_path = row['image_path']
    if image_path.startswith('/'):
        filepath = '.' + image_path
    else:
        filepath = os.path.join('static', image_path)
    
    if os.path.exists(filepath):
        os.remove(filepath)
    
    # Delete from database
    c.execute("DELETE FROM visual_task_cards WHERE id = ?", (card_id,))
    c.execute("DELETE FROM task_completions WHERE card_id = ?", (card_id,))
    
    conn.commit()
    conn.close()
    
    return redirect(url_for('visual_task_cards'))


@app.route('/child-task-cards', methods=['GET'])
def child_task_cards():
    child = session.get('user') if session else None
    if not child:
        return redirect(url_for('home'))
    
    conn = get_db_conn()
    c = conn.cursor()
    
    # Get all available cards (from parent and recommended)
    c.execute("SELECT id, title, image_path, points FROM visual_task_cards ORDER BY created_at DESC")
    cards = [dict(row) for row in c.fetchall()]
    
    # Get completed cards for this child
    c.execute("SELECT card_id FROM task_completions WHERE child_username = ?", (child,))
    completed_ids = set(row['card_id'] for row in c.fetchall())
    
    conn.close()
    
    # Mark completed cards
    for card in cards:
        card['completed'] = card['id'] in completed_ids
    
    return render_template('child_task_cards.html', cards=cards)


@app.route('/complete-task-card', methods=['POST'])
def complete_task_card():
    child = session.get('user') if session else None
    if not child:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    data = request.get_json() if request.is_json else {}
    card_id = data.get('card_id')
    
    if not card_id:
        return jsonify({'success': False, 'error': 'Card ID required'}), 400
    
    conn = get_db_conn()
    c = conn.cursor()
    
    # Get card details
    c.execute("SELECT id, points FROM visual_task_cards WHERE id = ?", (card_id,))
    card = c.fetchone()
    
    if not card:
        conn.close()
        return jsonify({'success': False, 'error': 'Card not found'}), 404
    
    # Check if already completed
    c.execute("SELECT id FROM task_completions WHERE card_id = ? AND child_username = ?", (card_id, child))
    if c.fetchone():
        conn.close()
        return jsonify({'success': False, 'error': 'Already completed'}), 400
    
    # Record completion
    completed_at = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    c.execute(
        "INSERT INTO task_completions (card_id, child_username, completed_at) VALUES (?, ?, ?)",
        (card_id, child, completed_at)
    )
    
    # Award points
    points = card['points']
    c.execute("UPDATE users SET points = points + ? WHERE username = ?", (points, child))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'points_awarded': points})


if __name__ == "__main__":
    # start reminder scheduler thread in this process (avoids using Flask-specific hooks)
    try:
        start_reminder_scheduler()
    except Exception as e:
        print('Could not start reminder scheduler:', e)
    app.run(debug=True, port=5050)
    
    