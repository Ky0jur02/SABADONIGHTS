import sqlite3
import hashlib
import os
from contextlib import contextmanager


# =========================================================
# DATABASE CONFIGURATION
# =========================================================

DATABASE_NAME = "students.db"


# =========================================================
# CONNECT TO DATABASE
# =========================================================

def connect_db():
    connection = sqlite3.connect(DATABASE_NAME)
    # SQLite ignores foreign keys unless this is switched on for
    # every connection. It makes ON DELETE CASCADE / SET NULL real.
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def _db():
    """Open a connection and always close it. Uncommitted work is rolled back."""
    connection = connect_db()
    try:
        yield connection
    finally:
        connection.close()


def _clean_text(value):
    """Trim the ends and collapse repeated spaces: '  MARIA   ANNE ' -> 'MARIA ANNE'."""
    return " ".join(str(value or "").split())


# =========================================================
# CREATE TABLES + SAFE MIGRATION
# =========================================================

def create_tables():
    """
    Creates every table if missing and migrates an existing students.db
    in place. Nothing is dropped or emptied:

    * teachers / attempts / session_id data are left untouched.
    * `sections` is a brand new table.
    * `students` gets two new columns (last_name, section_id) via
      PRAGMA table_info + ALTER TABLE. Old students keep their id and
      first_name, get last_name = '' and section_id = NULL (legacy /
      unassigned) so their attempts stay linked.
    * If ALTER TABLE ever fails, the students table is rebuilt by
      copying every row (see _rebuild_students_table).
    """

    connection = connect_db()
    cursor = connection.cursor()

    # -----------------------------------------------------
    # TEACHERS TABLE
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS teachers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL
        )
    """)

    # -----------------------------------------------------
    # SECTIONS TABLE (new)
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            section_name TEXT NOT NULL,
            teacher_id INTEGER NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (teacher_id)
                REFERENCES teachers(id)
                ON DELETE CASCADE
        )
    """)

    # A teacher cannot have two sections with the same name (any letter case).
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_sections_teacher_name
        ON sections (teacher_id, section_name COLLATE NOCASE)
    """)

    # -----------------------------------------------------
    # STUDENTS TABLE
    # (fresh installs get the full schema; existing databases
    #  are upgraded by _migrate_students_table below)
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL DEFAULT '',
            section_id INTEGER,
            FOREIGN KEY (section_id)
                REFERENCES sections(id)
                ON DELETE SET NULL
        )
    """)

    # -----------------------------------------------------
    # ATTEMPTS TABLE
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            student_id INTEGER NOT NULL,

            game_type TEXT NOT NULL,

            question TEXT NOT NULL,

            student_answer INTEGER,

            correct_answer INTEGER NOT NULL,

            is_correct INTEGER NOT NULL,

            response_time REAL NOT NULL,

            difficulty_before INTEGER NOT NULL,

            difficulty_after INTEGER NOT NULL,

            decision TEXT NOT NULL,

            decision_reason TEXT,

            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (student_id)
                REFERENCES students(id)
                ON DELETE CASCADE
        )
    """)

    connection.commit()

    # -----------------------------------------------------
    # SESSION ID COLUMN (added for teacher dashboard grouping)
    # Added safely with ALTER TABLE so existing attempt rows
    # and the existing schema are never destroyed.
    # -----------------------------------------------------

    cursor.execute("PRAGMA table_info(attempts)")
    existing_columns = [row[1] for row in cursor.fetchall()]
    if "session_id" not in existing_columns:
        cursor.execute("ALTER TABLE attempts ADD COLUMN session_id TEXT")
        connection.commit()

    # -----------------------------------------------------
    # STUDENTS: add last_name + section_id to an old database
    # -----------------------------------------------------

    _migrate_students_table(connection)

    # -----------------------------------------------------
    # INDEXES (speed up section / student / performance lookups)
    # -----------------------------------------------------

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_students_section ON students (section_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_attempts_student ON attempts (student_id)")
    connection.commit()

    # Create a default teacher account if none exist yet, so the
    # dashboard is reachable on a fresh install without breaking
    # anything that already exists.
    cursor.execute("SELECT COUNT(*) FROM teachers")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO teachers (username, password_hash) VALUES (?, ?)",
            ("teacher", _hash_password("teacher123"))
        )
        connection.commit()

    connection.close()


def _student_columns(cursor):
    cursor.execute("PRAGMA table_info(students)")
    return {row[1] for row in cursor.fetchall()}


def _migrate_students_table(connection):
    cursor = connection.cursor()
    columns = _student_columns(cursor)

    try:
        if "last_name" not in columns:
            cursor.execute(
                "ALTER TABLE students ADD COLUMN last_name TEXT NOT NULL DEFAULT ''"
            )

        if "section_id" not in columns:
            # SQLite allows adding a REFERENCES column when its default is NULL.
            cursor.execute(
                "ALTER TABLE students ADD COLUMN section_id INTEGER "
                "REFERENCES sections(id) ON DELETE SET NULL"
            )

        connection.commit()

    except sqlite3.OperationalError:
        # Very old SQLite builds: fall back to a copy-and-swap rebuild.
        connection.rollback()
        _rebuild_students_table(connection)


def _rebuild_students_table(connection):
    """
    Fallback migration: builds a new students table with the final schema,
    copies every existing row (same ids, so attempts stay linked), then
    swaps it in. Runs with foreign keys off, exactly as the SQLite docs
    recommend, and is fully rolled back if anything goes wrong.
    """
    cursor = connection.cursor()
    columns = _student_columns(cursor)
    last_name_expr = "last_name" if "last_name" in columns else "''"
    section_expr = "section_id" if "section_id" in columns else "NULL"

    connection.commit()
    cursor.execute("PRAGMA foreign_keys = OFF")

    try:
        cursor.execute("BEGIN")
        cursor.execute("DROP TABLE IF EXISTS students_new")
        cursor.execute("""
            CREATE TABLE students_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL DEFAULT '',
                section_id INTEGER,
                FOREIGN KEY (section_id)
                    REFERENCES sections(id)
                    ON DELETE SET NULL
            )
        """)
        cursor.execute(
            f"""
            INSERT INTO students_new (id, first_name, last_name, section_id)
            SELECT id, first_name, {last_name_expr}, {section_expr}
            FROM students
            """
        )
        cursor.execute("DROP TABLE students")
        cursor.execute("ALTER TABLE students_new RENAME TO students")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.execute("PRAGMA foreign_keys = ON")


# =========================================================
# TEACHER AUTH HELPERS
# =========================================================

def _hash_password(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def authenticate_teacher(username, password):
    """Returns the teacher's id if the username/password match, otherwise None."""
    with _db() as connection:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT id, password_hash FROM teachers WHERE username = ?",
            (str(username).strip(),)
        )
        row = cursor.fetchone()

    if row is None:
        return None

    if row[1] == _hash_password(password):
        return row[0]

    return None


