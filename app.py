from flask import Flask, render_template, request, redirect, url_for, session
from login import login_bp

app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.register_blueprint(login_bp)

tasks = {
    "Major": [],
    "Medium": [],
    "Minor": []
}

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
    return render_template("activities.html", tasks=tasks)

# Add a new task
@app.route("/add_task", methods=["POST"])
def add_task():
    task_name = request.form.get("task_name")
    task_date = request.form.get("task_date")  
    importance = request.form.get("importance")

    if task_name and task_date and importance in tasks:
        
        tasks[importance].append({
            "name": task_name,
            "date": task_date
        })

    return redirect(url_for("activities"))

# Delete a task
@app.route("/delete_task/<importance>/<int:task_index>", methods=["POST"])
def delete_task(importance, task_index):
    if importance in tasks and 0 <= task_index < len(tasks[importance]):
        tasks[importance].pop(task_index)
    return redirect(url_for("activities"))


if __name__ == "__main__":
    app.run(debug=True, port=5050)

   