import os
import sqlite3
import urllib.request
from flask import current_app


def ensure_images():
    """Download background images from GitHub repository if missing locally."""
    images_dir = os.path.join(current_app.root_path, "static", "images")
    os.makedirs(images_dir, exist_ok=True)
    base_url = "https://raw.githubusercontent.com/Sumitgohel07/smart_hostel/main/static/images/"
    headers = {"User-Agent": "Mozilla/5.0"}
    for i in range(1, 13):
        filename = f"bg_{i}.jpg"
        filepath = os.path.join(images_dir, filename)
        if not os.path.exists(filepath):
            try:
                req = urllib.request.Request(base_url + filename, headers=headers)
                with urllib.request.urlopen(req) as resp, open(filepath, "wb") as out_file:
                    out_file.write(resp.read())
            except Exception:
                pass


def get_db_connection():
    # Simple connection helper with Row access by column name.
    conn = sqlite3.connect(current_app.config["DATABASE"])
    conn.row_factory = sqlite3.Row
    return conn


def ensure_schema():
    """Create optional tables/indexes that may be missing in existing DB files."""
    conn = get_db_connection()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS leave_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_username TEXT NOT NULL,
            reason TEXT NOT NULL,
            from_date TEXT NOT NULL,
            to_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending',
            admin_remark TEXT,
            created_at TEXT,
            updated_at TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_leave_requests_student
        ON leave_requests (student_username);

        CREATE INDEX IF NOT EXISTS idx_leave_requests_status
        ON leave_requests (status);
        """
    )

    # Backfill optional columns for existing databases.
    users_table = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
    ).fetchone()
    if users_table:
        user_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()
        }
        if "age" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN age INTEGER")

    conn.commit()
    conn.close()