def verify_teacher(username, password):
    """Returns True if the username/password combo matches a teacher row."""
    return authenticate_teacher(username, password) is not None


def get_teacher(teacher_id):
    with _db() as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT id, username FROM teachers WHERE id = ?", (teacher_id,))
        row = cursor.fetchone()

    if row is None:
        return None
    return {"id": row[0], "username": row[1]}


# =========================================================
# OWNERSHIP HELPERS
# (the database itself enforces who may touch what, the UI
#  filtering is not the only line of defence)
# =========================================================

def _teacher_owns_section(cursor, teacher_id, section_id):
    if teacher_id is None or section_id is None:
        return False
    cursor.execute(
        "SELECT 1 FROM sections WHERE id = ? AND teacher_id = ?",
        (section_id, teacher_id)
    )
    return cursor.fetchone() is not None


def _teacher_owns_student(cursor, teacher_id, student_id):
    if teacher_id is None or student_id is None:
        return False
    cursor.execute(
        """
        SELECT 1
        FROM students st
        JOIN sections se ON se.id = st.section_id
        WHERE st.id = ? AND se.teacher_id = ?
        """,
        (student_id, teacher_id)
    )
    return cursor.fetchone() is not None


def teacher_owns_section(teacher_id, section_id):
    with _db() as connection:
        return _teacher_owns_section(connection.cursor(), teacher_id, section_id)


