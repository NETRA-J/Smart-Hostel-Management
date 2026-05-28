BEGIN TRANSACTION;
DROP TABLE IF EXISTS "allocations";
CREATE TABLE allocations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_username TEXT UNIQUE,
    room_number TEXT
);
DROP TABLE IF EXISTS "complaints";
CREATE TABLE complaints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_username TEXT,
    complaint TEXT,
    status TEXT DEFAULT 'Pending',
    created_at TEXT
);
DROP TABLE IF EXISTS "fees";
CREATE TABLE fees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_username TEXT NOT NULL,
    status TEXT NOT NULL,
    paid_date TEXT,
    UNIQUE(student_username)
);
DROP TABLE IF EXISTS "leave_requests";
CREATE TABLE leave_requests (
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
CREATE INDEX idx_leave_requests_student ON leave_requests (student_username);
CREATE INDEX idx_leave_requests_status ON leave_requests (status);
DROP TABLE IF EXISTS "notices";
CREATE TABLE notices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TEXT
);
DROP TABLE IF EXISTS "rooms";
CREATE TABLE rooms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_number TEXT UNIQUE,
    capacity INTEGER NOT NULL CHECK (capacity > 0),
    occupied INTEGER NOT NULL DEFAULT 0 CHECK (occupied >= 0 AND occupied <= capacity),
    room_type TEXT,
    monthly_fee INTEGER NOT NULL CHECK (monthly_fee > 0)
);
DROP TABLE IF EXISTS "users";
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    password TEXT NOT NULL,
    role TEXT,
    full_name TEXT,
    phone TEXT,
    email TEXT,
    caste TEXT,
    sub_caste TEXT,
    date_of_birth TEXT,
    age INTEGER,
    blood_group TEXT,
    state TEXT,
    city TEXT,
    taluka TEXT,
    address TEXT,
    pincode TEXT,
    institution_name TEXT,
    academic_course TEXT,
    academic_year INTEGER,
    academic_semester INTEGER,
    roll_number TEXT,
    guardian_name TEXT,
    guardian_phone TEXT
);
INSERT INTO "complaints" ("id","student_username","complaint","status","created_at") VALUES (1,'sumit','helllo guys','Resolved','2026-02-03 16:39');
INSERT INTO "fees" ("id","student_username","status","paid_date") VALUES (1,'sumit','Pending','2026-02-03');
INSERT INTO "users" ("id","username","password","role") VALUES (1,'sumit','sumit','student');
COMMIT;
