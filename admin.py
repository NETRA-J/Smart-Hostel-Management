"""Admin routes and workflows."""

import csv
import io
import re
import sqlite3
from datetime import datetime
from functools import wraps

from flask import Blueprint, render_template, request, redirect, url_for, session, flash, Response

from db import get_db_connection

bp = Blueprint("admin", __name__, url_prefix="/admin")

ROOM_NUMBER_PATTERN = re.compile(r"^[A-Za-z0-9-]{1,20}$")
ALLOWED_ROOM_TYPES = {"Single", "Double", "Dormitory"}


def _safe_page(value, default=1):
    try:
        page = int(value)
    except (TypeError, ValueError):
        return default
    return page if page > 0 else default


def _parse_positive_int(raw):
    raw = (raw or "").strip()
    if not raw.isdigit():
        return None
    value = int(raw)
    return value if value > 0 else None


def admin_required(view):
    # Gate admin-only pages in one place.
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("role") != "admin":
            return redirect(url_for("auth.admin_login"))
        return view(*args, **kwargs)

    return wrapped


@bp.route("/dashboard")
@admin_required
def dashboard():
    return render_template("admin_dashboard.html")


@bp.route("/add-room", methods=["GET", "POST"])
@admin_required
def add_room():
    error = None

    if request.method == "POST":
        room_number = request.form.get("room_number", "").strip()
        capacity = _parse_positive_int(request.form.get("capacity"))
        room_type = request.form.get("room_type", "").strip()
        monthly_fee = _parse_positive_int(request.form.get("monthly_fee"))

        if not ROOM_NUMBER_PATTERN.fullmatch(room_number):
            error = "Room number should be 1-20 chars (letters, numbers, hyphen)"
        elif room_type not in ALLOWED_ROOM_TYPES:
            error = "Please select a valid room type"
        elif capacity is None:
            error = "Capacity must be a positive number"
        elif room_type == "Single" and capacity != 1:
            error = "Single room capacity must be 1"
        elif room_type == "Double" and capacity != 2:
            error = "Double room capacity must be 2"
        elif room_type == "Dormitory" and not (3 <= capacity <= 10):
            error = "Dormitory capacity must be between 3 and 10"
        elif monthly_fee is None:
            error = "Monthly fee must be a positive number"

        if error:
            return render_template("add_room.html", error=error)

        conn = None
        try:
            # Insert a new room; UNIQUE constraint protects duplicates.
            conn = get_db_connection()
            conn.execute(
                """
                INSERT INTO rooms (room_number, capacity, room_type, monthly_fee)
                VALUES (?, ?, ?, ?)
                """,
                (room_number, capacity, room_type, monthly_fee),
            )
            conn.commit()
            flash("Room added successfully", "success")
            return redirect(url_for("admin.dashboard"))
        except sqlite3.IntegrityError:
            error = "Room already exists"
        except sqlite3.Error:
            error = "Database error while adding room"
        finally:
            if conn:
                conn.close()

    return render_template("add_room.html", error=error)


@bp.route("/allocate-room", methods=["GET", "POST"])
@admin_required
def allocate_room():
    error = None

    if request.method == "POST":
        student = request.form.get("student", "").strip()
        room = request.form.get("room", "").strip()

        if not student or not room:
            error = "Please select both student and room"
        else:
            allocated = False
            conn = None
            try:
                conn = get_db_connection()
                # Lock early to avoid over-allocating the same room.
                conn.execute("BEGIN IMMEDIATE")

                student_row = conn.execute(
                    "SELECT username FROM users WHERE username=? AND role='student'",
                    (student,),
                ).fetchone()

                already = conn.execute(
                    "SELECT 1 FROM allocations WHERE student_username=?",
                    (student,),
                ).fetchone()

                room_row = conn.execute(
                    "SELECT capacity, occupied FROM rooms WHERE room_number=?",
                    (room,),
                ).fetchone()

                if not student_row:
                    error = "Student not found"
                elif not room_row:
                    error = "Room not found"
                elif already:
                    error = "Student already has a room"
                elif room_row["occupied"] >= room_row["capacity"]:
                    error = "Room is already full"
                else:
                    conn.execute(
                        "INSERT INTO allocations (student_username, room_number) VALUES (?, ?)",
                        (student, room),
                    )
                    conn.execute(
                        "UPDATE rooms SET occupied = occupied + 1 WHERE room_number=?",
                        (room,),
                    )
                    conn.commit()
                    allocated = True
            except sqlite3.IntegrityError:
                if conn:
                    conn.rollback()
                error = "Allocation failed due to duplicate data"
            except sqlite3.Error:
                if conn:
                    conn.rollback()
                error = "Database error while allocating room"
            finally:
                if conn:
                    if not allocated:
                        try:
                            conn.rollback()
                        except sqlite3.Error:
                            pass
                    conn.close()

            if allocated:
                flash("Room allocated successfully", "success")
                return redirect(url_for("admin.dashboard"))

    conn = get_db_connection()
    students = conn.execute(
        "SELECT username FROM users WHERE role='student'"
    ).fetchall()
    rooms = conn.execute(
        "SELECT * FROM rooms WHERE occupied < capacity"
    ).fetchall()
    conn.close()

    return render_template(
        "allocate_room.html",
        students=students,
        rooms=rooms,
        error=error,
    )


