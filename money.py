import random
import time
import uuid


# =========================================================
# MONEY GAME
# =========================================================

class MoneyGame:
    """
    Core backend engine for the Money Math Learning Game.

    Modes:
        - total   : Calculate the total cost of two items.
        - change  : Calculate the change received.
        - savings : Calculate total money saved.
        - make    : Build an exact amount using money buttons.

    Adaptive difficulty:
        Level 1 = Easy
        Level 2 = Medium
        Level 3 = Hard

    Difficulty increases after:
        - 2 consecutive correct AND fast answers.

    Difficulty decreases after:
        - 2 consecutive incorrect answers.
    """

    # =====================================================
    # CONFIGURATION
    # =====================================================

    DENOMINATIONS = [1, 5, 10, 20, 50]

    MIN_AMOUNT = 1
    MAX_QUESTION_AMOUNT = 50
    MAX_ANSWER_AMOUNT = 50

    FAST_TIME_THRESHOLD = 5.0

    TOTAL_QUESTIONS = 10

    MIN_DIFFICULTY = 1
    MAX_DIFFICULTY = 3

    CORRECT_STREAK_REQUIRED = 2
    WRONG_STREAK_REQUIRED = 2

    # =====================================================
    # ITEM POOLS
    # =====================================================

    EASY_ITEMS = [
        ("pencil", 5),
        ("eraser", 3),
        ("juice", 10),
        ("candy", 3),
        ("pencil", 5),
        ("juice", 10),
        ("bread", 15),
    ]

    MEDIUM_ITEMS = [
        ("pencil", 7),
        ("ruler", 7),
        ("notebook", 15),
        ("snack", 12),
        ("bread", 15),
        ("toy", 20),
        ("ball", 25),
    ]

    HARD_ITEMS = [
        ("toy", 27),
        ("ball", 27),
        ("toy", 35),
        ("book", 35),
        ("toy", 36),
        ("toy", 40),
        ("ball", 30),
    ]

    # =====================================================
    # INITIALIZATION
    # =====================================================

    def __init__(self, mode: str):

        self.mode = mode.lower().strip()

        self.session_id = str(uuid.uuid4())

        # -------------------------------------------------
        # Game Progress
        # -------------------------------------------------

        self.total_questions = self.TOTAL_QUESTIONS
        self.question_number = 1
        self.score = 0
        self.finished = False

        # -------------------------------------------------
        # Current Question
        # -------------------------------------------------

        self.question = ""
        self.correct_answer = 0
        self.user_answer = 0

        # Stores individual money button selections.
        #
        # Example:
        # [20, 5, 1, 1]
        #
        # = ₱27

        self.selected_money = []

        # -------------------------------------------------
        # Question Metadata
        # -------------------------------------------------

        self.item = ""
        self.item1 = ""
        self.item2 = ""

        self.price = 0
        self.price1 = 0
        self.price2 = 0

        self.money_given = 0
        self.item_price = 0

        self.saving1 = 0
        self.saving2 = 0

        # -------------------------------------------------
        # Timing
        # -------------------------------------------------

        self.start_time = 0.0
        self.answer_time = 0.0
        self.total_time = 0.0

        # -------------------------------------------------
        # Adaptive Difficulty
        # -------------------------------------------------

        self.difficulty = self.MIN_DIFFICULTY

        self.correct_streak = 0
        self.wrong_streak = 0

        # -------------------------------------------------
        # Generate First Question
        # -------------------------------------------------

        self.generate_question()

    # =====================================================
    # QUESTION GENERATION
    # =====================================================

    def generate_question(self):
        """
        Generates a new question based on the current mode
        and adaptive difficulty.
        """

        if self.finished:
            return

        self.selected_money = []
        self.user_answer = 0

        self.start_time = time.time()

        # Reset current question metadata

        self.question = ""
        self.correct_answer = 0

        self.item = ""
        self.item1 = ""
        self.item2 = ""

        self.price = 0
        self.price1 = 0
        self.price2 = 0

        self.money_given = 0
        self.item_price = 0

        self.saving1 = 0
        self.saving2 = 0

        if self.mode == "total":

            self._generate_total_cost_question()

        elif self.mode == "change":

            self._generate_change_question()

        elif self.mode == "savings":

            self._generate_savings_question()

        elif self.mode == "make":

            self._generate_make_amount_question()

        else:

            self.correct_answer = 0
            self.question = "Invalid money game mode selected."

    # =====================================================
    # DIFFICULTY ITEM POOL
    # =====================================================

    def _get_items_for_difficulty(self):
        """
        Returns the item pool for the current difficulty.
        """

        if self.difficulty == 1:
            return self.EASY_ITEMS

        if self.difficulty == 2:
            return self.MEDIUM_ITEMS

        return self.HARD_ITEMS

    # =====================================================
    # TOTAL COST QUESTIONS
    # =====================================================

    def _generate_total_cost_question(self):
        """
        Generates a question asking for the combined cost
        of two items.

        Ensures:
            - Total is not above MAX_QUESTION_AMOUNT.
            - The two items are different when possible.
        """

        items = self._get_items_for_difficulty()

        valid_pairs = []

        for item1, price1 in items:

            for item2, price2 in items:

                if item1 == item2:
                    continue

                if price1 + price2 <= self.MAX_QUESTION_AMOUNT:

                    valid_pairs.append(
                        (item1, price1, item2, price2)
                    )

        # Safety fallback

        if not valid_pairs:

            item1, price1 = random.choice(items)

            valid_second_items = [
                (name, price)
                for name, price in items
                if price1 + price <= self.MAX_QUESTION_AMOUNT
            ]

            if valid_second_items:

                item2, price2 = random.choice(
                    valid_second_items
                )

            else:

                item2, price2 = item1, price1

        else:

            item1, price1, item2, price2 = random.choice(
                valid_pairs
            )

        self.item1 = item1
        self.price1 = price1

        self.item2 = item2
        self.price2 = price2

        self.correct_answer = price1 + price2

        self.question = (
            f"You want to buy a {item1} for ₱{price1} "
            f"and a {item2} for ₱{price2}. "
            f"What is the total cost?"
        )

    # =====================================================
    # CHANGE QUESTIONS
    # =====================================================

    def _generate_change_question(self):
        """
        Generates a question asking how much change
        the player receives.
        """

        items = self._get_items_for_difficulty()

        valid_questions = []

        # Available bills given to cashier.
        # ₱50 is included.

        money_options = [10, 20, 50]

        for item, price in items:

            for money_given in money_options:

                if money_given > price:

                    change = money_given - price

                    if change <= self.MAX_QUESTION_AMOUNT:

                        valid_questions.append(
                            (item, price, money_given)
                        )

        # Safety fallback

        if not valid_questions:

            item, price = random.choice(items)

            money_given = 50

            while money_given <= price:
                money_given += 10

            valid_questions.append(
                (item, price, money_given)
            )

        item, price, money_given = random.choice(
            valid_questions
        )

        self.item = item
        self.price = price
        self.money_given = money_given

        self.correct_answer = money_given - price

        self.question = (
            f"A {item} costs ₱{price}. "
            f"You give the cashier ₱{money_given}. "
            f"How much change will you get?"
        )

    # =====================================================
    # SAVINGS QUESTIONS
    # =====================================================

    def _generate_savings_question(self):
        """
        Generates a savings addition question.
        The answer represents the total amount saved.
        """

        if self.difficulty == 1:

            item, price = random.choice([
                ("pencil", 5),
                ("eraser", 3),
                ("juice", 10),
            ])

            saving_options = [1, 5]

        elif self.difficulty == 2:

            item, price = random.choice([
                ("notebook", 15),
                ("bread", 15),
                ("snack", 15),
                ("toy", 20),
            ])

            saving_options = [5, 10]

        else:

            item, price = random.choice([
                ("toy", 35),
                ("ball", 30),
                ("book", 35),
                ("toy", 40),
            ])

            saving_options = [10, 15, 20]

        # Find valid combinations

        valid_savings = []

        for saving1 in saving_options:

            for saving2 in saving_options:

                saved = saving1 + saving2

                # Saved amount should not exceed item price.

                if saved <= price:

                    valid_savings.append(
                        (saving1, saving2)
                    )

        # Safety fallback

        if not valid_savings:

            saving1 = saving_options[0]
            saving2 = saving_options[0]

        else:

            saving1, saving2 = random.choice(
                valid_savings
            )

        saved = saving1 + saving2

        self.item = item
        self.item_price = price

        self.saving1 = saving1
        self.saving2 = saving2

        self.correct_answer = saved

        self.question = (
            f"You are saving for a {item} that costs ₱{price}. "
            f"You save ₱{saving1} today and ₱{saving2} tomorrow. "
            f"How much have you saved?"
        )

    # =====================================================
    # MAKE AMOUNT QUESTIONS
    # =====================================================

    def _generate_make_amount_question(self):
        """
        Generates a question where the student must build
        an exact amount using money buttons.
        """

        if self.difficulty == 1:

            item, price = random.choice([
                ("pencil", 5),
                ("juice", 10),
            ])

        elif self.difficulty == 2:

            item, price = random.choice([
                ("notebook", 15),
                ("bread", 15),
                ("toy", 20),
                ("ball", 25),
            ])

        else:

            item, price = random.choice([
                ("toy", 27),
                ("ball", 27),
                ("toy", 36),
                ("toy", 40),
                ("book", 35),
            ])

        self.item = item
        self.item_price = price

        self.correct_answer = price

        self.question = (
            f"A {item} costs ₱{price}. "
            f"Use the money buttons to pay exactly ₱{price}."
        )

    # =====================================================
    # MONEY INPUT
    # =====================================================

    def add_money(self, value: int) -> bool:
        """
        Adds a denomination to the player's money tray.

        Accepted denominations:
            ₱1
            ₱5
            ₱10
            ₱20
            ₱50

        Returns:
            True  = accepted
            False = rejected
        """

        if self.finished:
            return False

        if value not in self.DENOMINATIONS:
            return False

        new_total = self.user_answer + value

        if new_total > self.MAX_ANSWER_AMOUNT:
            return False

        self.user_answer = new_total

        self.selected_money.append(value)

        return True

    # =====================================================
    # CLEAR MONEY TRAY
    # =====================================================

    def clear_answer(self):
        """
        Clears all selected money.
        """

        if self.finished:
            return

        self.user_answer = 0
        self.selected_money = []

    # =====================================================
    # ADAPTIVE DIFFICULTY
    # =====================================================

    def update_difficulty(
        self,
        correct: bool,
        answer_time: float
    ):
        """
        Updates difficulty based on student performance.

        Increase:
            2 consecutive correct AND fast answers.

        Decrease:
            2 consecutive incorrect answers.

        A single incorrect answer does not immediately
        reduce difficulty.
        """

        # -------------------------------------------------
        # CORRECT ANSWER
        # -------------------------------------------------

        if correct:

            self.correct_streak += 1
            self.wrong_streak = 0

            if (
                self.correct_streak >=
                self.CORRECT_STREAK_REQUIRED
                and answer_time <=
                self.FAST_TIME_THRESHOLD
            ):

                if self.difficulty < self.MAX_DIFFICULTY:

                    self.difficulty += 1

                # Reset streak after adaptation attempt.

                self.correct_streak = 0

        # -------------------------------------------------
        # WRONG ANSWER
        # -------------------------------------------------

        else:

            self.wrong_streak += 1
            self.correct_streak = 0

            if self.wrong_streak >= self.WRONG_STREAK_REQUIRED:

                if self.difficulty > self.MIN_DIFFICULTY:

                    self.difficulty -= 1

                self.wrong_streak = 0

        # -------------------------------------------------
        # SAFETY BOUNDARY
        # -------------------------------------------------

        self.difficulty = max(
            self.MIN_DIFFICULTY,
            min(
                self.MAX_DIFFICULTY,
                self.difficulty
            )
        )

    # =====================================================
    # SUBMIT ANSWER
    # =====================================================

    def submit_answer(self) -> dict | None:
        """
        Evaluates the player's answer.

        Returns:
            Structured result dictionary.

        Returns None when:
            - Game is finished.
            - No money has been selected.
        """

        if self.finished:
            return None

        if self.user_answer == 0:
            return None

        # -------------------------------------------------
        # Calculate Answer Time
        # -------------------------------------------------

        self.answer_time = time.time() - self.start_time

        self.total_time += self.answer_time

        # -------------------------------------------------
        # Check Answer
        # -------------------------------------------------

        correct = (
            self.user_answer == self.correct_answer
        )

        if correct:
            self.score += 1

        # -------------------------------------------------
        # Save Difficulty Before Adaptation
        # -------------------------------------------------

        answered_difficulty = self.difficulty

        question_text = self.question

        # -------------------------------------------------
        # Update Adaptive Difficulty
        # -------------------------------------------------

        self.update_difficulty(
            correct,
            self.answer_time
        )

        next_difficulty = self.difficulty

        # -------------------------------------------------
        # Determine Adaptation
        # -------------------------------------------------

        if next_difficulty > answered_difficulty:

            adaptation = "INCREASE"
            reason = "Fast and correct answers"

        elif next_difficulty < answered_difficulty:

            adaptation = "DECREASE"
            reason = "Repeated incorrect answers"

        else:

            adaptation = "STAY"

            if correct:

                reason = (
                    "Correct answer; "
                    "continue current level"
                )

            else:

                reason = (
                    "Incorrect answer; "
                    "monitoring performance"
                )

        # -------------------------------------------------
        # Build Result
        # -------------------------------------------------

        result = {

            "session_id":
                self.session_id,

            "correct":
                correct,

            "user_answer":
                self.user_answer,

            "correct_answer":
                self.correct_answer,

            "formatted_user_tray":
                self.render_money_tray(),

            "time":
                round(
                    self.answer_time,
                    2
                ),

            "difficulty":
                answered_difficulty,

            "difficulty_name":
                self._get_difficulty_name_for_level(
                    answered_difficulty
                ),

            "next_difficulty":
                next_difficulty,

            "next_difficulty_name":
                self.get_difficulty_name(),

            "adaptation":
                adaptation,

            "decision_reason":
                reason,

            "question":
                question_text,

            "question_number":
                self.question_number,

            "score":
                self.score,

            "correct_streak":
                self.correct_streak,

            "wrong_streak":
                self.wrong_streak,
        }

        # -------------------------------------------------
        # Advance Question
        # -------------------------------------------------

        self.question_number += 1

        if self.question_number > self.total_questions:

            self.finished = True

        else:

            self.generate_question()

        return result

    # =====================================================
    # MONEY TRAY DISPLAY
    # =====================================================

    def render_money_tray(self) -> str:
        """
        Returns a readable representation of selected money.

        Example:
            ₱20 + ₱5 + ₱1 + ₱1 = ₱27
        """

        if not self.selected_money:

            return "₱0 (Empty Tray)"

        money_values = [
            f"₱{value}"
            for value in self.selected_money
        ]

        coins = " + ".join(money_values)

        return (
            f"{coins} = ₱{self.user_answer}"
        )

    # =====================================================
    # DIFFICULTY NAME
    # =====================================================

    def _get_difficulty_name_for_level(
        self,
        level: int
    ) -> str:

        """
        Returns a difficulty name for a specific level.
        """

        diff_map = {
            1: "Easy",
            2: "Medium",
            3: "Hard"
        }

        return diff_map.get(
            level,
            "Unknown"
        )

    def get_difficulty_name(self) -> str:
        """
        Returns the current difficulty name.
        """

        return self._get_difficulty_name_for_level(
            self.difficulty
        )

    # =====================================================
    # AVERAGE ANSWER TIME
    # =====================================================

    def average_time(self) -> float:
        """
        Returns average answer time for completed questions.
        """

        answered = self.question_number - 1

        if answered <= 0:
            return 0.0

        return round(
            self.total_time / answered,
            2
        )

    # =====================================================
    # STATUS HEADER
    # =====================================================

    def get_status_header(self) -> str:
        """
        Returns a standardized UI status header.
        """

        current_question = min(
            self.question_number,
            self.total_questions
        )

        return (
            f"Question {current_question}/"
            f"{self.total_questions} | "
            f"Score: {self.score} | "
            f"Difficulty: {self.get_difficulty_name()}"
        )

    # =====================================================
    # SESSION SUMMARY
    # =====================================================

    def get_summary(self) -> dict:
        """
        Returns total session performance summary.
        """

        accuracy = (
            self.score / self.total_questions
        ) * 100

        return {

            "session_id":
                self.session_id,

            "mode":
                self.mode,

            "score":
                self.score,

            "total_questions":
                self.total_questions,

            "accuracy_percentage":
                round(
                    accuracy,
                    1
                ),

            "average_time":
                self.average_time(),

            "final_difficulty":
                self.difficulty,

            "difficulty_name":
                self.get_difficulty_name(),

            "finished":
                self.finished
        }