def teacher_owns_student(teacher_id, student_id):
    with _db() as connection:
        return _teacher_owns_student(connection.cursor(), teacher_id, student_id)


# =========================================================
# SECTIONS
# =========================================================

def _section_dict(row):
    return {
        "id": row[0],
        "section_name": row[1],
        "teacher_id": row[2],
        "created_at": row[3]
    }


def create_section(teacher_id, section_name):
    """
    Creates a section owned by the teacher and returns its id.
    Raises ValueError with a friendly message for an empty or duplicate name.
    """
    name = _clean_text(section_name)
    if not name:
        raise ValueError("SECTION NAME CANNOT BE EMPTY")

    with _db() as connection:
        cursor = connection.cursor()

        cursor.execute("SELECT 1 FROM teachers WHERE id = ?", (teacher_id,))
        if cursor.fetchone() is None:
            raise PermissionError("UNKNOWN TEACHER")

        cursor.execute(
            """
            SELECT 1 FROM sections
            WHERE teacher_id = ? AND LOWER(section_name) = LOWER(?)
            """,
            (teacher_id, name)
        )
        if cursor.fetchone() is not None:
            raise ValueError("SECTION ALREADY EXISTS")

        try:
            cursor.execute(
                "INSERT INTO sections (section_name, teacher_id) VALUES (?, ?)",
                (name, teacher_id)
            )
        except sqlite3.IntegrityError:
            raise ValueError("SECTION ALREADY EXISTS")

        connection.commit()
        return cursor.lastrowid


def get_teacher_sections(teacher_id):
    """Only the sections that belong to this teacher."""
    with _db() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT id, section_name, teacher_id, created_at
            FROM sections
            WHERE teacher_id = ?
            ORDER BY section_name COLLATE NOCASE
            """,
            (teacher_id,)
        )
        return [_section_dict(row) for row in cursor.fetchall()]


def get_section(section_id, teacher_id=None):
    """
    Returns {"id", "section_name", "teacher_id", "created_at"} or None.
    When teacher_id is given, None is returned unless that teacher owns it.
    """
    with _db() as connection:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT id, section_name, teacher_id, created_at FROM sections WHERE id = ?",
            (section_id,)
        )
        row = cursor.fetchone()

    if row is None:
        return None
    if teacher_id is not None and row[2] != teacher_id:
        return None
    return _section_dict(row)


def get_all_sections():
    """
    Every section with its student count. Used by the STUDENT login
    "select your section" screen (students do not know their teacher).
    """
    with _db() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT se.id, se.section_name, se.teacher_id, COUNT(st.id)
            FROM sections se
            LEFT JOIN students st ON st.section_id = se.id
            GROUP BY se.id
            ORDER BY se.section_name COLLATE NOCASE
            """
        )
        return [
            {"id": r[0], "section_name": r[1], "teacher_id": r[2], "student_count": r[3]}
            for r in cursor.fetchall()
        ]


def update_section(section_id, section_name, teacher_id=None):
    """
    Renames a section. Returns True when updated, False if it does not exist.
    Raises ValueError (empty / duplicate name) or PermissionError (not the owner).
    """
    name = _clean_text(section_name)
    if not name:
        raise ValueError("SECTION NAME CANNOT BE EMPTY")

    with _db() as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT teacher_id FROM sections WHERE id = ?", (section_id,))
        row = cursor.fetchone()
        if row is None:
            return False

        owner_id = row[0]
        if teacher_id is not None and owner_id != teacher_id:
            raise PermissionError("THIS SECTION BELONGS TO ANOTHER TEACHER")

        cursor.execute(
            """
            SELECT 1 FROM sections
            WHERE teacher_id = ? AND LOWER(section_name) = LOWER(?) AND id != ?
            """,
            (owner_id, name, section_id)
        )
        if cursor.fetchone() is not None:
            raise ValueError("SECTION ALREADY EXISTS")

        try:
            cursor.execute(
                "UPDATE sections SET section_name = ? WHERE id = ?",
                (name, section_id)
            )
        except sqlite3.IntegrityError:
            raise ValueError("SECTION ALREADY EXISTS")

        connection.commit()
        return True


