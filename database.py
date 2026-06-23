import sqlite3
from pathlib import Path

# Database file will live next to this project folder
DB_PATH = Path(__file__).resolve().parent / "data.sqlite3"


def get_connection():
    """Create a SQLite connection with Row access by column name."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create required tables if they do not already exist."""
    conn = get_connection()
    cur = conn.cursor()

    # users table
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """
    )

    # clients table (one user -> many clients)
    # NOTE: Step 2 spec requires additional fields + updated_at + per-user unique email.
    # We use a two-step approach:
    # 1) Ensure the new schema exists (CREATE TABLE IF NOT EXISTS)
    # 2) If the DB already had the old schema, we migrate columns by recreating the table.

    # Create (new) clients table if it doesn't exist.
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            full_name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            company TEXT,
            address TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE (user_id, email)
        );
        """
    )

    # Check if the current clients table uses the old columns (name,address,updated_at).
    # If column 'full_name' is missing but 'name' exists, migrate.
    cur.execute("PRAGMA table_info(clients);")
    cols = [row["name"] if isinstance(row, sqlite3.Row) else row[1] for row in cur.fetchall()]

    if "full_name" not in cols and "name" in cols:
        # - Rename old table
        # - Create new table with desired schema
        # - Copy data from old -> new
        #   name -> full_name, (address missing -> NULL), updated_at -> created_at
        cur.execute("ALTER TABLE clients RENAME TO clients_old;")

        cur.execute(
            """
            CREATE TABLE clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                full_name TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                company TEXT,
                address TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id),
                UNIQUE (user_id, email)
            );
            """
        )

        cur.execute(
            """
            INSERT INTO clients (id, user_id, full_name, email, phone, company, address, created_at, updated_at)
            SELECT
                id,
                user_id,
                name as full_name,
                email,
                phone,
                company,
                NULL as address,
                created_at,
                created_at as updated_at
            FROM clients_old;
            """
        )

        cur.execute("DROP TABLE clients_old;")

    # tasks table (one client -> many tasks)
    # Step-3 spec fields:
    # id, client_id, title, description, priority, status, due_date, created_at, updated_at
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            priority TEXT NOT NULL,
            status TEXT NOT NULL,
            due_date TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (client_id) REFERENCES clients(id)
        );
        """
    )

    # If an older tasks table exists (missing columns), migrate to the Step-3 schema.
    cur.execute("PRAGMA table_info(tasks);")
    task_cols = [row["name"] for row in cur.fetchall()]

    needed = {"description", "due_date", "updated_at"}
    if not needed.issubset(set(task_cols)):
        cur.execute(
            """
            CREATE TABLE tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                priority TEXT NOT NULL,
                status TEXT NOT NULL,
                due_date TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (client_id) REFERENCES clients(id)
            );
            """
        )

        # Migrate existing data where possible.
        # - description/due_date will be NULL for old rows.
        # - updated_at will be set to created_at.
        cur.execute(
            """
            INSERT INTO tasks (id, client_id, title, priority, status, created_at, updated_at)
            SELECT
                id,
                client_id,
                title,
                priority,
                status,
                created_at,
                created_at as updated_at
            FROM tasks_old;
            """
        )

        cur.execute("DROP TABLE tasks_old;")

    # notes table (one client -> many notes)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (client_id) REFERENCES clients(id)
        );
        """
    )

    conn.commit()
    conn.close()