@bp.route("/complaints")
@admin_required
def complaints():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()
    sort = request.args.get("sort", "new").strip()
    page = _safe_page(request.args.get("page"))
    per_page = 10
    offset = (page - 1) * per_page

    where = []
    params = []

    if q:
        where.append("(student_username LIKE ? OR complaint LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%"])
    if status in {"Pending", "Resolved"}:
        where.append("status = ?")
        params.append(status)

    order_by = "id DESC" if sort == "new" else "id ASC"
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    # Paginated complaint list with filters.
    conn = get_db_connection()
    complaints_list = conn.execute(
        f"SELECT * FROM complaints {where_sql} ORDER BY {order_by} LIMIT ? OFFSET ?",
        (*params, per_page, offset),
    ).fetchall()

    total = conn.execute(
        f"SELECT COUNT(*) AS cnt FROM complaints {where_sql}",
        params,
    ).fetchone()["cnt"]

    conn.close()

    total_pages = max(1, (total + per_page - 1) // per_page)

    return render_template(
        "admin_complaints.html",
        complaints=complaints_list,
        q=q,
        status=status,
        sort=sort,
        page=page,
        total_pages=total_pages,
    )


@bp.route("/resolve/<int:cid>")
@admin_required
def resolve_complaint(cid):
    conn = get_db_connection()
    updated = conn.execute(
        "UPDATE complaints SET status='Resolved' WHERE id=? AND status='Pending'",
        (cid,),
    )
    conn.commit()
    conn.close()

    if updated.rowcount:
        flash("Complaint resolved", "success")
    else:
        flash("Complaint not found or already resolved", "error")
    return redirect(url_for("admin.complaints"))


@bp.route("/students")
@admin_required
def students():
    q = request.args.get("q", "").strip()
    page = _safe_page(request.args.get("page"))
    per_page = 10
    offset = (page - 1) * per_page

    where_sql = "WHERE role='student'"
    params = []
    if q:
        where_sql += " AND (username LIKE ? OR full_name LIKE ? OR phone LIKE ? OR academic_course LIKE ?)"
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%"])

    conn = get_db_connection()
    students_list = conn.execute(
        f"""
        SELECT username, full_name, phone, academic_course, academic_year, academic_semester
        FROM users
        {where_sql}
        ORDER BY username ASC
        LIMIT ? OFFSET ?
        """,
        (*params, per_page, offset),
    ).fetchall()

    total = conn.execute(
        f"SELECT COUNT(*) AS cnt FROM users {where_sql}",
        params,
    ).fetchone()["cnt"]
    conn.close()

    total_pages = max(1, (total + per_page - 1) // per_page)

    return render_template(
        "admin_students.html",
        students=students_list,
        q=q,
        page=page,
        total_pages=total_pages,
    )


@bp.route("/students/delete/<username>", methods=["POST"])
@admin_required
def delete_student(username):
    conn = get_db_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")

        user = conn.execute(
            "SELECT username FROM users WHERE username=? AND role='student'",
            (username,),
        ).fetchone()

        if not user:
            conn.rollback()
            flash("Student not found", "error")
            return redirect(url_for("admin.students"))

        allocation = conn.execute(
            "SELECT room_number FROM allocations WHERE student_username=?",
            (username,),
        ).fetchone()

        if allocation:
            conn.execute(
                "DELETE FROM allocations WHERE student_username=?",
                (username,),
            )
            conn.execute(
                """
                UPDATE rooms
                SET occupied = CASE WHEN occupied > 0 THEN occupied - 1 ELSE 0 END
                WHERE room_number=?
                """,
                (allocation["room_number"],),
            )

        conn.execute("DELETE FROM fees WHERE student_username=?", (username,))
        conn.execute("DELETE FROM complaints WHERE student_username=?", (username,))
        conn.execute("DELETE FROM leave_requests WHERE student_username=?", (username,))
        conn.execute("DELETE FROM users WHERE username=? AND role='student'", (username,))

        conn.commit()
        flash("Student removed successfully", "success")
    except sqlite3.Error:
        conn.rollback()
        flash("Database error while removing student", "error")
    finally:
        conn.close()

    return redirect(url_for("admin.students"))


@bp.route("/leave-requests")
@admin_required
def leave_requests():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()
    sort = request.args.get("sort", "new").strip()
    page = _safe_page(request.args.get("page"))
    per_page = 10
    offset = (page - 1) * per_page

    where = []
    params = []
    if q:
        where.append("(student_username LIKE ? OR reason LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%"])
    if status in {"Pending", "Approved", "Rejected"}:
        where.append("status = ?")
        params.append(status)

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    order_by = "id DESC" if sort == "new" else "id ASC"

    conn = get_db_connection()
    leave_list = conn.execute(
        f"""
        SELECT id, student_username, reason, from_date, to_date, status, admin_remark, created_at, updated_at
        FROM leave_requests
        {where_sql}
        ORDER BY {order_by}
        LIMIT ? OFFSET ?
        """,
        (*params, per_page, offset),
    ).fetchall()

    total = conn.execute(
        f"SELECT COUNT(*) AS cnt FROM leave_requests {where_sql}",
        params,
    ).fetchone()["cnt"]
    conn.close()

    total_pages = max(1, (total + per_page - 1) // per_page)

    return render_template(
        "admin_leave_requests.html",
        leave_requests=leave_list,
        q=q,
        status=status,
        sort=sort,
        page=page,
        total_pages=total_pages,
    )


@bp.route("/leave-requests/<int:lid>/action", methods=["POST"])
@admin_required
def leave_request_action(lid):
    action = request.form.get("action", "").strip().lower()
    admin_remark = request.form.get("admin_remark", "").strip()

    if action not in {"approve", "reject"}:
        flash("Invalid leave action", "error")
        return redirect(url_for("admin.leave_requests"))
    if len(admin_remark) > 300:
        flash("Admin remark cannot exceed 300 characters", "error")
        return redirect(url_for("admin.leave_requests"))

    new_status = "Approved" if action == "approve" else "Rejected"
    updated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    conn = get_db_connection()
    row = conn.execute(
        "SELECT status FROM leave_requests WHERE id=?",
        (lid,),
    ).fetchone()

    if not row:
        conn.close()
        flash("Leave request not found", "error")
        return redirect(url_for("admin.leave_requests"))

    if row["status"] != "Pending":
        conn.close()
        flash("Leave request already processed", "error")
        return redirect(url_for("admin.leave_requests"))

    conn.execute(
        """
        UPDATE leave_requests
        SET status=?, admin_remark=?, updated_at=?
        WHERE id=?
        """,
        (new_status, admin_remark or None, updated_at, lid),
    )
    conn.commit()
    conn.close()

    flash(f"Leave request {new_status.lower()}", "success")
    return redirect(url_for("admin.leave_requests"))


@bp.route("/notices", methods=["GET", "POST"])
@admin_required
def notices():
    conn = get_db_connection()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        message = request.form.get("message", "").strip()

        if len(title) < 3 or len(title) > 120:
            flash("Title must be between 3 and 120 characters", "error")
        elif len(message) < 10 or len(message) > 2000:
            flash("Message must be between 10 and 2000 characters", "error")
        else:
            # Save notice with a timestamp.
            conn.execute(
                "INSERT INTO notices (title, message, created_at) VALUES (?, ?, datetime('now'))",
                (title, message),
            )
            conn.commit()
            flash("Notice posted", "success")

    q = request.args.get("q", "").strip()
    page = _safe_page(request.args.get("page"))
    per_page = 10
    offset = (page - 1) * per_page

    where_sql = ""
    params = []
    if q:
        where_sql = "WHERE title LIKE ? OR message LIKE ?"
        params = [f"%{q}%", f"%{q}%"]

    notices_list = conn.execute(
        f"SELECT * FROM notices {where_sql} ORDER BY id DESC LIMIT ? OFFSET ?",
        (*params, per_page, offset),
    ).fetchall()

    total = conn.execute(
        f"SELECT COUNT(*) AS cnt FROM notices {where_sql}",
        params,
    ).fetchone()["cnt"]

    conn.close()

    total_pages = max(1, (total + per_page - 1) // per_page)

    return render_template(
        "admin_notices.html",
        notices=notices_list,
        q=q,
        page=page,
        total_pages=total_pages,
    )


@bp.route("/fees", methods=["GET"])
@admin_required
def fees():
    conn = get_db_connection()

    status = request.args.get("status", "").strip()
    sort = request.args.get("sort", "student").strip()
    page = _safe_page(request.args.get("page"))
    per_page = 10
    offset = (page - 1) * per_page
    if sort not in {"student", "date"}:
        sort = "student"

    where = []
    params = []
    if status in {"Pending", "Paid"}:
        where.append("fees.status = ?")
        params.append(status)

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    order_by = "fees.student_username ASC" if sort == "student" else "fees.paid_date DESC"

    # Join fees with allocations and rooms for a richer view.
    fees_list = conn.execute(
        f"""
        SELECT
            fees.student_username,
            fees.status,
            fees.paid_date,
            rooms.monthly_fee
        FROM fees
        JOIN allocations ON fees.student_username = allocations.student_username
        JOIN rooms ON allocations.room_number = rooms.room_number
        {where_sql}
        ORDER BY {order_by}
        LIMIT ? OFFSET ?
        """,
        (*params, per_page, offset),
    ).fetchall()

    total = conn.execute(
        f"""
        SELECT COUNT(*) AS cnt
        FROM fees
        JOIN allocations ON fees.student_username = allocations.student_username
        JOIN rooms ON allocations.room_number = rooms.room_number
        {where_sql}
        """,
        params,
    ).fetchone()["cnt"]

    conn.close()

    total_pages = max(1, (total + per_page - 1) // per_page)

    return render_template(
        "admin_fees.html",
        fees=fees_list,
        status=status,
        sort=sort,
        page=page,
        total_pages=total_pages,
    )


@bp.route("/fees/export")
@admin_required
def export_fees():
    conn = get_db_connection()
    # Export all fees to CSV.
    rows = conn.execute(
        """
        SELECT
            fees.student_username,
            fees.status,
            fees.paid_date,
            rooms.monthly_fee
        FROM fees
        JOIN allocations ON fees.student_username = allocations.student_username
        JOIN rooms ON allocations.room_number = rooms.room_number
        ORDER BY fees.student_username ASC
        """
    ).fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["student_username", "status", "paid_date", "monthly_fee"])
    for row in rows:
        writer.writerow(
            [row["student_username"], row["status"], row["paid_date"], row["monthly_fee"]]
        )

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=fees.csv"},
    )


@bp.route("/complaints/export")
@admin_required
def export_complaints():
    conn = get_db_connection()
    # Export all complaints to CSV.
    rows = conn.execute(
        "SELECT id, student_username, complaint, status, created_at FROM complaints ORDER BY id DESC"
    ).fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "student_username", "complaint", "status", "created_at"])
    for row in rows:
        writer.writerow(
            [row["id"], row["student_username"], row["complaint"], row["status"], row["created_at"]]
        )

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=complaints.csv"},
    )


