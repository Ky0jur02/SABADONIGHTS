import random
import time
import uuid


# =========================================================
# ADAPTIVE DIFFICULTY
# =========================================================

class AdaptiveDifficulty:
    def __init__(self, min_level=1, max_level=5):
        self.min_level = min_level
        self.max_level = max_level
        self.difficulty = min_level
        self.consecutive_correct = 0
        self.consecutive_wrong = 0

    def update(self, correct):
        """
        CURRENT ADAPTIVE LOGIC:

        Correct:
            - Increase difficulty immediately by 1
            - Maximum difficulty is 5

        Wrong:
            - First wrong answer: no decrease
            - 2 consecutive wrong answers: decrease by 1
            - Minimum difficulty is 1
        """

        if correct:
            self.consecutive_correct += 1
            self.consecutive_wrong = 0

            if self.consecutive_correct >= 1:
                if self.difficulty < self.max_level:
                    self.difficulty += 1

                self.consecutive_correct = 0

        else:
            self.consecutive_wrong += 1
            self.consecutive_correct = 0

            if self.consecutive_wrong >= 2:
                if self.difficulty > self.min_level:
                    self.difficulty -= 1

                self.consecutive_wrong = 0

        # Keep difficulty within valid range
        self.difficulty = max(
            self.min_level,
            min(self.difficulty, self.max_level)
        )

    def get_difficulty(self):
        return self.difficulty

    def reset(self):
        self.difficulty = self.min_level
        self.consecutive_correct = 0
        self.consecutive_wrong = 0


# =========================================================
# COUNTING GAME
# =========================================================

class CountingGame:
    def __init__(self):
        self.total_questions = 10
        self.current_question = 0
        self.score = 0

        self.session_id = str(uuid.uuid4())

        self.question = []
        self.correct_answer = 0
        self.user_answer = ""

        self.question_start_time = 0
        self.answer_time = 0
        self.total_time = 0

        self.adaptive = AdaptiveDifficulty(
            min_level=1,
            max_level=5
        )

        self.generate_question()

    # -----------------------------------------------------
    # KEYBOARD INPUT
    # -----------------------------------------------------

    def add_digit(self, digit_str):
        if self.user_answer is None:
            self.user_answer = ""

        self.user_answer = (
            str(self.user_answer) + str(digit_str)
        )

    def remove_digit(self):
        if (
            self.user_answer is not None
            and str(self.user_answer) != ""
        ):
            self.user_answer = str(self.user_answer)[:-1]

    # -----------------------------------------------------
    # GENERATE QUESTION
    # -----------------------------------------------------

    def generate_question(self):
        self.user_answer = ""

        difficulty = self.adaptive.get_difficulty()

        max_number_by_level = {
            1: 10,
            2: 20,
            3: 50,
            4: 75,
            5: 99
        }

        maximum = max_number_by_level[difficulty]

        start_number = random.randint(
            1,
            maximum - 4
        )

        numbers = [
            start_number + i
            for i in range(5)
        ]

        missing_index = random.randint(0, 4)

        self.correct_answer = numbers[missing_index]

        numbers[missing_index] = None

        self.question = numbers

        self.question_start_time = time.time()

    # -----------------------------------------------------
    # QUESTION TEXT
    # -----------------------------------------------------

    def get_question_text(self):
        parts = []

        for number in self.question:
            if number is None:
                parts.append("_")
            else:
                parts.append(str(number))

        return ", ".join(parts)

    # -----------------------------------------------------
    # SUBMIT ANSWER
    # -----------------------------------------------------

    def submit_answer(self):

        # Do not allow empty submission
        if (
            self.user_answer is None
            or str(self.user_answer).strip() == ""
        ):
            return None

        # Save student's raw answer
        student_answer = self.user_answer

        # Record response time
        self.answer_time = (
            time.time() - self.question_start_time
        )

        self.total_time += self.answer_time

        # IMPORTANT:
        # Save the difficulty and correct answer
        # BEFORE generating the next question.
        answered_difficulty = (
            self.adaptive.get_difficulty()
        )

        question_text = self.get_question_text()

        correct_answer = self.correct_answer

        # Validate answer
        try:
            student_answer = int(student_answer)
        except (ValueError, TypeError):
            student_answer = None

        self.user_answer = student_answer

        correct = (
            student_answer is not None
            and student_answer == correct_answer
        )

        # Update score
        if correct:
            self.score += 1

        # Update adaptive difficulty
        self.adaptive.update(correct)

        next_difficulty = (
            self.adaptive.get_difficulty()
        )

        # Determine adaptation
        if next_difficulty > answered_difficulty:
            adaptation = "INCREASE"

        elif next_difficulty < answered_difficulty:
            adaptation = "DECREASE"

        else:
            adaptation = "STAY"

        # Move to next question
        self.current_question += 1

        # Generate next question
        if not self.is_finished():
            self.generate_question()

        # Database-ready result
        return {
            "correct": correct,
            "user_answer": student_answer,
            "correct_answer": correct_answer,
            "time": self.answer_time,
            "difficulty": answered_difficulty,
            "next_difficulty": next_difficulty,
            "adaptation": adaptation,
            "question": question_text,
            "question_number": self.current_question,
            "score": self.score
        }

    # -----------------------------------------------------
    # FINISHED
    # -----------------------------------------------------

    def is_finished(self):
        return self.current_question >= self.total_questions

    # -----------------------------------------------------
    # AVERAGE TIME
    # -----------------------------------------------------

    def get_average_time(self):
        if self.current_question == 0:
            return 0

        return (
            self.total_time / self.current_question
        )

    # -----------------------------------------------------
    # CURRENT DIFFICULTY
    # -----------------------------------------------------

    def get_difficulty(self):
        return self.adaptive.get_difficulty()


