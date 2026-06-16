import sqlite3
from database import get_connection
from werkzeug.security import generate_password_hash, check_password_hash


def is_logged_in(session):
    """Return True if the session contains a logged-in user_id."""
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
        # Unique constraint failed (email already exists)
        return None
    finally:
        conn.close()


def get_user_by_id(user_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, username, email, password_hash, created_at FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_email(email: str):
    """Fetch user by email."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, email, password_hash, created_at FROM users WHERE email = ?", (email,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def verify_password(user: dict, password: str) -> bool:
    """Verify the given password against stored password_hash."""
    if user is None:
        return False
    stored_hash = user.get("password_hash")
    return check_password_hash(stored_hash, password)