def delete_section(section_id, teacher_id=None):
    """
    Deletes a section together with its students and their attempts.
    Returns the number of sections deleted (0 or 1).
    Raises PermissionError when teacher_id is given and does not own it.
    """
    with _db() as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT teacher_id FROM sections WHERE id = ?", (section_id,))
        row = cursor.fetchone()
        if row is None:
            return 0

        if teacher_id is not None and row[0] != teacher_id:
            raise PermissionError("THIS SECTION BELONGS TO ANOTHER TEACHER")

        cursor.execute(
            "DELETE FROM attempts WHERE student_id IN "
            "(SELECT id FROM students WHERE section_id = ?)",
            (section_id,)
        )
        cursor.execute("DELETE FROM students WHERE section_id = ?", (section_id,))
        cursor.execute("DELETE FROM sections WHERE id = ?", (section_id,))
        connection.commit()
        return cursor.rowcount


# =========================================================
# ADD STUDENT
# =========================================================

def add_student(first_name, last_name="", section_id=None, teacher_id=None):
    """
    Adds a student and returns the new student id.

    section_id  - the section the student belongs to (None = legacy/unassigned)
    teacher_id  - when given, the section must belong to that teacher

    Raises ValueError (empty name, unknown section, duplicate student in the
    section) or PermissionError (section owned by another teacher).
    """
    first = _clean_text(first_name)
    last = _clean_text(last_name)

    if not first:
        raise ValueError("FIRST NAME CANNOT BE EMPTY")

    with _db() as connection:
        cursor = connection.cursor()

        if section_id is not None:
            cursor.execute("SELECT teacher_id FROM sections WHERE id = ?", (section_id,))
            row = cursor.fetchone()
            if row is None:
                raise ValueError("SECTION DOES NOT EXIST")
            if teacher_id is not None and row[0] != teacher_id:
                raise PermissionError("THIS SECTION BELONGS TO ANOTHER TEACHER")

            cursor.execute(
                """
                SELECT 1 FROM students
                WHERE section_id = ?
                  AND LOWER(first_name) = LOWER(?)
                  AND LOWER(last_name) = LOWER(?)
                """,
                (section_id, first, last)
            )
            if cursor.fetchone() is not None:
                raise ValueError("STUDENT ALREADY EXISTS IN THIS SECTION")
        elif teacher_id is not None:
            raise PermissionError("A TEACHER CAN ONLY ADD STUDENTS TO A SECTION")

        cursor.execute(
            """
            INSERT INTO students (first_name, last_name, section_id)
            VALUES (?, ?, ?)
            """,
            (first, last, section_id)
        )
        connection.commit()
        return cursor.lastrowid


# =========================================================
# GET STUDENTS
# =========================================================

def get_students_by_section(section_id, teacher_id=None):
    """
    Students of ONE section as (id, first_name, last_name, section_id).
    When teacher_id is given and does not own the section, an empty
    list is returned.
    """
    if section_id is None:
        return []

    with _db() as connection:
        cursor = connection.cursor()

        if teacher_id is not None and not _teacher_owns_section(cursor, teacher_id, section_id):
            return []

        cursor.execute(
            """
            SELECT id, first_name, last_name, section_id
            FROM students
            WHERE section_id = ?
            ORDER BY first_name COLLATE NOCASE, last_name COLLATE NOCASE, id
            """,
            (section_id,)
        )
        return cursor.fetchall()


