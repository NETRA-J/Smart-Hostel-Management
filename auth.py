"""Authentication routes."""

import re
from datetime import date, datetime

from flask import Blueprint, render_template, request, redirect, url_for, session

from db import get_db_connection

bp = Blueprint("auth", __name__)

MIN_STUDENT_AGE = 18
MAX_STUDENT_AGE = 60

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.]{3,20}$")
PASSWORD_PATTERN = re.compile(r"^(?=.*[A-Za-z])(?=.*\d).{6,64}$")
NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z .'-]{1,49}$")
LOCATION_TEXT_PATTERN = re.compile(r"^[A-Za-z][A-Za-z .'-]{1,59}$")
PHONE_PATTERN = re.compile(r"^[6-9]\d{9}$")
PINCODE_PATTERN = re.compile(r"^[1-9]\d{5}$")
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def calculate_age(dob: date) -> int:
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


@bp.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = None

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        # Simple hardcoded admin credentials for this project.
        if username == "admin" and password == "admin":
            session["user"] = "admin"
            session["role"] = "admin"
            return redirect(url_for("admin.dashboard"))
        error = "Invalid admin credentials"

    return render_template("admin_login.html", error=error)


@bp.route("/student/login", methods=["GET", "POST"])
def student_login():
    error = None

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not USERNAME_PATTERN.fullmatch(username):
            error = "Username must be 3-20 chars (letters, numbers, _ or .)"
        elif len(password) < 4 or len(password) > 64:
            error = "Password length must be 4-64 characters"
        elif " " in password:
            error = "Password cannot contain spaces"

        if not error:
            # Validate student credentials from the DB.
            conn = get_db_connection()
            user = conn.execute(
                "SELECT * FROM users WHERE username=? AND password=?",
                (username, password),
            ).fetchone()
            conn.close()

            if user:
                session["user"] = user["username"]
                session["role"] = "student"
                return redirect(url_for("student.dashboard"))
            error = "Invalid student credentials"

    return render_template("student_login.html", error=error)


