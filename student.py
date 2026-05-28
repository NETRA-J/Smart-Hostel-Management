"""Student routes and workflows."""

from datetime import datetime
from functools import wraps

from flask import Blueprint, render_template, request, redirect, url_for, session, flash

from db import get_db_connection

bp = Blueprint("student", __name__, url_prefix="/student")

MIN_COMPLAINT_LENGTH = 10
MAX_COMPLAINT_LENGTH = 1000
MIN_LEAVE_REASON_LENGTH = 5
MAX_LEAVE_REASON_LENGTH = 500
MAX_LEAVE_DAYS = 60


def has_room_allocation(username):
    """Return True if the student has an allocated room."""
    conn = get_db_connection()
    allocation = conn.execute(
        "SELECT 1 FROM allocations WHERE student_username = ?",
        (username,),
    ).fetchone()
    conn.close()
    return allocation is not None


def student_required(view):
    # Gate student-only pages in one place.
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("role") != "student":
            return redirect(url_for("auth.student_login"))
        return view(*args, **kwargs)

    return wrapped


@bp.route("/dashboard")
@student_required
def dashboard():
    has_room = has_room_allocation(session["user"])
    return render_template("student_dashboard.html", has_room=has_room)


@bp.route("/profile")
@student_required
def profile():
    conn = get_db_connection()
    # Load profile info, room allocation, and fees in one view.
    user = conn.execute(
        """
        SELECT
            username,
            role,
            full_name,
            phone,
            email,
            date_of_birth,
            age,
            blood_group,
            caste,
            sub_caste,
            state,
            city,
            taluka,
            address,
            pincode,
            institution_name,
            academic_course,
            academic_year,
            academic_semester,
            roll_number,
            guardian_name,
            guardian_phone
        FROM users
        WHERE username=?
        """,
        (session["user"],),
    ).fetchone()

    if not user:
        conn.close()
        session.clear()
        return redirect(url_for("auth.student_login"))

    room = conn.execute(
        """
        SELECT rooms.room_number, rooms.room_type, rooms.capacity, rooms.occupied
        FROM allocations
        JOIN rooms ON allocations.room_number = rooms.room_number
        WHERE allocations.student_username=?
        """,
        (session["user"],),
    ).fetchone()

    fee = conn.execute(
        """
        SELECT
            fees.status,
            fees.paid_date,
            rooms.monthly_fee
        FROM fees
        JOIN allocations ON fees.student_username = allocations.student_username
        JOIN rooms ON allocations.room_number = rooms.room_number
        WHERE fees.student_username = ?
        """,
        (session["user"],),
    ).fetchone()

    notice_count = conn.execute(
        "SELECT COUNT(*) AS cnt FROM notices"
    ).fetchone()["cnt"]

    conn.close()

    return render_template(
        "student_profile.html",
        user=user,
        room=room,
        fee=fee,
        notice_count=notice_count,
    )


@bp.route("/my-room")
@student_required
def my_room():
    conn = get_db_connection()
    room = conn.execute(
        """
        SELECT rooms.room_number, rooms.capacity, rooms.occupied
        FROM allocations
        JOIN rooms ON allocations.room_number = rooms.room_number
        WHERE allocations.student_username=?
        """,
        (session["user"],),
    ).fetchone()
    conn.close()

    return render_template("my_room.html", room=room)


@bp.route("/complaint", methods=["GET", "POST"])
@student_required
def complaint():
    error = None
    complaint_text = ""

    if not has_room_allocation(session["user"]):
        flash("Room allocation is required before submitting complaints", "error")
        return redirect(url_for("student.dashboard"))

    if request.method == "POST":
        complaint_text = request.form.get("complaint", "").strip()

        if len(complaint_text) < MIN_COMPLAINT_LENGTH:
            error = f"Complaint must be at least {MIN_COMPLAINT_LENGTH} characters"
        elif len(complaint_text) > MAX_COMPLAINT_LENGTH:
            error = f"Complaint cannot exceed {MAX_COMPLAINT_LENGTH} characters"

        if not error:
            created_at = datetime.now().strftime("%Y-%m-%d %H:%M")

            # Save complaint with timestamp.
            conn = get_db_connection()
            conn.execute(
                "INSERT INTO complaints (student_username, complaint, created_at) VALUES (?, ?, ?)",
                (session["user"], complaint_text, created_at),
            )
            conn.commit()
            conn.close()

            flash("Complaint submitted", "success")
            return redirect(url_for("student.dashboard"))

    return render_template("student_complaint.html", error=error, complaint_text=complaint_text)


