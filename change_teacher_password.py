"""Change (or create) a teacher account.

Usage:  python change_teacher_password.py
The first-run default account is  teacher / teacher123  - change it
before letting students use the machine.
"""
import getpass
import database as db

db.create_tables()
username = input("Teacher username [teacher]: ").strip() or "teacher"
password = getpass.getpass("New password: ")
if len(password) < 4:
    raise SystemExit("Password must be at least 4 characters.")

connection = db.connect_db()
cursor = connection.cursor()
cursor.execute(
    "INSERT INTO teachers (username, password_hash) VALUES (?, ?) "
    "ON CONFLICT(username) DO UPDATE SET password_hash = excluded.password_hash",
    (username, db._hash_password(password)),
)
connection.commit()
connection.close()
print(f"Password saved for '{username}'.")