def get_students():
    """
    Legacy helper: EVERY student in the database as
    (id, first_name, last_name, section_id).
    The application no longer uses this for student login or the
    teacher dashboard; use get_students_by_section() instead.
    """
    with _db() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT id, first_name, last_name, section_id
            FROM students
            ORDER BY first_name COLLATE NOCASE, last_name COLLATE NOCASE, id
            """
        )
        return cursor.fetchall()


def get_unassigned_students():
    """Legacy students that were created before sections existed."""
    with _db() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT id, first_name, last_name, section_id
            FROM students
            WHERE section_id IS NULL
            ORDER BY first_name COLLATE NOCASE, last_name COLLATE NOCASE, id
            """
        )
        return cursor.fetchall()


def adopt_unassigned_students(section_id, teacher_id):
    """
    Moves every legacy (unassigned) student into one of the teacher's
    sections so their old performance data becomes reachable again.
    Returns how many students were moved.
    """
    with _db() as connection:
        cursor = connection.cursor()
        if not _teacher_owns_section(cursor, teacher_id, section_id):
            raise PermissionError("THIS SECTION BELONGS TO ANOTHER TEACHER")

        cursor.execute(
            "UPDATE students SET section_id = ? WHERE section_id IS NULL",
            (section_id,)
        )
        moved = cursor.rowcount
        connection.commit()
        return moved


def get_student_section(student_id, teacher_id=None):
    """
    Returns {"id", "section_name", "teacher_id"} for the student's section,
    or None when the student is unassigned (or not visible to teacher_id).
    """
    with _db() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT se.id, se.section_name, se.teacher_id
            FROM students st
            JOIN sections se ON se.id = st.section_id
            WHERE st.id = ?
            """,
            (student_id,)
        )
        row = cursor.fetchone()

    if row is None:
        return None
    if teacher_id is not None and row[2] != teacher_id:
        return None
    return {"id": row[0], "section_name": row[1], "teacher_id": row[2]}


def get_section_student_count(section_id):
    with _db() as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM students WHERE section_id = ?", (section_id,))
        return cursor.fetchone()[0]


# =========================================================
# DELETE STUDENT
# =========================================================

def delete_student(student_id, teacher_id=None, section_id=None):
    """
    Deletes a student and all of that student's attempts.
    Returns the number of students deleted (0 or 1).

    teacher_id - when given, the student must be in that teacher's section
                 (otherwise PermissionError)
    section_id - when given, the student must be in that section
                 (used by the student-side screen)
    """
    with _db() as connection:
        cursor = connection.cursor()

        cursor.execute("SELECT section_id FROM students WHERE id = ?", (student_id,))
        row = cursor.fetchone()
        if row is None:
            return 0

        if teacher_id is not None and not _teacher_owns_student(cursor, teacher_id, student_id):
            raise PermissionError("THIS STUDENT BELONGS TO ANOTHER TEACHER")

        if section_id is not None and row[0] != section_id:
            raise PermissionError("THIS STUDENT IS NOT IN THIS SECTION")

        cursor.execute("DELETE FROM attempts WHERE student_id = ?", (student_id,))
        cursor.execute("DELETE FROM students WHERE id = ?", (student_id,))
        connection.commit()
        return cursor.rowcount


# =========================================================
# SAVE GAME ATTEMPT
# =========================================================

def save_attempt(
    student_id,
    game_type,
    question,
    student_answer,
    correct_answer,
    is_correct,
    response_time,
    difficulty_before,
    difficulty_after,
    decision,
    decision_reason,
    session_id=None
):

    connection = connect_db()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO attempts (
            student_id,
            game_type,
            question,
            student_answer,
            correct_answer,
            is_correct,
            response_time,
            difficulty_before,
            difficulty_after,
            decision,
            decision_reason,
            session_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            student_id,
            game_type,
            question,
            student_answer,
            correct_answer,
            int(is_correct),
            response_time,
            difficulty_before,
            difficulty_after,
            decision,
            decision_reason,
            session_id
        )
    )

    connection.commit()
    connection.close()


# =========================================================
# GET STUDENT ATTEMPTS
# =========================================================

def get_student_attempts(student_id):

    connection = connect_db()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            id,
            game_type,
            question,
            student_answer,
            correct_answer,
            is_correct,
            response_time,
            difficulty_before,
            difficulty_after,
            decision,
            decision_reason,
            timestamp
        FROM attempts
        WHERE student_id = ?
        ORDER BY timestamp ASC
        """,
        (student_id,)
    )

    attempts = cursor.fetchall()

    connection.close()

    return attempts


