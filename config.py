"""App configuration values."""

import os

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "smart_hostel")
    # Always point at the project database unless overridden.
    DATABASE = os.environ.get(
        "DATABASE", os.path.join(os.path.dirname(__file__), "database.db")
    )
