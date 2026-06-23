from flask import Flask, render_template, request, redirect, url_for, session, flash

from database import init_db
from models import (
    add_client,
    add_task,
    create_user,
    delete_client,
    delete_task,
    get_client_by_id,
    get_clients_for_user,
    get_task_by_id,
    get_tasks_for_client,
    get_user_by_email,
    is_logged_in,
    logout_user,
    update_client,
    update_task,
    verify_password,
)


app = Flask(__name__)
app.secret_key = "change-this-secret-key"  # TODO: change in production

# Initialize database tables
init_db()


@app.route("/")
def home():
    """Redirect user depending on login state."""
    if is_logged_in(session):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/signup", methods=["GET", "POST"])
def signup():
    """User registration."""
    if is_logged_in(session):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not username or not email or not password:
            flash("All fields are required.")
            return redirect(url_for("signup"))

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
    """User login."""
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
        session["username"] = user.get("username")
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out."""
    logout_user(session)
    return redirect(url_for("login"))


@app.route("/dashboard")
def dashboard():
    """Dashboard landing page."""
    if not is_logged_in(session):
        return redirect(url_for("login"))

    user_id = session.get("user_id")

    # Step-2 requirement: show total clients for this account.
    total_clients = len(get_clients_for_user(user_id=user_id))

    return render_template("dashboard.html", total_clients=total_clients)


@app.route("/clients", methods=["GET"])
def clients_list():
    """List clients for the logged-in user (Step-2 search/filter/sort)."""
    if not is_logged_in(session):
        return redirect(url_for("login"))

    user_id = session.get("user_id")

    # Step-2 params
    q = request.args.get("q", "").strip() or None  # full_name/company/email
    company_filter = request.args.get("company", "").strip() or None
    sort = request.args.get("sort", "newest").strip().lower()
    if sort not in ("newest", "oldest", "alpha_az", "alpha_za"):
        sort = "newest"

    clients = get_clients_for_user(
        user_id=user_id,
        q=q,
        company_filter=company_filter,
        sort=sort,
    )

    return render_template(
        "clients.html",
        clients=clients,
        search=q,
        company_filter=company_filter,
        sort=sort,
        editing_client=None,
        form_data=None,
    )


@app.route("/clients/add", methods=["POST"])
def clients_add():
    """Create a new client (Step-2)."""
    if not is_logged_in(session):
        return redirect(url_for("login"))

    user_id = session.get("user_id")

    full_name = request.form.get("full_name", "")
    email = request.form.get("email", "")
    phone = request.form.get("phone", "")
    company = request.form.get("company", "")
    address = request.form.get("address", "")

    _, error = add_client(
        user_id=user_id,
        full_name=full_name,
        email=email,
        phone=phone,
        company=company,
        address=address,
    )

    # Keep search params if validation fails
    q = request.args.get("q", "").strip() or None
    company_filter = request.args.get("company", "").strip() or None
    sort = request.args.get("sort", "newest").strip().lower()
    if sort not in ("newest", "oldest", "alpha_az", "alpha_za"):
        sort = "newest"

    if error:
        flash(error)
        clients = get_clients_for_user(
            user_id=user_id,
            q=q,
            company_filter=company_filter,
            sort=sort,
        )
        return render_template(
            "clients.html",
            clients=clients,
            search=q,
            company_filter=company_filter,
            sort=sort,
            editing_client=None,
            form_data={
                "full_name": full_name,
                "email": email,
                "phone": phone,
                "company": company,
                "address": address,
            },
        )

    return redirect(url_for("clients_list"))


@app.route("/clients/edit/<int:client_id>", methods=["GET"])
def clients_edit_get(client_id: int):
    """Load a client into the edit form (ownership enforced by model)."""
    if not is_logged_in(session):
        return redirect(url_for("login"))

    user_id = session.get("user_id")
    client = get_client_by_id(user_id=user_id, client_id=client_id)

    if not client:
        flash("Client not found (or you don't have access).")
        return redirect(url_for("clients_list"))

    clients = get_clients_for_user(user_id=user_id)

    return render_template(
        "clients.html",
        clients=clients,
        search=None,
        company_filter=None,
        sort="newest",
        editing_client=client,
        form_data={
            "full_name": client.get("full_name"),
            "email": client.get("email") or "",
            "phone": client.get("phone") or "",
            "company": client.get("company") or "",
            "address": client.get("address") or "",
        },
    )


@app.route("/clients/edit/<int:client_id>", methods=["POST"])
def clients_edit_post(client_id: int):
    """Update a client (ownership enforced by model)."""
    if not is_logged_in(session):
        return redirect(url_for("login"))

    user_id = session.get("user_id")

    full_name = request.form.get("full_name", "")
    email = request.form.get("email", "")
    phone = request.form.get("phone", "")
    company = request.form.get("company", "")
    address = request.form.get("address", "")

    _, error = update_client(
        user_id=user_id,
        client_id=client_id,
        full_name=full_name,
        email=email,
        phone=phone,
        company=company,
        address=address,
    )

    if error:
        flash(error)
        client = get_client_by_id(user_id=user_id, client_id=client_id)
        clients = get_clients_for_user(user_id=user_id)
        return render_template(
            "clients.html",
            clients=clients,
            search=None,
            company_filter=None,
            sort="newest",
            editing_client=client,
            form_data={
                "full_name": full_name,
                "email": email,
                "phone": phone,
                "company": company,
                "address": address,
            },
        )

    return redirect(url_for("clients_list"))


@app.route("/clients/delete/<int:client_id>", methods=["POST"])
def clients_delete(client_id: int):
    """Delete a client (ownership enforced by model)."""
    if not is_logged_in(session):
        return redirect(url_for("login"))

    user_id = session.get("user_id")
    ok = delete_client(user_id=user_id, client_id=client_id)

    if not ok:
        flash("Client not found (or you don't have access).")

    return redirect(url_for("clients_list"))


@app.route("/tasks/<int:client_id>", methods=["GET"])
def tasks_list(client_id: int):
    
    if not is_logged_in(session):
        return redirect(url_for("login"))

    user_id = session.get("user_id")

    # Ownership is enforced by the model.
    selected_client = get_client_by_id(user_id=user_id, client_id=client_id)
    if not selected_client:
        flash("Client not found (or you don't have access).")
        return redirect(url_for("clients_list"))

    # Filters (optional)
    status = request.args.get("status", "").strip() or None
    priority = request.args.get("priority", "").strip() or None
    due_date = request.args.get("due_date", "").strip() or None

    tasks = get_tasks_for_client(
        user_id=user_id,
        client_id=client_id,
        status=status,
        priority=priority,
        due_date=due_date,
    )

    return render_template(
        "tasks.html",
        selected_client=selected_client,
        selected_client_id=client_id,
        tasks=tasks,
        editing_task=None,
        status=status,
        priority=priority,
        due_date=due_date,
    )


@app.route("/tasks/<int:client_id>/add", methods=["POST"])
def tasks_add(client_id: int):
    """Create a new task for the selected client."""
    if not is_logged_in(session):
        return redirect(url_for("login"))

    user_id = session.get("user_id")

    title = request.form.get("title", "")
    description = request.form.get("description", "")
    priority = request.form.get("priority", "")
    status = request.form.get("status", "")
    due_date = request.form.get("due_date", "").strip() or None

    _, error = add_task(
        user_id=user_id,
        client_id=client_id,
        title=title,
        description=description,
        priority=priority,
        status=status,
        due_date=due_date,
    )

    if error:
        flash(error)

    return redirect(url_for("tasks_list", client_id=client_id))


@app.route("/tasks/<int:client_id>/edit/<int:task_id>", methods=["GET"])
def tasks_edit_get(task_id: int, client_id: int):
    """Load a task into the edit form."""
    if not is_logged_in(session):
        return redirect(url_for("login"))

    user_id = session.get("user_id")

    selected_client = get_client_by_id(user_id=user_id, client_id=client_id)
    if not selected_client:
        flash("Client not found (or you don't have access).")
        return redirect(url_for("clients_list"))

    editing_task = get_task_by_id(user_id=user_id, task_id=task_id)
    if not editing_task:
        flash("Task not found (or you don't have access).")
        return redirect(url_for("tasks_list", client_id=client_id))

    return render_template(
        "tasks.html",
        selected_client=selected_client,
        selected_client_id=client_id,
        tasks=get_tasks_for_client(user_id=user_id, client_id=client_id),
        editing_task=editing_task,
        status=None,
        priority=None,
        due_date=None,
    )


@app.route("/tasks/<int:client_id>/edit/<int:task_id>", methods=["POST"])
def tasks_edit_post(task_id: int, client_id: int):
    """Update a task."""
    if not is_logged_in(session):
        return redirect(url_for("login"))

    user_id = session.get("user_id")

    title = request.form.get("title", "")
    description = request.form.get("description", "")
    priority = request.form.get("priority", "")
    status = request.form.get("status", "")
    due_date = request.form.get("due_date", "").strip() or None

    _, error = update_task(
        user_id=user_id,
        task_id=task_id,
        title=title,
        description=description,
        priority=priority,
        status=status,
        due_date=due_date,
    )

    if error:
        flash(error)
        selected_client = get_client_by_id(user_id=user_id, client_id=client_id)
        editing_task = get_task_by_id(user_id=user_id, task_id=task_id)
        return render_template(
            "tasks.html",
            selected_client=selected_client,
            selected_client_id=client_id,
            tasks=get_tasks_for_client(user_id=user_id, client_id=client_id),
            editing_task=editing_task,
            status=None,
            priority=None,
            due_date=None,
        )

    flash("Task updated successfully.")
    return redirect(url_for("tasks_list", client_id=client_id))


@app.route("/tasks/delete/<int:task_id>", methods=["POST"])
def tasks_delete(task_id: int):
    """Delete a task (with ownership enforced by lookup)."""
    if not is_logged_in(session):
        return redirect(url_for("login"))

    user_id = session.get("user_id")

    existing = get_task_by_id(user_id=user_id, task_id=task_id)
    if not existing:
        flash("Task not found (or you don't have access).")
        return redirect(url_for("dashboard"))

    ok = delete_task(user_id=user_id, task_id=task_id)
    if not ok:
        flash("Unable to delete task.")
    else:
        flash("Task deleted successfully.")

    return redirect(url_for("tasks_list", client_id=existing["client_id"]))




if __name__ == "__main__":
    app.run(debug=True)

