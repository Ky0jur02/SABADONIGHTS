from database import (
    create_tables,
    add_student,
    get_students,
    save_attempt,
    get_student_attempts,
    get_student_performance
)


# Create database tables
create_tables()

print("Database tables created.")


# ---------------------------------------------------------
# ADD TEST STUDENT
# ---------------------------------------------------------

add_student("Test Student")

students = get_students()

print("\nStudents:")
print(students)


# Get the first student's ID
student_id = students[-1][0]


# ---------------------------------------------------------
# SAVE TEST ATTEMPT
# ---------------------------------------------------------

save_attempt(
    student_id=student_id,
    game_type="Addition",
    question="7 + 5",
    student_answer=12,
    correct_answer=12,
    is_correct=True,
    response_time=2.4,
    difficulty_before=1,
    difficulty_after=2,
    decision="INCREASE",
    decision_reason="1 consecutive correct answer"
)

print("\nAttempt saved successfully!")


# ---------------------------------------------------------
# DISPLAY ATTEMPTS
# ---------------------------------------------------------

attempts = get_student_attempts(student_id)

print("\nStudent Attempts:")

for attempt in attempts:
    print(attempt)


# ---------------------------------------------------------
# DISPLAY PERFORMANCE
# ---------------------------------------------------------

performance = get_student_performance(student_id)

print("\nPerformance Summary:")
print(performance)