@bp.route("/student/signup", methods=["GET", "POST"])
def student_signup():
    error = None

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()
        full_name = request.form.get("full_name", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip()
        date_of_birth = request.form.get("date_of_birth", "").strip()
        age = request.form.get("age", "").strip()
        blood_group = request.form.get("blood_group", "").strip()
        caste = request.form.get("caste", "").strip()
        sub_caste = request.form.get("sub_caste", "").strip()
        state = request.form.get("state", "").strip()
        city = request.form.get("city", "").strip()
        taluka = request.form.get("taluka", "").strip()
        address = request.form.get("address", "").strip()
        pincode = request.form.get("pincode", "").strip()
        institution_name = request.form.get("institution_name", "").strip()
        academic_course = request.form.get("academic_course", "").strip()
        custom_course_years = request.form.get("custom_course_years", "").strip()
        academic_year = request.form.get("academic_year", "").strip()
        academic_semester = request.form.get("academic_semester", "").strip()
        guardian_name = request.form.get("guardian_name", "").strip()
        guardian_phone = request.form.get("guardian_phone", "").strip()
        confirm = request.form.get("confirm")

        course_years = {
            "BCA": 3,
            "BSc": 3,
            "BA": 3,
            "BCom": 3,
            "BE/BTech": 4,
            "Diploma": 3,
            "MCA": 2,
            "MBA": 2,
        }

        allowed_blood_groups = {
            "A+",
            "A-",
            "B+",
            "B-",
            "AB+",
            "AB-",
            "O+",
            "O-",
            "Other",
        }

        parsed_dob = None
        computed_age = None
        years = None

        if not USERNAME_PATTERN.fullmatch(username):
            error = "Username must be 3-20 chars (letters, numbers, _ or .)"
        elif not PASSWORD_PATTERN.fullmatch(password):
            error = "Password must be 6-64 chars and include letters and numbers"
        elif password != confirm_password:
            error = "Password and confirm password do not match"
        elif not NAME_PATTERN.fullmatch(full_name):
            error = "Enter a valid full name"
        elif not PHONE_PATTERN.fullmatch(phone):
            error = "Phone number must be 10 digits and start with 6-9"
        elif email and not EMAIL_PATTERN.fullmatch(email):
            error = "Email address looks invalid"
        elif not date_of_birth:
            error = "Date of birth is required"
        else:
            try:
                parsed_dob = datetime.strptime(date_of_birth, "%Y-%m-%d").date()
                computed_age = calculate_age(parsed_dob)
                if computed_age < MIN_STUDENT_AGE:
                    error = f"Student age must be at least {MIN_STUDENT_AGE} years"
                elif computed_age > MAX_STUDENT_AGE:
                    error = f"Student age must be at most {MAX_STUDENT_AGE} years"
                elif not age.isdigit():
                    error = "Age is invalid. Please reselect date of birth"
                elif int(age) != computed_age:
                    error = "Age does not match date of birth"
            except ValueError:
                error = "Invalid date of birth"

        if not error and blood_group not in allowed_blood_groups:
            error = "Please select a valid blood group"
        elif not error and not caste:
            error = "Caste is required"
        elif not error and not LOCATION_TEXT_PATTERN.fullmatch(state):
            error = "State must be 2-60 letters (spaces, . ' - allowed)"
        elif not error and not LOCATION_TEXT_PATTERN.fullmatch(city):
            error = "City must be 2-60 letters (spaces, . ' - allowed)"
        elif not error and not LOCATION_TEXT_PATTERN.fullmatch(taluka):
            error = "Taluka must be 2-60 letters (spaces, . ' - allowed)"
        elif not error and not address:
            error = "Address is required"
        elif not error and not PINCODE_PATTERN.fullmatch(pincode):
            error = "Pincode must be a valid 6-digit number"
        elif not error and not institution_name:
            error = "College/School name is required"
        elif not error and academic_course not in {*course_years.keys(), "Other"}:
            error = "Please select a valid course"
        elif not error and academic_course == "Other":
            if not custom_course_years.isdigit():
                error = "For Other course, enter course duration in years"
            else:
                years = int(custom_course_years)
                if years < 1 or years > 8:
                    error = "Custom course duration must be between 1 and 8 years"
        elif not error:
            years = course_years.get(academic_course)

        if not error and not academic_year.isdigit():
            error = "Please select a valid year"
        elif not error and not academic_semester.isdigit():
            error = "Please select a valid semester"
        elif not error and not NAME_PATTERN.fullmatch(guardian_name):
            error = "Guardian name is required"
        elif not error and not PHONE_PATTERN.fullmatch(guardian_phone):
            error = "Guardian phone must be 10 digits and start with 6-9"
        elif not error and guardian_phone == phone:
            error = "Guardian phone cannot be same as student phone"
        elif not error and confirm != "on":
            error = "Please confirm the details are correct"

        if not error:
            year_num = int(academic_year)
            sem_num = int(academic_semester)
            max_sem = years * 2
            start_sem = (year_num - 1) * 2 + 1
            end_sem = min(year_num * 2, max_sem)

            if year_num < 1 or year_num > years:
                error = "Selected year is out of range for the course"
            elif sem_num < 1 or sem_num > max_sem:
                error = "Selected semester is out of range for the course"
            elif sem_num < start_sem or sem_num > end_sem:
                error = "Selected semester does not match the selected year"

        if not error:
            academic_course_value = (
                f"Other ({years} Years)" if academic_course == "Other" else academic_course
            )

            conn = get_db_connection()
            existing_user = conn.execute(
                "SELECT * FROM users WHERE username=?",
                (username,),
            ).fetchone()

            if existing_user:
                error = "Username already exists"
            else:
                # Create the student and seed fees as pending.
                conn.execute(
                    """
                    INSERT INTO users (
                        username,
                        password,
                        role,
                        full_name,
                        phone,
                        email,
                        caste,
                        sub_caste,
                        date_of_birth,
                        age,
                        blood_group,
                        state,
                        city,
                        taluka,
                        address,
                        pincode,
                        institution_name,
                        academic_course,
                        academic_year,
                        academic_semester,
                        guardian_name,
                        guardian_phone
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        username,
                        password,
                        "student",
                        full_name,
                        phone,
                        email or None,
                        caste,
                        sub_caste or None,
                        date_of_birth,
                        computed_age,
                        blood_group,
                        state,
                        city,
                        taluka,
                        address,
                        pincode,
                        institution_name,
                        academic_course_value,
                        academic_year,
                        academic_semester,
                        guardian_name,
                        guardian_phone,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO fees (student_username, status)
                    VALUES (?, ?)
                    """,
                    (username, "Pending"),
                )

                conn.commit()
                conn.close()
                return redirect(url_for("auth.student_login"))

            conn.close()

        if error:
            return render_template("student_signup.html", error=error)

    return render_template("student_signup.html", error=error)


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))