@bp.route("/leave-request", methods=["GET", "POST"])
@student_required
def leave_request():
    error = None
    reason = ""
    from_date = ""
    to_date = ""

    if not has_room_allocation(session["user"]):
        flash("Room allocation is required before applying for leave", "error")
        return redirect(url_for("student.dashboard"))

    if request.method == "POST":
        reason = request.form.get("reason", "").strip()
        from_date = request.form.get("from_date", "").strip()
        to_date = request.form.get("to_date", "").strip()

        if len(reason) < MIN_LEAVE_REASON_LENGTH:
            error = f"Reason must be at least {MIN_LEAVE_REASON_LENGTH} characters"
        elif len(reason) > MAX_LEAVE_REASON_LENGTH:
            error = f"Reason cannot exceed {MAX_LEAVE_REASON_LENGTH} characters"
        elif not from_date or not to_date:
            error = "Please select both from and to dates"
        else:
            try:
                from_obj = datetime.strptime(from_date, "%Y-%m-%d").date()
                to_obj = datetime.strptime(to_date, "%Y-%m-%d").date()
                today = datetime.now().date()
                days = (to_obj - from_obj).days + 1

                if from_obj > to_obj:
                    error = "From date cannot be after to date"
                elif from_obj < today:
                    error = "From date cannot be in the past"
                elif days > MAX_LEAVE_DAYS:
                    error = f"Leave cannot be more than {MAX_LEAVE_DAYS} days"
            except ValueError:
                error = "Invalid date format"

        if not error:
            created_at = datetime.now().strftime("%Y-%m-%d %H:%M")
            conn = get_db_connection()

            overlapping = conn.execute(
                """
                SELECT 1
                FROM leave_requests
                WHERE student_username=?
                  AND status IN ('Pending', 'Approved')
                  AND from_date <= ?
                  AND to_date >= ?
                """,
                (session["user"], to_date, from_date),
            ).fetchone()

            if overlapping:
                conn.close()
                error = "You already have a pending/approved leave in this date range"
                return render_template(
                    "student_leave_request.html",
                    error=error,
                    reason=reason,
                    from_date=from_date,
                    to_date=to_date,
                )

            conn.execute(
                """
                INSERT INTO leave_requests (
                    student_username,
                    reason,
                    from_date,
                    to_date,
                    status,
                    created_at
                ) VALUES (?, ?, ?, ?, 'Pending', ?)
                """,
                (session["user"], reason, from_date, to_date, created_at),
            )
            conn.commit()
            conn.close()

            flash("Leave request submitted", "success")
            return redirect(url_for("student.my_leaves"))

    return render_template(
        "student_leave_request.html",
        error=error,
        reason=reason,
        from_date=from_date,
        to_date=to_date,
    )


@bp.route("/my-leaves")
@student_required
def my_leaves():
    conn = get_db_connection()
    leave_requests = conn.execute(
        """
        SELECT id, reason, from_date, to_date, status, admin_remark, created_at, updated_at
        FROM leave_requests
        WHERE student_username=?
        ORDER BY id DESC
        """,
        (session["user"],),
    ).fetchall()
    conn.close()

    return render_template("student_my_leaves.html", leave_requests=leave_requests)


@bp.route("/my-complaints")
@student_required
def my_complaints():
    conn = get_db_connection()
    # Show student's own complaints only.
    complaints_list = conn.execute(
        """
        SELECT id, complaint, status, created_at
        FROM complaints
        WHERE student_username=?
        ORDER BY id DESC
        """,
        (session["user"],),
    ).fetchall()
    conn.close()

    return render_template("student_my_complaints.html", complaints=complaints_list)


@bp.route("/notices")
@student_required
def notices():
    conn = get_db_connection()
    # Show all notices, newest first.
    notices_list = conn.execute(
        "SELECT * FROM notices ORDER BY id DESC"
    ).fetchall()
    conn.close()

    return render_template("student_notices.html", notices=notices_list)


@bp.route("/my-fees")
@student_required
def my_fees():
    conn = get_db_connection()
    # If there's no room allocation, fees don't apply yet.
    allocation = conn.execute(
        "SELECT * FROM allocations WHERE student_username = ?",
        (session["user"],),
    ).fetchone()

    if not allocation:
        conn.close()
        return render_template(
            "my_fees.html",
            fee=None,
            no_room=True,
        )

    fee = conn.execute(
        """
        SELECT
            fees.status,
            fees.paid_date,
            rooms.monthly_fee
        FROM fees
        JOIN allocations ON fees.student_username = allocations.student_username
        JOIN rooms ON allocations.room_number = rooms.room_number
        WHERE fees.student_username = ?
        """,
        (session["user"],),
    ).fetchone()

    conn.close()

    return render_template("my_fees.html", fee=fee, no_room=False)


@bp.route("/pay-fee", methods=["POST"])
@student_required
def pay_fee():
    payment_date = datetime.now().strftime("%Y-%m-%d")

    # Mark the student's fees as paid.
    conn = get_db_connection()
    updated = conn.execute(
        """
        UPDATE fees
        SET status = 'Paid',
            paid_date = ?
        WHERE student_username = ?
          AND status = 'Pending'
        """,
        (payment_date, session["user"]),
    )
    conn.commit()
    conn.close()

    if updated.rowcount:
        flash("Fee paid successfully", "success")
    else:
        flash("No pending fee found", "error")
    return redirect(url_for("student.my_fees"))