@bp.route("/stats")
@admin_required
def stats():
    conn = get_db_connection()

    # High-level stats for the admin dashboard.
    room_stats = conn.execute(
        """
        SELECT
            COUNT(*) AS total_rooms,
            SUM(capacity) AS total_capacity,
            SUM(occupied) AS total_occupied
        FROM rooms
        """
    ).fetchone()

    student_count = conn.execute(
        "SELECT COUNT(*) AS total_students FROM users WHERE role='student'"
    ).fetchone()

    pending_fees = conn.execute(
        "SELECT COUNT(*) AS pending_fees FROM fees WHERE status='Pending'"
    ).fetchone()

    conn.close()

    return render_template(
        "admin_stats.html",
        room_stats=room_stats,
        student_count=student_count,
        pending_fees=pending_fees,
    )


@bp.route("/rooms/vacancy")
@admin_required
def room_vacancy():
    conn = get_db_connection()
    # Show capacity and availability by room.
    rooms = conn.execute(
        """
        SELECT
            room_number,
            capacity,
            occupied,
            (capacity - occupied) AS available
        FROM rooms
        ORDER BY room_number ASC
        """
    ).fetchall()
    conn.close()

    return render_template("admin_vacancy.html", rooms=rooms)


@bp.route("/fees/defaulters")
@admin_required
def fee_defaulters():
    conn = get_db_connection()
    # Find students with pending fees.
    defaulters = conn.execute(
        """
        SELECT
            fees.student_username,
            fees.status,
            fees.paid_date,
            rooms.monthly_fee
        FROM fees
        JOIN allocations ON fees.student_username = allocations.student_username
        JOIN rooms ON allocations.room_number = rooms.room_number
        WHERE fees.status = 'Pending'
        ORDER BY fees.student_username ASC
        """
    ).fetchall()
    conn.close()

    return render_template("admin_defaulters.html", defaulters=defaulters)


@bp.route("/rooms/students")
@admin_required
def room_students():
    conn = get_db_connection()
    # List students grouped by room.
    rows = conn.execute(
        """
        SELECT
            rooms.room_number,
            allocations.student_username
        FROM rooms
        LEFT JOIN allocations ON allocations.room_number = rooms.room_number
        ORDER BY rooms.room_number ASC, allocations.student_username ASC
        """
    ).fetchall()
    conn.close()

    grouped = {}
    for row in rows:
        room_number = row["room_number"]
        if room_number not in grouped:
            grouped[room_number] = []
        if row["student_username"]:
            grouped[room_number].append(row["student_username"])

    return render_template("admin_room_students.html", rooms=grouped)
