import csv, io, os, sqlite3
from functools import wraps
from flask import (Flask, render_template, request, redirect, url_for,
                   session, flash, g, Response)
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "students.db")

# ---- CHANGE THESE before using the project for real ----
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD_HASH = generate_password_hash("admin123")
SECRET_KEY = "change-this-secret-key"
# --------------------------------------------------------

app = Flask(__name__)
app.secret_key = SECRET_KEY


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_):
    db = g.pop("db", None)
    if db:
        db.close()


def init_db():
    with sqlite3.connect(DB_PATH) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            roll_no TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            course TEXT,
            year TEXT,
            address TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")


def login_required(view):
    @wraps(view)
    def wrapped(*a, **kw):
        if not session.get("admin"):
            return redirect(url_for("login"))
        return view(*a, **kw)
    return wrapped


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = request.form.get("username", "").strip()
        pw = request.form.get("password", "")
        if user == ADMIN_USERNAME and check_password_hash(ADMIN_PASSWORD_HASH, pw):
            session["admin"] = True
            return redirect(url_for("dashboard"))
        flash("Wrong username or password. Try again.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def dashboard():
    q = request.args.get("q", "").strip()
    db = get_db()
    if q:
        like = f"%{q}%"
        rows = db.execute(
            "SELECT * FROM students WHERE name LIKE ? OR roll_no LIKE ? OR course LIKE ? "
            "ORDER BY id DESC", (like, like, like)).fetchall()
    else:
        rows = db.execute("SELECT * FROM students ORDER BY id DESC").fetchall()
    return render_template("dashboard.html", students=rows, q=q)


@app.route("/add", methods=["POST"])
@login_required
def add():
    f = request.form
    roll, name = f.get("roll_no", "").strip(), f.get("name", "").strip()
    if not roll or not name:
        flash("Roll number and name are required.", "error")
        return redirect(url_for("dashboard"))
    try:
        get_db().execute(
            "INSERT INTO students (roll_no, name, email, phone, course, year, address) "
            "VALUES (?,?,?,?,?,?,?)",
            (roll, name, f.get("email", "").strip(), f.get("phone", "").strip(),
             f.get("course", "").strip(), f.get("year", "").strip(),
             f.get("address", "").strip()))
        get_db().commit()
        flash(f"Saved {name}.", "ok")
    except sqlite3.IntegrityError:
        flash(f"Roll number {roll} already exists.", "error")
    return redirect(url_for("dashboard"))


@app.route("/delete/<int:sid>", methods=["POST"])
@login_required
def delete(sid):
    get_db().execute("DELETE FROM students WHERE id = ?", (sid,))
    get_db().commit()
    flash("Student record deleted.", "ok")
    return redirect(url_for("dashboard"))


@app.route("/export")
@login_required
def export():
    rows = get_db().execute(
        "SELECT roll_no,name,email,phone,course,year,address FROM students").fetchall()
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Roll No", "Name", "Email", "Phone", "Course", "Year", "Address"])
    w.writerows([tuple(r) for r in rows])
    return Response(out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=students.csv"})


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