# =========================================================
# GET STUDENT PERFORMANCE SUMMARY
# =========================================================

def get_student_performance(student_id):

    connection = connect_db()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            COUNT(*) AS total_attempts,

            SUM(
                CASE
                    WHEN is_correct = 1 THEN 1
                    ELSE 0
                END
            ) AS correct_answers,

            AVG(response_time) AS average_response_time,

            MAX(difficulty_after) AS highest_difficulty

        FROM attempts

        WHERE student_id = ?
        """,
        (student_id,)
    )

    performance = cursor.fetchone()

    connection.close()

    return performance


# =========================================================
# CENTRALIZED PERFORMANCE STATUS
# (kept identical to the original inline logic used
# throughout main.py: score > 7 -> MASTERED,
# score > 3 -> DEVELOPING, else -> NEEDS SUPPORT)
# =========================================================

def get_performance_status(score, total_questions):
    if score > 7:
        return "MASTERED"
    elif score > 3:
        return "DEVELOPING"
    else:
        return "NEEDS SUPPORT"


# =========================================================
# SECTION / CLASS PERFORMANCE
# Nothing is copied into the sections table: everything is
# calculated live from  section -> students -> attempts.
# =========================================================

def _section_performance(cursor, section_id):
    cursor.execute(
        """
        SELECT
            st.id,
            COUNT(a.id),
            COALESCE(SUM(a.is_correct), 0),
            COALESCE(SUM(a.response_time), 0.0)
        FROM students st
        LEFT JOIN attempts a ON a.student_id = st.id
        WHERE st.section_id = ?
        GROUP BY st.id
        """,
        (section_id,)
    )
    rows = cursor.fetchall()

    student_count = len(rows)
    total_attempts = sum(r[1] for r in rows)
    total_correct = sum(r[2] for r in rows)
    total_time = sum(r[3] for r in rows)

    # per-student accuracy for students that have played at least once
    accuracies = [100.0 * r[2] / r[1] for r in rows if r[1] > 0]

    return {
        "student_count": student_count,
        "students_with_data": len(accuracies),
        "total_attempts": total_attempts,
        "correct_answers": total_correct,
        # all answered questions in the section: correct / total
        "average_accuracy": (100.0 * total_correct / total_attempts) if total_attempts else None,
        # mean of every student's own accuracy (each student counts equally)
        "class_average": (sum(accuracies) / len(accuracies)) if accuracies else None,
        "average_time": (total_time / total_attempts) if total_attempts else None
    }


def get_section_performance(section_id, teacher_id=None):
    """
    Returns a dict with student_count, students_with_data, total_attempts,
    correct_answers, average_accuracy, class_average, average_time.
    accuracy / average values are None when there is no data yet.
    Returns None when teacher_id is given and does not own the section.
    """
    with _db() as connection:
        cursor = connection.cursor()

        if teacher_id is not None and not _teacher_owns_section(cursor, teacher_id, section_id):
            return None

        return _section_performance(cursor, section_id)


def get_teacher_dashboard_data(teacher_id):
    """
    One entry per section owned by the teacher (and nobody else's):
    {"id", "section_name", "created_at", "student_count", "class_average", ...}
    """
    with _db() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT id, section_name, created_at
            FROM sections
            WHERE teacher_id = ?
            ORDER BY section_name COLLATE NOCASE
            """,
            (teacher_id,)
        )
        sections = cursor.fetchall()

        result = []
        for section_id, section_name, created_at in sections:
            entry = {
                "id": section_id,
                "section_name": section_name,
                "created_at": created_at
            }
            entry.update(_section_performance(cursor, section_id))
            result.append(entry)

        return result