# =========================================================
# ADDITION GAME
# =========================================================

class AdditionGame:
    def __init__(self):
        self.total_questions = 10
        self.current_question = 0
        self.score = 0

        self.session_id = str(uuid.uuid4())

        self.num1 = 0
        self.num2 = 0
        self.answer = 0
        self.user_answer = ""

        self.question_start_time = 0
        self.answer_time = 0
        self.total_time = 0

        self.adaptive = AdaptiveDifficulty(
            min_level=1,
            max_level=5
        )

        self.generate_question()

    # -----------------------------------------------------
    # KEYBOARD INPUT
    # -----------------------------------------------------

    def add_digit(self, digit_str):
        if self.user_answer is None:
            self.user_answer = ""

        self.user_answer = (
            str(self.user_answer) + str(digit_str)
        )

    def remove_digit(self):
        if (
            self.user_answer is not None
            and str(self.user_answer) != ""
        ):
            self.user_answer = str(self.user_answer)[:-1]

    # -----------------------------------------------------
    # GENERATE QUESTION
    # -----------------------------------------------------

    def generate_question(self):
        self.user_answer = ""

        difficulty = self.adaptive.get_difficulty()

        max_number_by_level = {
            1: 10,
            2: 15,
            3: 20,
            4: 20,
            5: 20
        }

        maximum = max_number_by_level[difficulty]

        self.num1 = random.randint(
            1,
            maximum - 1
        )

        self.num2 = random.randint(
            1,
            maximum - self.num1
        )

        self.answer = self.num1 + self.num2

        self.question_start_time = time.time()

    # -----------------------------------------------------
    # QUESTION TEXT
    # -----------------------------------------------------

    def get_question_text(self):
        return f"{self.num1} + {self.num2}"

    # -----------------------------------------------------
    # SUBMIT ANSWER
    # -----------------------------------------------------

    def submit_answer(self):

        if (
            self.user_answer is None
            or str(self.user_answer).strip() == ""
        ):
            return None

        student_answer = self.user_answer

        self.answer_time = (
            time.time() - self.question_start_time
        )

        self.total_time += self.answer_time

        # Save current question data BEFORE
        # generating the next question.
        answered_difficulty = (
            self.adaptive.get_difficulty()
        )

        question_text = self.get_question_text()

        correct_answer = self.answer

        # Validate answer
        try:
            student_answer = int(student_answer)
        except (ValueError, TypeError):
            student_answer = None

        self.user_answer = student_answer

        correct = (
            student_answer is not None
            and student_answer == correct_answer
        )

        # Update score
        if correct:
            self.score += 1

        # Adaptive difficulty
        self.adaptive.update(correct)

        next_difficulty = (
            self.adaptive.get_difficulty()
        )

        # Adaptation
        if next_difficulty > answered_difficulty:
            adaptation = "INCREASE"

        elif next_difficulty < answered_difficulty:
            adaptation = "DECREASE"

        else:
            adaptation = "STAY"

        # Move to next question
        self.current_question += 1

        if not self.is_finished():
            self.generate_question()

        # Database-ready result
        return {
            "correct": correct,
            "user_answer": student_answer,
            "correct_answer": correct_answer,
            "time": self.answer_time,
            "difficulty": answered_difficulty,
            "next_difficulty": next_difficulty,
            "adaptation": adaptation,
            "question": question_text,
            "question_number": self.current_question,
            "score": self.score
        }

    # -----------------------------------------------------
    # FINISHED
    # -----------------------------------------------------

    def is_finished(self):
        return self.current_question >= self.total_questions

    # -----------------------------------------------------
    # AVERAGE TIME
    # -----------------------------------------------------

    def get_average_time(self):
        if self.current_question == 0:
            return 0

        return (
            self.total_time / self.current_question
        )

    # -----------------------------------------------------
    # CURRENT DIFFICULTY
    # -----------------------------------------------------

    def get_difficulty(self):
        return self.adaptive.get_difficulty()


