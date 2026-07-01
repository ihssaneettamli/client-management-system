import sqlite3
from database import get_connection
from werkzeug.security import generate_password_hash, check_password_hash


# ---------------------------
# Authentication helpers
# ---------------------------

def is_logged_in(session):
    return session is not None and session.get("user_id") is not None


def logout_user(session):
    """Clear authentication info from session."""
    if session is None:
        return
    session.pop("user_id", None)
    session.pop("email", None)


def create_user(username: str, email: str, password: str):
    """Create a new user.

    Returns:
        dict-like row (id, email, ...) if created successfully
        None if email already exists.
    """
    password_hash = generate_password_hash(password)

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            (username, email, password_hash),
        )
        conn.commit()
        user_id = cur.lastrowid
        return get_user_by_id(user_id)
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def get_user_by_id(user_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, username, email, password_hash, created_at FROM users WHERE id = ?",
        (user_id,),
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_email(email: str):
    """Fetch user by email."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, email, password_hash, created_at FROM users WHERE email = ?",
        (email,),
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def verify_password(user: dict, password: str) -> bool:
    """Verify the given password against stored password_hash."""
    if user is None:
        return False
    stored_hash = user.get("password_hash")
    return check_password_hash(stored_hash, password)


# ---------------------------
# Client management helpers
# ---------------------------

def _validate_email(email: str) -> bool:
    return email is not None and ("@" in email) and ("." in email)


def _validate_phone(phone: str) -> bool:
    """Simple phone validation: digits, spaces, plus, dashes.

    Beginner-friendly rule: 7-15 digits total (after removing non-digits).
    """
    if phone is None:
        return False
    allowed = set("0123456789+ -()")
    if any(ch not in allowed for ch in phone):
        return False
    digits = "".join([c for c in phone if c.isdigit()])
    return 7 <= len(digits) <= 15


def _validate_client_payload(full_name: str, email: str, phone: str, company: str, address: str | None):
    """Validate Step-2 client fields.

    Required fields: full_name, email, phone, company.
    """
    full_name = (full_name or "").strip()
    email = (email or "").strip().lower() if email is not None else None
    phone = (phone or "").strip() if phone is not None else None
    company = (company or "").strip() if company is not None else None
    address = (address or "").strip() if address is not None else None

    if not full_name:
        return None, "Full name is required."
    if not email:
        return None, "Email is required."
    if not _validate_email(email):
        return None, "Please enter a valid email address."
    if not phone:
        return None, "Phone number is required."
    if not _validate_phone(phone):
        return None, "Please enter a valid phone number."
    if not company:
        return None, "Company is required."

    return {
        "full_name": full_name,
        "email": email,
        "phone": phone,
        "company": company,
        "address": address if address else None,
    }, None


def add_client(
    user_id: int,
    full_name: str,
    email: str,
    phone: str,
    company: str,
    address: str | None,
):
    """Insert a new client for the given user."""
    clean, err = _validate_client_payload(
        full_name=full_name,
        email=email,
        phone=phone,
        company=company,
        address=address,
    )
    if err:
        return None, err

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO clients (user_id, full_name, email, phone, company, address)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, clean["full_name"], clean["email"], clean["phone"], clean["company"], clean["address"]),
        )
        conn.commit()
        client_id = cur.lastrowid
        return get_client_by_id(user_id=user_id, client_id=client_id), None
    except sqlite3.IntegrityError:
        return None, "A client with this email already exists for your account."
    finally:
        conn.close()


def get_client_by_id(user_id: int, client_id: int):
    """Fetch a single client only if it belongs to the user."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, user_id, full_name, email, phone, company, address, created_at, updated_at
        FROM clients
        WHERE id = ? AND user_id = ?
        """,
        (client_id, user_id),
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_clients_for_user(
    user_id: int,
    q: str | None = None,
    company_filter: str | None = None,
    sort: str = "newest",
):
    """List clients for a user with search + filters."""
    conn = get_connection()
    cur = conn.cursor()

    params = [user_id]
    where = ["user_id = ?"]

    if q:
        s = f"%{q.strip()}%"
        where.append("(full_name LIKE ? OR company LIKE ? OR email LIKE ?)")
        params.extend([s, s, s])

    if company_filter:
        where.append("company = ?")
        params.append(company_filter)

    if sort == "oldest":
        order_by = "created_at ASC"
    elif sort == "alpha_az":
        order_by = "full_name ASC"
    elif sort == "alpha_za":
        order_by = "full_name DESC"
    else:
        order_by = "created_at DESC"

    sql = f"""
        SELECT id, full_name, email, phone, company, address, created_at, updated_at
        FROM clients
        WHERE {' AND '.join(where)}
        ORDER BY {order_by}
    """

    cur.execute(sql, tuple(params))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_client(
    user_id: int,
    client_id: int,
    full_name: str,
    email: str,
    phone: str,
    company: str,
    address: str | None,
):
    """Update a client's data if ownership matches."""
    clean, err = _validate_client_payload(
        full_name=full_name,
        email=email,
        phone=phone,
        company=company,
        address=address,
    )
    if err:
        return None, err

    existing = get_client_by_id(user_id=user_id, client_id=client_id)
    if not existing:
        return None, "Client not found (or you don't have access)."

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE clients
            SET full_name = ?, email = ?, phone = ?, company = ?, address = ?,
                updated_at = datetime('now')
            WHERE id = ? AND user_id = ?
            """,
            (
                clean["full_name"],
                clean["email"],
                clean["phone"],
                clean["company"],
                clean["address"],
                client_id,
                user_id,
            ),
        )
        conn.commit()
        return get_client_by_id(user_id=user_id, client_id=client_id), None
    except sqlite3.IntegrityError:
        return None, "A client with this email already exists for your account."
    finally:
        conn.close()


def delete_client(user_id: int, client_id: int):
    existing = get_client_by_id(user_id=user_id, client_id=client_id)
    if not existing:
        return False

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM clients WHERE id = ? AND user_id = ?", (client_id, user_id))
    conn.commit()
    conn.close()
    return True


# ---------------------------
# Task management helpers (Step-3)
# ---------------------------

def _validate_task_priority(priority: str) -> str | None:
    priority = (priority or "").strip()
    allowed = {"High", "Medium", "Low"}
    return priority if priority in allowed else None


def _validate_task_status(status: str) -> str | None:
    # Step-4 requirement: add In Progress status support
    status = (status or "").strip()
    allowed = {"Pending", "In Progress", "Completed"}
    return status if status in allowed else None


def _validate_task_payload(title: str, description: str, priority: str, status: str, due_date: str | None):
    title = (title or "").strip()
    description = (description or "").strip() if description is not None else ""

    if not title:
        return None, "Task title is required."

    clean_priority = _validate_task_priority(priority)
    if not clean_priority:
        return None, "Priority must be High, Medium, or Low."

    clean_status = _validate_task_status(status)
    if not clean_status:
        return None, "Status must be Pending, In Progress, or Completed."

    clean_due_date = None
    if due_date:
        # frontend sends YYYY-MM-DD
        clean_due_date = due_date.strip()

    return {
        "title": title,
        "description": description or None,
        "priority": clean_priority,
        "status": clean_status,
        "due_date": clean_due_date,
    }, None


def _assert_client_belongs_to_user(user_id: int, client_id: int):
    """Return True if the client belongs to the user."""
    return get_client_by_id(user_id=user_id, client_id=client_id) is not None


def add_task(
    user_id: int,
    client_id: int,
    title: str,
    description: str,
    priority: str,
    status: str,
    due_date: str | None,
):
    if not _assert_client_belongs_to_user(user_id=user_id, client_id=client_id):
        return None, "Client not found (or you don't have access)."

    clean, err = _validate_task_payload(
        title=title,
        description=description,
        priority=priority,
        status=status,
        due_date=due_date,
    )
    if err:
        return None, err

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO tasks (client_id, title, description, priority, status, due_date)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            client_id,
            clean["title"],
            clean["description"],
            clean["priority"],
            clean["status"],
            clean["due_date"],
        ),
    )
    conn.commit()
    task_id = cur.lastrowid
    conn.close()
    return get_task_by_id(user_id=user_id, task_id=task_id), None


def get_task_by_id(user_id: int, task_id: int):
    """Fetch a single task only if its client belongs to the user."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT t.*
        FROM tasks t
        JOIN clients c ON c.id = t.client_id
        WHERE t.id = ? AND c.user_id = ?
        """,
        (task_id, user_id),
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def update_task(
    user_id: int,
    task_id: int,
    title: str,
    description: str,
    priority: str,
    status: str,
    due_date: str | None,
):
    clean, err = _validate_task_payload(
        title=title,
        description=description,
        priority=priority,
        status=status,
        due_date=due_date,
    )
    if err:
        return None, err

    existing = get_task_by_id(user_id=user_id, task_id=task_id)
    if not existing:
        return None, "Task not found (or you don't have access)."

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE tasks
            SET title = ?, description = ?, priority = ?, status = ?, due_date = ?,
                updated_at = datetime('now')
            WHERE id = ?
            """,
            (
                clean["title"],
                clean["description"],
                clean["priority"],
                clean["status"],
                clean["due_date"],
                task_id,
            ),
        )
        conn.commit()
        return get_task_by_id(user_id=user_id, task_id=task_id), None
    finally:
        conn.close()


def delete_task(user_id: int, task_id: int) -> bool:
    existing = get_task_by_id(user_id=user_id, task_id=task_id)
    if not existing:
        return False

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()
    return True


def get_tasks_for_client(
    user_id: int,
    client_id: int,
    status: str | None = None,
    priority: str | None = None,
    due_date: str | None = None,
):
    """List tasks for a client owned by user, with filters."""
    if not _assert_client_belongs_to_user(user_id=user_id, client_id=client_id):
        return []

    where = ["t.client_id = ?"]
    params = [client_id]

    if status:
        clean_status = _validate_task_status(status)
        if clean_status:
            where.append("t.status = ?")
            params.append(clean_status)

    if priority:
        clean_priority = _validate_task_priority(priority)
        if clean_priority:
            where.append("t.priority = ?")
            params.append(clean_priority)

    if due_date:
        due_date = due_date.strip()
        if due_date:
            where.append("t.due_date = ?")
            params.append(due_date)

    sql = f"""
        SELECT t.*
        FROM tasks t
        JOIN clients c ON c.id = t.client_id
        WHERE {' AND '.join(where)} AND c.user_id = ?
        ORDER BY t.created_at DESC
    """
    params.append(user_id)

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(sql, tuple(params))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

