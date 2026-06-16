from flask import Flask, render_template, request, redirect, url_for, session, flash
from database import init_db
from models import (
    create_user,
    get_user_by_email,
    verify_password,
    is_logged_in,
    logout_user
)

app = Flask(__name__)
app.secret_key = "change-this-secret-key"  # TODO: change in production

# Initialize database tables
init_db()


@app.route("/")
def home():
    # Simple redirect based on login state
    if is_logged_in(session):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if is_logged_in(session):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not username or not email or not password:
            flash("All fields are required.")
            return redirect(url_for("signup"))

        # Create user (includes uniqueness check)
        user = create_user(username=username, email=email, password=password)
        if user is None:
            flash("A user with this email already exists.")
            return redirect(url_for("signup"))

        # Log user in immediately after signup
        session["user_id"] = user["id"]
        session["email"] = user["email"]
        return redirect(url_for("dashboard"))

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if is_logged_in(session):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = get_user_by_email(email)
        if user is None:
            flash("Invalid email or password.")
            return redirect(url_for("login"))

        if not verify_password(user, password):
            flash("Invalid email or password.")
            return redirect(url_for("login"))

        session["user_id"] = user["id"]
        session["email"] = user["email"]
        session["username"] = user["username"]
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    logout_user(session)
    return redirect(url_for("login"))


@app.route("/dashboard")
def dashboard():
    if not is_logged_in(session):
        return redirect(url_for("login"))

    # Placeholder for now (will be implemented in later steps)
    return render_template("dashboard.html")


if __name__ == "__main__":
    app.run(debug=True)