# =========================================================
# ADDITION 100 GAME
# =========================================================

class Addition100Game:
    def __init__(self):
        self.total_questions = 10
        self.current_question = 0
        self.score = 0

        self.session_id = str(uuid.uuid4())

        self.num1 = 0
        self.num2 = 0
        self.answer = 0
        self.user_answer = ""

        self.question_start_time = 0
        self.answer_time = 0
        self.total_time = 0

        self.adaptive = AdaptiveDifficulty(
            min_level=1,
            max_level=5
        )

        self.generate_question()

    # -----------------------------------------------------
    # KEYBOARD INPUT
    # -----------------------------------------------------

    def add_digit(self, digit_str):
        if self.user_answer is None:
            self.user_answer = ""

        self.user_answer = (
            str(self.user_answer) + str(digit_str)
        )

    def remove_digit(self):
        if (
            self.user_answer is not None
            and str(self.user_answer) != ""
        ):
            self.user_answer = str(self.user_answer)[:-1]

    # -----------------------------------------------------
    # GENERATE QUESTION
    # -----------------------------------------------------

    def generate_question(self):
        self.user_answer = ""

        difficulty = self.adaptive.get_difficulty()

        max_number_by_level = {
            1: 20,
            2: 40,
            3: 60,
            4: 80,
            5: 99
        }

        maximum = max_number_by_level[difficulty]

        self.num1 = random.randint(
            1,
            maximum - 1
        )

        self.num2 = random.randint(
            1,
            maximum - self.num1
        )

        self.answer = self.num1 + self.num2

        self.question_start_time = time.time()

    # -----------------------------------------------------
    # QUESTION TEXT
    # -----------------------------------------------------

    def get_question_text(self):
        return f"{self.num1} + {self.num2}"

    # -----------------------------------------------------
    # SUBMIT ANSWER
    # -----------------------------------------------------

    def submit_answer(self):

        if (
            self.user_answer is None
            or str(self.user_answer).strip() == ""
        ):
            return None

        student_answer = self.user_answer

        self.answer_time = (
            time.time() - self.question_start_time
        )

        self.total_time += self.answer_time

        # Save current question data
        answered_difficulty = (
            self.adaptive.get_difficulty()
        )

        question_text = self.get_question_text()

        correct_answer = self.answer

        # Validate answer
        try:
            student_answer = int(student_answer)
        except (ValueError, TypeError):
            student_answer = None

        self.user_answer = student_answer

        correct = (
            student_answer is not None
            and student_answer == correct_answer
        )

        # Score
        if correct:
            self.score += 1

        # Adaptive difficulty
        self.adaptive.update(correct)

        next_difficulty = (
            self.adaptive.get_difficulty()
        )

        # Adaptation
        if next_difficulty > answered_difficulty:
            adaptation = "INCREASE"

        elif next_difficulty < answered_difficulty:
            adaptation = "DECREASE"

        else:
            adaptation = "STAY"

        # Next question
        self.current_question += 1

        if not self.is_finished():
            self.generate_question()

        # Database-ready result
        return {
            "correct": correct,
            "user_answer": student_answer,
            "correct_answer": correct_answer,
            "time": self.answer_time,
            "difficulty": answered_difficulty,
            "next_difficulty": next_difficulty,
            "adaptation": adaptation,
            "question": question_text,
            "question_number": self.current_question,
            "score": self.score
        }

    # -----------------------------------------------------
    # FINISHED
    # -----------------------------------------------------

    def is_finished(self):
        return self.current_question >= self.total_questions

    # -----------------------------------------------------
    # AVERAGE TIME
    # -----------------------------------------------------

    def get_average_time(self):
        if self.current_question == 0:
            return 0

        return (
            self.total_time / self.current_question
        )

    # -----------------------------------------------------
    # CURRENT DIFFICULTY
    # -----------------------------------------------------

    def get_difficulty(self):
        return self.adaptive.get_difficulty()