# =========================================================
# TEACHER DASHBOARD DATA
# =========================================================
#
# Individual question attempts are stored one row per
# question (as before). To show the teacher per-activity
# "attempts / best score / average time" the rows are
# grouped back into play sessions using session_id (each
# full 10-question playthrough shares one session_id).
# Rows saved before session_id existed (session_id IS NULL)
# are grouped one-row-per-session so no old data is lost.

def get_student_dashboard_summary(student_id, teacher_id=None):
    """
    Returns a dict:
    {
        "GAME_TYPE": [
            {
                "session_id": ...,
                "attempts": <question count in that session>,
                "score": <correct answers in that session>,
                "total_questions": <question count in that session>,
                "average_time": <avg response_time in that session>,
                "status": "MASTERED" / "DEVELOPING" / "NEEDS SUPPORT",
                "last_timestamp": <timestamp of last question>
            },
            ...
        ],
        ...
    }
    Sessions are ordered oldest -> newest per game type.

    When teacher_id is given, an empty dict is returned unless the
    student belongs to one of that teacher's sections.
    """

    connection = connect_db()
    cursor = connection.cursor()

    if teacher_id is not None and not _teacher_owns_student(cursor, teacher_id, student_id):
        connection.close()
        return {}

    cursor.execute(
        """
        SELECT
            game_type,
            session_id,
            id,
            is_correct,
            response_time,
            timestamp
        FROM attempts
        WHERE student_id = ?
        ORDER BY game_type ASC, timestamp ASC, id ASC
        """,
        (student_id,)
    )

    rows = cursor.fetchall()
    connection.close()

    summary = {}

    # Group rows into sessions. A NULL session_id (legacy rows
    # saved before this feature existed) is treated as its own
    # one-row session so nothing is dropped or merged incorrectly.
    sessions = {}
    order = []

    for game_type, session_id, attempt_id, is_correct, response_time, timestamp in rows:
        key = (game_type, session_id if session_id else f"legacy-{attempt_id}")
        if key not in sessions:
            sessions[key] = {
                "game_type": game_type,
                "session_id": session_id,
                "attempts": 0,
                "score": 0,
                "time_sum": 0.0,
                "last_timestamp": timestamp
            }
            order.append(key)

        entry = sessions[key]
        entry["attempts"] += 1
        entry["score"] += int(is_correct)
        entry["time_sum"] += response_time or 0.0
        entry["last_timestamp"] = timestamp

    for key in order:
        entry = sessions[key]
        game_type = entry["game_type"]
        total_questions = entry["attempts"]
        average_time = entry["time_sum"] / entry["attempts"] if entry["attempts"] else 0.0

        summary.setdefault(game_type, []).append({
            "session_id": entry["session_id"],
            "attempts": entry["attempts"],
            "score": entry["score"],
            "total_questions": total_questions,
            "average_time": average_time,
            "status": get_performance_status(entry["score"], total_questions),
            "last_timestamp": entry["last_timestamp"]
        })

    return summary


def get_all_students_dashboard_summary(teacher_id=None):
    """
    Returns {student_id: {"name": ..., "section_id": ..., "summary": ...}}.
    With teacher_id, only students in that teacher's sections are included.
    """
    result = {}

    if teacher_id is None:
        students = get_students()
    else:
        students = []
        for section in get_teacher_sections(teacher_id):
            students.extend(get_students_by_section(section["id"], teacher_id))

    for student_id, first_name, last_name, section_id in students:
        result[student_id] = {
            "name": (first_name + " " + (last_name or "")).strip(),
            "section_id": section_id,
            "summary": get_student_dashboard_summary(student_id, teacher_id)
        }
    return result