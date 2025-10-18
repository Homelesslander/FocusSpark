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
    conn.commit()
    conn.close()



def get_tasks_grouped():
    
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT id, name, date, importance FROM tasks ORDER BY id")
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

       
        c.execute("UPDATE users SET points = points + ? WHERE username = ?", (points, username))

        
        c.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
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




if __name__ == "__main__":
    app.run(debug=True, port=5050)