# =========================================================
# SUBTRACTION 100 GAME
# =========================================================

class Subtraction100Game:
    def __init__(self):
        self.total_questions = 10
        self.current_question = 0
        self.score = 0

        self.session_id = str(uuid.uuid4())

        self.num1 = 0
        self.num2 = 0
        self.answer = 0
        self.user_answer = ""

        self.question_start_time = 0
        self.answer_time = 0
        self.total_time = 0

        self.adaptive = AdaptiveDifficulty(
            min_level=1,
            max_level=5
        )

        self.generate_question()

    # -----------------------------------------------------
    # KEYBOARD INPUT
    # -----------------------------------------------------

    def add_digit(self, digit_str):
        if self.user_answer is None:
            self.user_answer = ""

        self.user_answer = (
            str(self.user_answer) + str(digit_str)
        )

    def remove_digit(self):
        if (
            self.user_answer is not None
            and str(self.user_answer) != ""
        ):
            self.user_answer = str(self.user_answer)[:-1]

    # -----------------------------------------------------
    # GENERATE QUESTION
    # -----------------------------------------------------

    def generate_question(self):
        self.user_answer = ""

        difficulty = self.adaptive.get_difficulty()

        max_number_by_level = {
            1: 20,
            2: 40,
            3: 60,
            4: 80,
            5: 99
        }

        maximum = max_number_by_level[difficulty]

        self.num1 = random.randint(
            1,
            maximum
        )

        # num2 is never greater than num1,
        # so negative answers are avoided.
        self.num2 = random.randint(
            1,
            self.num1
        )

        self.answer = self.num1 - self.num2

        self.question_start_time = time.time()

    # -----------------------------------------------------
    # QUESTION TEXT
    # -----------------------------------------------------

    def get_question_text(self):
        return f"{self.num1} - {self.num2}"

    # -----------------------------------------------------
    # SUBMIT ANSWER
    # -----------------------------------------------------

    def submit_answer(self):

        if (
            self.user_answer is None
            or str(self.user_answer).strip() == ""
        ):
            return None

        student_answer = self.user_answer

        self.answer_time = (
            time.time() - self.question_start_time
        )

        self.total_time += self.answer_time

        # Save current question data
        answered_difficulty = (
            self.adaptive.get_difficulty()
        )

        question_text = self.get_question_text()

        correct_answer = self.answer

        # Validate answer
        try:
            student_answer = int(student_answer)
        except (ValueError, TypeError):
            student_answer = None

        self.user_answer = student_answer

        correct = (
            student_answer is not None
            and student_answer == correct_answer
        )

        # Score
        if correct:
            self.score += 1

        # Adaptive difficulty
        self.adaptive.update(correct)

        next_difficulty = (
            self.adaptive.get_difficulty()
        )

        # Adaptation
        if next_difficulty > answered_difficulty:
            adaptation = "INCREASE"

        elif next_difficulty < answered_difficulty:
            adaptation = "DECREASE"

        else:
            adaptation = "STAY"

        # Next question
        self.current_question += 1

        if not self.is_finished():
            self.generate_question()

        # Database-ready result
        return {
            "correct": correct,
            "user_answer": student_answer,
            "correct_answer": correct_answer,
            "time": self.answer_time,
            "difficulty": answered_difficulty,
            "next_difficulty": next_difficulty,
            "adaptation": adaptation,
            "question": question_text,
            "question_number": self.current_question,
            "score": self.score
        }

    # -----------------------------------------------------
    # FINISHED
    # -----------------------------------------------------

    def is_finished(self):
        return self.current_question >= self.total_questions

    # -----------------------------------------------------
    # AVERAGE TIME
    # -----------------------------------------------------

    def get_average_time(self):
        if self.current_question == 0:
            return 0

        return (
            self.total_time / self.current_question
        )

    # -----------------------------------------------------
    # CURRENT DIFFICULTY
    # -----------------------------------------------------

    def get_difficulty(self):
        return self.adaptive.get_difficulty()