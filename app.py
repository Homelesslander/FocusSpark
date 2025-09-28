from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

# Store tasks in memory
tasks = {
    "Major": [],
    "Medium": [],
    "Minor": []
}

# Serve your existing pages
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

# Handle adding tasks from a form
@app.route("/add_task", methods=["POST"])
def add_task():
    task_name = request.form.get("task_name")
    importance = request.form.get("importance")
    
    if task_name and importance in tasks:
        tasks[importance].append(task_name)
    return redirect(url_for("activities"))
    
@app.route("/delete_task/<importance>/<int:task_index>", methods=["POST"])
def delete_task(importance, task_index):
    if importance in tasks and 0 <= task_index < len(tasks[importance]):
        tasks[importance].pop(task_index)
    return redirect(url_for("activities"))

if __name__ == "__main__":
    app.run(debug=True)
