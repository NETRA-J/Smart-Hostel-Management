"""Flask app factory for Smart Hostel."""

from flask import Flask, render_template

from admin import bp as admin_bp
from auth import bp as auth_bp
from student import bp as student_bp
from config import Config
from db import ensure_schema


def create_app():
    # App factory keeps configuration and blueprints in one place.
    app = Flask(__name__)
    app.config.from_object(Config)

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(student_bp)

    with app.app_context():
        ensure_schema()

    @app.route("/")
    def index():
        return render_template("index.html")

    return app


app = create_app()


if __name__ == "__main__":
    # Debug mode is fine for local development.
    app.run(debug=True)
