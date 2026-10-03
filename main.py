import pygame
import sys
import math
import serial

import database as db
from database import (
    create_tables,
    add_student,
    delete_student,
    save_attempt,
    verify_teacher,
    get_student_dashboard_summary,
    get_performance_status,
    # --- section architecture ---
    create_section,
    get_teacher_sections,
    get_section,
    get_students_by_section,
    get_student_section,
    get_section_student_count,
    get_section_performance,
)

from games.number_block import (
    CountingGame,
    AdditionGame,
    Addition100Game,
    Subtraction100Game
)

from games.money import MoneyGame


# =========================================================
# INITIALIZATION
# =========================================================

pygame.init()

SCREEN_WIDTH = 1024
SCREEN_HEIGHT = 600

screen = pygame.display.set_mode(
    (SCREEN_WIDTH, SCREEN_HEIGHT)
)

pygame.display.set_caption(
    "Capstone 2 - Mathematics Learning System"
)

clock = pygame.time.Clock()

animation_time = 0.0

WORLD_TRANSITION_SECONDS = 0.45
last_world = "HOME"
world_transition_start = -10.0
fade_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))


# =========================================================
# COLORS
# =========================================================

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
BLUE = (50, 100, 200)
LIGHT_BLUE = (220, 235, 255)
GRAY = (180, 180, 180)
GREEN = (70, 160, 90)
RED = (200, 70, 70)
YELLOW = (240, 210, 70)


# =========================================================
# FONTS
# =========================================================

title_font = pygame.font.SysFont("arial", 56, bold=True)
large_font = pygame.font.SysFont("arial", 64, bold=True)
button_font = pygame.font.SysFont("arial", 38, bold=True)
small_font = pygame.font.SysFont("arial", 28, bold=True)
input_font = pygame.font.SysFont("arial", 42, bold=True)

PLAYFUL_FONT_STACK = "comicsansms,trebuchetms,verdana,arial"

font_world_title = pygame.font.SysFont(PLAYFUL_FONT_STACK, 52, bold=True)
font_topic_title = pygame.font.SysFont(PLAYFUL_FONT_STACK, 34, bold=True)
font_ui_button = pygame.font.SysFont(PLAYFUL_FONT_STACK, 30, bold=True)
font_instruction = pygame.font.SysFont(PLAYFUL_FONT_STACK, 20, bold=True)
font_hint = pygame.font.SysFont(PLAYFUL_FONT_STACK, 16, bold=True)
font_score_big = pygame.font.SysFont(PLAYFUL_FONT_STACK, 46, bold=True)
font_dashboard = pygame.font.SysFont(PLAYFUL_FONT_STACK, 22, bold=True)
font_dashboard_small = pygame.font.SysFont(PLAYFUL_FONT_STACK, 16, bold=True)

# Large playful fonts for the math question / answer (same family as above)
font_question_big = pygame.font.SysFont(PLAYFUL_FONT_STACK, 64, bold=True)
font_question_mid = pygame.font.SysFont(PLAYFUL_FONT_STACK, 50, bold=True)
font_answer_big = pygame.font.SysFont(PLAYFUL_FONT_STACK, 52, bold=True)

# Arial has arrow glyphs (used for the "<- BACK" buttons) and the bullet character
font_back = pygame.font.SysFont("arial", 18, bold=True)
font_key_small = pygame.font.Font(None, 24)

# Some playful fonts have no peso sign. Fall back to Arial for text with it.
_PESO_FONT_CACHE = {}
_PLAYFUL_SIZES = {}
for _f, _sz in ((font_world_title, 52), (font_topic_title, 34), (font_ui_button, 30),
                (font_instruction, 20), (font_hint, 16), (font_score_big, 46),
                (font_dashboard, 22), (font_dashboard_small, 16),
                (font_question_big, 64), (font_question_mid, 50), (font_answer_big, 52)):
    _PLAYFUL_SIZES[id(_f)] = _sz


def peso_safe(font):
    """Return font itself if it can draw the peso sign, else an Arial twin."""
    key = id(font)
    if key not in _PESO_FONT_CACHE:
        try:
            ok = font.metrics("\u20b1")[0] is not None
        except Exception:
            ok = False
        if ok:
            _PESO_FONT_CACHE[key] = font
        else:
            size = _PLAYFUL_SIZES.get(key, 24)
            _PESO_FONT_CACHE[key] = pygame.font.SysFont("arial", size, bold=True)
    return _PESO_FONT_CACHE[key]

# Icon font stack supporting emojis
ICON_FONT_STACK = "segoeuiemoji,applecoloremoji,notocoloremoji,arial"
font_icon_large = pygame.font.SysFont(ICON_FONT_STACK, 54)
font_icon_small = pygame.font.SysFont(ICON_FONT_STACK, 32)


# =========================================================
# IMAGES
# =========================================================

COIN_SIZE = (35, 35)

try:
    coin_images = {
        1: pygame.transform.scale(pygame.image.load("1_peso.png"), COIN_SIZE),
        5: pygame.transform.scale(pygame.image.load("5_peso.png"), COIN_SIZE),
        10: pygame.transform.scale(pygame.image.load("10_peso.png"), COIN_SIZE),
        20: pygame.transform.scale(pygame.image.load("20_peso.png"), COIN_SIZE)
    }
except FileNotFoundError:
    print("WARNING: Coin images not found! Please add 1_peso.png, 5_peso.png, 10_peso.png, 20_peso.png")
    coin_images = {}


# =========================================================
# DATABASE
# =========================================================

create_tables()


# =========================================================
# DATABASE ROW HELPERS
# (thin adapters so main.py works whether database.py returns
#  tuples, sqlite3.Row objects or dicts)
# =========================================================

def _field(row, names, idx=None, default=None):
    """Read a value from a dict / sqlite3.Row by name, or from a tuple by index."""
    if row is None:
        return default
    if hasattr(row, "keys"):
        try:
            keys = list(row.keys())
        except Exception:
            keys = []
        for n in names:
            if n in keys:
                return row[n]
        return default
    if idx is not None and isinstance(row, (tuple, list)) and idx < len(row):
        return row[idx]
    return default


def norm_student(row):
    """-> (student_id, "First Last", first_name, last_name)"""
    sid = _field(row, ["id", "student_id"], 0)
    first = _field(row, ["first_name", "name"], 1, "") or ""
    last = _field(row, ["last_name"], 2, "") or ""
    if not isinstance(last, str):      # legacy (id, name, ...) rows
        last = ""
    display = (str(first) + " " + last).strip()
    return (sid, display, str(first), last)


def norm_section(row):
    """-> (section_id, section_name, teacher_id)"""
    return (
        _field(row, ["id", "section_id"], 0),
        str(_field(row, ["section_name", "name"], 1, "") or ""),
        _field(row, ["teacher_id"], 2),
    )


def section_title(name):
    return "GRADE 1 - " + str(name).upper()


SECTION_ICONS = ["\U0001F338", "\U0001F339", "\U0001F33B", "\U0001F337", "\U0001F33A", "\U0001F33C"]


def section_icon(section_id):
    try:
        return SECTION_ICONS[int(section_id) % len(SECTION_ICONS)]
    except (TypeError, ValueError):
        return SECTION_ICONS[0]


def resolve_teacher_id(result, username):
    """verify_teacher may return the teacher id, a row, or just True."""
    if result is None or result is False:
        return None
    if isinstance(result, bool):
        for fn_name in ("get_teacher_id", "get_teacher_id_by_username"):
            fn = getattr(db, fn_name, None)
            if fn:
                try:
                    return fn(username)
                except Exception:
                    pass
        print("WARNING: verify_teacher returned only True - assuming teacher id 1.")
        return 1
    if isinstance(result, int):
        return result
    return _field(result, ["id", "teacher_id"], 0)


def section_stats(section_id):
    """Return (student_count, class_average_or_None, total_attempts)."""
    try:
        count = int(get_section_student_count(section_id) or 0)
    except Exception as e:
        print("Section count error:", e)
        count = 0

    average, attempts = None, None
    try:
        perf = get_section_performance(section_id)
        if isinstance(perf, (int, float)) and not isinstance(perf, bool):
            average = float(perf)
        else:
            average = _field(perf, ["class_average", "average_accuracy", "accuracy", "average"], None)
            attempts = _field(perf, ["total_attempts", "attempts"], None)
    except Exception as e:
        print("Section performance error:", e)

    if attempts is not None and attempts == 0:
        average = None
    if average is not None:
        average = float(average)
    return count, average, (attempts or 0)


# =========================================================
# SCREEN STATES
# =========================================================

HOME = "home"

SECTION_SELECTION = "section_selection"
STUDENT_SELECTION = "student_selection"
REGISTER_STUDENT = "register_student"
DELETE_STUDENT = "delete_student"
VIRTUAL_KEYBOARD = "virtual_keyboard"
CURRENT_PLAYER = "current_player"

GAME_SELECTION = "game_selection"
NUMBER_BLOCK_TOPICS = "number_block_topics"
MONEY_TOPICS = "money_topics"

MONEY_TOTAL_GAME = "money_total_game"
MONEY_CHANGE_GAME = "money_change_game"
MONEY_SAVINGS_GAME = "money_savings_game"
MONEY_MAKE_GAME = "money_make_game"
MONEY_RESULT = "money_result"

CLOCK_GAME = "clock_game"
PIZZA_FRACTION_GAME = "pizza_fraction_game"
MIXED_QUICKSTART = "mixed_quickstart"

TEACHER_LOGIN = "teacher_login"
TEACHER_DASHBOARD = "teacher_dashboard"
TEACHER_CREATE_SECTION = "teacher_create_section"
TEACHER_SECTION = "teacher_section"
TEACHER_ADD_STUDENT = "teacher_add_student"
TEACHER_STUDENT_DETAIL = "teacher_student_detail"

COUNTING_GAME = "counting_game"
COUNTING_RESULT = "counting_result"

ADDITION_GAME = "addition_game"
ADDITION_RESULT = "addition_result"

ADDITION100_GAME = "addition100_game"
ADDITION100_RESULT = "addition100_result"

SUBTRACTION100_GAME = "subtraction100_game"
SUBTRACTION100_RESULT = "subtraction100_result"

current_screen = HOME

home_menu_options = ["LOGIN", "TEACHER DASHBOARD"]
selected_home_option = 0

# ---------------- teacher login ----------------

TEACHER_USERNAME_DEFAULT = "teacher"

teacher_username_input = TEACHER_USERNAME_DEFAULT
teacher_password_input = ""
teacher_login_field = 1          # 0 = username, 1 = password, 2 = LOGIN button
teacher_login_error = ""
teacher_logged_in = False
teacher_id = None

# ---------------- teacher dashboard (sections) ----------------

teacher_sections = []            # list of dicts: id, name, count, average, attempts
teacher_dash_sel = 0             # 0 = "+ CREATE NEW SECTION", 1.. = sections
teacher_dash_scroll = 0

# ---------------- create section ----------------

create_section_name = ""
create_section_focus = 0         # 0 = name field, 1 = CREATE, 2 = CANCEL
create_section_error = ""

# ---------------- teacher section view ----------------

teacher_section_id = None
teacher_section_name = ""
teacher_section_students = []
section_sel = 0                  # 0 = "+ ADD STUDENT", 1.. = students
section_scroll = 0
section_delete_focus = False
section_confirm = None           # (student_id, display_name) while the confirm box is open
section_confirm_yes = False

# ---------------- add / register student form (shared) ----------------

form_kind = "TEACHER"            # "TEACHER" (add to teacher's section) or "STUDENT" (student-side register)
form_first = ""
form_last = ""
form_focus = 0                   # 0 first, 1 last, 2 ADD, 3 CANCEL
form_error = ""
form_section_id = None
form_section_name = ""

# ---------------- teacher student detail ----------------

dashboard_detail_student_id = None
dashboard_detail_student_name = ""
dashboard_detail_section_name = ""
dashboard_detail_rows = []
dashboard_detail_selected = 0
dashboard_detail_scroll = 0
dashboard_detail_summary = {}
dashboard_detail_view = "SUMMARY"
dashboard_detail_activity = None
dashboard_detail_topics = ["ALL"]
dashboard_detail_filter = 0

# Rebuilt every frame by the draw functions; used for mouse / touch clicks
dashboard_click_targets = []


# =========================================================
# STUDENTS / STUDENT-SIDE SECTION SELECTION
# =========================================================

login_sections = []              # list of dicts: id, name, count
selected_section_option = 0
section_select_scroll = 0

current_section_id = None
current_section_name = ""

students = []                    # normalized tuples: (id, "First Last", first, last)

selected_student_option = 0
student_scroll_offset = 0        # first visible ROW of the student card grid

current_player = None
current_player_id = None

delete_student_index = 0
delete_scroll_offset = 0


# =========================================================
# VIRTUAL KEYBOARD (reusable for every text field)
# =========================================================

keyboard_rows = [
    ["A", "B", "C", "D", "E", "F", "G"],
    ["H", "I", "J", "K", "L", "M", "N"],
    ["O", "P", "Q", "R", "S", "T", "U"],
    ["V", "W", "X", "Y", "Z", "SPACE", "BACKSPACE"],
    ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"],
    ["CLEAR", "aA", "DONE"]
]

SPECIAL_KEYS = ("SPACE", "BACKSPACE", "CLEAR", "DONE")

keyboard_row = 0
keyboard_col = 0

keyboard_value = ""
keyboard_title = "VIRTUAL KEYBOARD"
keyboard_password = False        # PASSWORD MODE: show bullets instead of characters
keyboard_lower = False           # aA toggle
keyboard_max_len = 30
keyboard_callback = None         # called with the final text when DONE is pressed
keyboard_return_screen = HOME


# =========================================================
# GAME MODULES DATA
# =========================================================

game_cards_data = [
    {"name": "NUMBER BLOCK", "icon": "🔢"},
    {"name": "MONEY", "icon": "₱"},
    {"name": "CLOCK", "icon": "🕐"},
    {"name": "PIZZA FRACTION", "icon": "🍕"},
    {"name": "MIXED QUICKSTART", "icon": "⚡"}
]

game_modules = [item["name"] for item in game_cards_data]

selected_game = 0
selected_game_name = ""


# =========================================================
# NUMBER BLOCK TOPICS DATA
# =========================================================

number_block_topics_data = [
    {"title": "COUNTING", "subtitle": "Fill in the blanks", "icon": "🔢"},
    {"title": "ADDITION", "subtitle": "Up to 20", "icon": "➕"},
    {"title": "ADDITION", "subtitle": "Up to 100", "icon": "➕"},
    {"title": "SUBTRACTION", "subtitle": "Up to 100", "icon": "➖"}
]

number_block_topics = [t["title"] + " - " + t["subtitle"] for t in number_block_topics_data]

selected_number_topic = 0


# =========================================================
# MONEY TOPICS DATA
# =========================================================

money_topics_data = [
    {"title": "TOTAL SPENT", "subtitle": "Find the total amount", "icon": "🛒"},
    {"title": "CHANGE", "subtitle": "Calculate change left", "icon": "🪙"},
    {"title": "SAVINGS", "subtitle": "Calculate total savings", "icon": "🐷"},
    {"title": "EXACT AMOUNT", "subtitle": "Make the exact amount", "icon": "💵"}
]

money_topics = [t["title"] + " - " + t["subtitle"] for t in money_topics_data]

selected_money_topic = 0


# =========================================================
# GAME VARIABLES
# =========================================================

counting_game = None
counting_result_message = ""

addition_game = None
addition100_game = None
subtraction100_game = None

money_game = None


# =========================================================
# TEXT FUNCTIONS
# =========================================================

def draw_text(text, font, color, x, y, center=True):
    surface = font.render(str(text), True, color)
    if center:
        rect = surface.get_rect(center=(x, y))
    else:
        rect = surface.get_rect(topleft=(x, y))
    screen.blit(surface, rect)


def draw_multiline_text(text, font, color, center_x, start_y, max_width):
    words = text.split(' ')
    lines = []
    current_line = []
    
    for word in words:
        test_line = ' '.join(current_line + [word])
        width, _ = font.size(test_line)
        if width <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(' '.join(current_line))
            current_line = [word]
            
    if current_line:
        lines.append(' '.join(current_line))
        
    y = start_y
    line_spacing = font.get_linesize()
    
    for line in lines:
        draw_text(line, font, color, center_x, y, center=True)
        y += line_spacing


# =========================================================
# WORLD THEMES
# =========================================================

WORLD_THEMES = {
    "HOME": {
        "title": "OVERWORLD",
        "sky_top": (140, 205, 255),
        "sky_bottom": (200, 232, 255),
        "ground": (90, 170, 95),
        "ground_dark": (70, 145, 78),
        "accent": (40, 110, 60),
        "button": (120, 200, 120),
        "button_selected": (255, 221, 89),
        "border": (40, 110, 60),
        "text_on_button": BLACK,
        "particle": "clouds"
    },
    "NUMBER BLOCK": {
        "title": "BLOCK FOREST",
        "sky_top": (150, 210, 255),
        "sky_bottom": (205, 235, 255),
        "ground": (100, 175, 100),
        "ground_dark": (78, 150, 82),
        "accent": (34, 120, 60),
        "button": (255, 196, 90),
        "button_selected": (255, 221, 89),
        "border": (34, 120, 60),
        "text_on_button": BLACK,
        "particle": "clouds"
    },
    "MONEY": {
        "title": "TREASURE REEF",
        "sky_top": (10, 70, 130),
        "sky_bottom": (25, 120, 175),
        "ground": (30, 90, 140),
        "ground_dark": (20, 70, 115),
        "accent": (255, 205, 70),
        "button": (60, 150, 200),
        "button_selected": (255, 205, 70),
        "border": (255, 205, 70),
        "text_on_button": WHITE,
        "particle": "bubbles"
    },
    "CLOCK": {
        "title": "FROZEN KINGDOM",
        "sky_top": (190, 225, 245),
        "sky_bottom": (225, 240, 250),
        "ground": (210, 232, 245),
        "ground_dark": (175, 210, 232),
        "accent": (40, 110, 160),
        "button": (150, 210, 235),
        "button_selected": (255, 255, 255),
        "border": (40, 110, 160),
        "text_on_button": BLACK,
        "particle": "snow"
    },
    "PIZZA FRACTION": {
        "title": "MAGMA CAVERNS",
        "sky_top": (40, 15, 15),
        "sky_bottom": (70, 25, 20),
        "ground": (55, 30, 25),
        "ground_dark": (35, 18, 15),
        "accent": (255, 140, 40),
        "button": (200, 80, 40),
        "button_selected": (255, 150, 50),
        "border": (255, 140, 40),
        "text_on_button": WHITE,
        "particle": "embers"
    },
    "MIXED QUICKSTART": {
        "title": "GALAXY GATE",
        "sky_top": (10, 10, 35),
        "sky_bottom": (30, 20, 60),
        "ground": (25, 20, 50),
        "ground_dark": (15, 12, 35),
        "accent": (170, 140, 255),
        "button": (90, 70, 160),
        "button_selected": (170, 140, 255),
        "border": (170, 140, 255),
        "text_on_button": WHITE,
        "particle": "stars"
    },
    "TEACHER": {
        "title": "TEACHER DASHBOARD",
        "sky_top": (235, 238, 245),
        "sky_bottom": (245, 247, 250),
        "ground": (225, 229, 238),
        "ground_dark": (210, 215, 226),
        "accent": (55, 70, 110),
        "button": (225, 230, 240),
        "button_selected": (60, 110, 200),
        "border": (55, 70, 110),
        "text_on_button": BLACK,
        "particle": "none"
    },
}

STATUS_COLORS = {
    "MASTERED": (60, 160, 90),
    "DEVELOPING": (235, 165, 45),
    "NEEDS SUPPORT": (210, 70, 70)
}


def get_world_for_screen(screen_name):
    if screen_name in (
        NUMBER_BLOCK_TOPICS, COUNTING_GAME, COUNTING_RESULT,
        ADDITION_GAME, ADDITION_RESULT, ADDITION100_GAME, ADDITION100_RESULT,
        SUBTRACTION100_GAME, SUBTRACTION100_RESULT
    ):
        return "NUMBER BLOCK"
    if screen_name in (
        MONEY_TOPICS, MONEY_TOTAL_GAME, MONEY_CHANGE_GAME,
        MONEY_SAVINGS_GAME, MONEY_MAKE_GAME, MONEY_RESULT
    ):
        return "MONEY"
    if screen_name == CLOCK_GAME:
        return "CLOCK"
    if screen_name == PIZZA_FRACTION_GAME:
        return "PIZZA FRACTION"
    if screen_name == MIXED_QUICKSTART:
        return "MIXED QUICKSTART"
    if screen_name in (TEACHER_LOGIN, TEACHER_DASHBOARD, TEACHER_CREATE_SECTION,
                       TEACHER_SECTION, TEACHER_ADD_STUDENT, TEACHER_STUDENT_DETAIL):
        return "TEACHER"
    return "HOME"


# =========================================================
# WORLD BACKGROUND / PARTICLES
# =========================================================

def draw_world_background(theme_key):
    theme = WORLD_THEMES[theme_key]

    band_count = 6
    band_height = (SCREEN_HEIGHT * 2 // 3) // band_count
    top = theme["sky_top"]
    bottom = theme["sky_bottom"]
    for i in range(band_count):
        ratio = i / max(1, band_count - 1)
        color = (
            int(top[0] + (bottom[0] - top[0]) * ratio),
            int(top[1] + (bottom[1] - top[1]) * ratio),
            int(top[2] + (bottom[2] - top[2]) * ratio),
        )
        pygame.draw.rect(screen, color, (0, i * band_height, SCREEN_WIDTH, band_height + 1))

    ground_y = SCREEN_HEIGHT * 2 // 3
    pygame.draw.rect(screen, theme["ground"], (0, ground_y, SCREEN_WIDTH, SCREEN_HEIGHT - ground_y))
    pygame.draw.rect(screen, theme["ground_dark"], (0, ground_y, SCREEN_WIDTH, 10))

    particle_kind = theme["particle"]
    if particle_kind == "clouds":
        for i in range(3):
            hx = 90 + i * 260
            hy = ground_y - 10
            pygame.draw.polygon(screen, theme["ground_dark"], [
                (hx - 70, ground_y), (hx, hy - 55), (hx + 70, ground_y)
            ])
        for i in range(4):
            tx = 50 + i * 240
            pygame.draw.rect(screen, (110, 75, 50), (tx - 6, ground_y - 40, 12, 40))
            pygame.draw.circle(screen, (55, 140, 70), (tx, ground_y - 55), 30)
    elif particle_kind == "bubbles":
        for i in range(5):
            cx = 60 + i * 200
            pygame.draw.ellipse(screen, (20, 60, 50), (cx - 40, ground_y - 20, 90, 35))
        chest_x = SCREEN_WIDTH // 2
        pygame.draw.rect(screen, (120, 80, 40), (chest_x - 45, ground_y - 35, 90, 35), border_radius=6)
        pygame.draw.rect(screen, theme["accent"], (chest_x - 45, ground_y - 35, 90, 35), 3, border_radius=6)
    elif particle_kind == "snow":
        for i in range(4):
            hx = 70 + i * 250
            pygame.draw.polygon(screen, (225, 240, 250), [
                (hx - 60, ground_y), (hx, ground_y - 90), (hx + 60, ground_y)
            ])
            pygame.draw.polygon(screen, WHITE, [
                (hx - 20, ground_y - 55), (hx, ground_y - 90), (hx + 20, ground_y - 55)
            ])
    elif particle_kind == "embers":
        for i in range(4):
            hx = 80 + i * 250
            pygame.draw.polygon(screen, (30, 15, 12), [
                (hx - 65, ground_y), (hx, ground_y - 70), (hx + 65, ground_y)
            ])
        glow_rect = pygame.Rect(0, ground_y - 6, SCREEN_WIDTH, 14)
        pygame.draw.rect(screen, (255, 120, 30), glow_rect)
    elif particle_kind == "stars":
        pygame.draw.circle(screen, (180, 150, 255), (SCREEN_WIDTH // 2, ground_y - 40), 55)
        pygame.draw.circle(screen, theme["sky_bottom"], (SCREEN_WIDTH // 2, ground_y - 40), 40)


def draw_world_particles(theme_key, t):
    theme = WORLD_THEMES[theme_key]
    kind = theme["particle"]
    ground_y = SCREEN_HEIGHT * 2 // 3

    draw_world_decor(theme_key, t)

    if kind == "clouds":
        for i in range(3):
            x = (i * 300 + int(t * 12)) % (SCREEN_WIDTH + 160) - 80
            y = 60 + i * 45
            for dx, dy, r in [(-25, 6, 18), (0, -8, 24), (25, 6, 18), (45, 8, 14)]:
                pygame.draw.circle(screen, WHITE, (int(x + dx), int(y + dy)), r)
    elif kind == "bubbles":
        for i in range(8):
            seed = i * 37
            x = 40 + (seed * 53) % (SCREEN_WIDTH - 80)
            y = ground_y - ((int(t * 40) + seed * 17) % (ground_y - 20))
            r = 4 + (seed % 4)
            pygame.draw.circle(screen, (210, 240, 255), (x, y), r, 1)
    elif kind == "snow":
        for i in range(24):
            seed = i * 53
            x = (seed * 7) % SCREEN_WIDTH
            y = int((t * 60 + seed * 4) % (ground_y + 20))
            pygame.draw.circle(screen, WHITE, (x, y), 2)
    elif kind == "embers":
        for i in range(14):
            seed = i * 41
            x = (seed * 5) % SCREEN_WIDTH
            y = ground_y - int((t * 55 + seed * 6) % ground_y)
            pygame.draw.circle(screen, (255, 170, 60), (x, y), 2)
    elif kind == "stars":
        for i in range(30):
            seed = i * 91
            x = (seed * 7) % SCREEN_WIDTH
            y = (seed * 13) % ground_y
            twinkle = 1 if (int(t * 2) + i) % 3 else 2
            pygame.draw.circle(screen, WHITE, (x, y), twinkle)


def draw_world_decor(theme_key, t):
    ground_y = SCREEN_HEIGHT * 2 // 3
    bob = lambda speed, amp, phase=0.0: int(math.sin(t * speed + phase) * amp)

    if theme_key == "NUMBER BLOCK":
        colors = [(255, 120, 90), (90, 170, 255), (255, 210, 80), (120, 210, 120)]
        spots = [(45, 250, "1"), (985, 300, "2"), (60, 420, "3"), (960, 140, "4")]
        for i, (x, y, digit) in enumerate(spots):
            r = pygame.Rect(0, 0, 38, 38)
            r.center = (x, y + bob(2.0, 8, i))
            pygame.draw.rect(screen, colors[i], r, border_radius=6)
            pygame.draw.rect(screen, (60, 60, 60), r, 3, border_radius=6)
            draw_text(digit, font_hint, BLACK, r.centerx, r.centery)
    elif theme_key == "MONEY":
        for i in range(2):
            x = int((t * (40 + i * 25) + i * 500) % (SCREEN_WIDTH + 120)) - 60
            y = 130 + i * 150 + bob(2.0, 6, i)
            pygame.draw.ellipse(screen, (255, 150, 60), (x - 18, y - 9, 36, 18))
            pygame.draw.polygon(screen, (255, 150, 60), [(x - 16, y), (x - 30, y - 9), (x - 30, y + 9)])
            pygame.draw.circle(screen, WHITE, (x + 8, y - 2), 3)
        for i, x in enumerate((70, 950)):
            pygame.draw.circle(screen, (255, 205, 70), (x, 430 + bob(2.5, 6, i)), 14)
            pygame.draw.circle(screen, (200, 150, 30), (x, 430 + bob(2.5, 6, i)), 14, 3)
        for x in (25, 995):
            for k in range(4):
                pygame.draw.line(screen, (40, 160, 90), (x, ground_y + 30), (x + bob(1.5, 6, k), ground_y - 40 + k * 8), 5)
    elif theme_key == "CLOCK":
        cx, cy = 90, 300 + bob(1.0, 5)
        pygame.draw.circle(screen, (235, 248, 255), (cx, cy), 42)
        pygame.draw.circle(screen, (60, 120, 170), (cx, cy), 42, 4)
        pygame.draw.line(screen, (60, 120, 170), (cx, cy), (cx, cy - 26), 3)
        pygame.draw.line(screen, (60, 120, 170), (cx, cy), (cx + 18, cy + 8), 3)
    elif theme_key == "PIZZA FRACTION":
        cx, cy = 935, 300 + bob(1.5, 8)
        pygame.draw.circle(screen, (240, 190, 90), (cx, cy), 44)
        pygame.draw.circle(screen, (200, 60, 40), (cx, cy), 36)
        pygame.draw.circle(screen, (255, 225, 120), (cx, cy), 32)
        for angle in range(0, 360, 90):
            a = math.radians(angle + 45)
            pygame.draw.line(screen, (170, 110, 40), (cx, cy), (cx + int(44 * math.cos(a)), cy + int(44 * math.sin(a))), 3)
        for x in (60, 260, 760):
            pygame.draw.circle(screen, (255, 130, 40), (x, ground_y + 20 + bob(2.0, 5, x)), 9)
    elif theme_key == "MIXED QUICKSTART":
        pygame.draw.circle(screen, (230, 140, 90), (90, 170 + bob(0.8, 6)), 34)
        pygame.draw.circle(screen, (190, 100, 60), (90, 170 + bob(0.8, 6)), 34, 3)
        rx = int((t * 30) % (SCREEN_WIDTH + 100)) - 50
        pygame.draw.polygon(screen, (230, 230, 240), [(rx, 470), (rx - 30, 462), (rx - 30, 478)])
        pygame.draw.polygon(screen, (255, 150, 60), [(rx - 30, 470), (rx - 46, 462), (rx - 46, 478)])
    elif theme_key == "HOME":
        for i, x in enumerate(range(40, SCREEN_WIDTH, 95)):
            fy = ground_y + 26 + (i % 3) * 22
            pygame.draw.line(screen, (50, 130, 60), (x, fy), (x, fy + 10), 2)
            pygame.draw.circle(screen, [(255, 110, 140), (255, 215, 80), (255, 255, 255)][i % 3], (x, fy), 5)


# =========================================================
# REUSABLE UI COMPONENTS
# =========================================================

def draw_game_button(rect, text, theme_key, selected, font=None, disabled=False):
    theme = WORLD_THEMES[theme_key]
    font = font or font_ui_button

    draw_rect = rect.copy()
    if selected and not disabled:
        draw_rect.inflate_ip(8, 6)

    shadow_rect = draw_rect.move(0, 4)
    pygame.draw.rect(screen, (0, 0, 0, 60), shadow_rect, border_radius=14)

    fill = theme["button_selected"] if (selected and not disabled) else theme["button"]
    if disabled:
        fill = GRAY
    pygame.draw.rect(screen, fill, draw_rect, border_radius=14)

    border_color = theme["border"] if not disabled else GRAY
    pygame.draw.rect(screen, border_color, draw_rect, 4 if selected else 3, border_radius=14)

    text_color = theme["text_on_button"] if not disabled else (110, 110, 110)
    label_font = fit_font(text, [font, font_dashboard, font_dashboard_small], rect.width - 24)
    draw_text(text, label_font, text_color, draw_rect.centerx, draw_rect.centery)

    return draw_rect


def fit_font(text, fonts, max_width):
    for f in fonts:
        if f.size(text)[0] <= max_width:
            return f
    return fonts[-1]


def draw_text_fit(text, fonts, color, x, y, max_width):
    draw_text(text, fit_font(text, fonts, max_width), color, x, y)


def draw_world_title(text, theme_key, y):
    theme = WORLD_THEMES[theme_key]
    font = fit_font(text, [font_world_title, font_topic_title, font_ui_button], SCREEN_WIDTH - 260)
    draw_text(text, font, (0, 0, 0), SCREEN_WIDTH // 2 + 3, y + 3)
    draw_text(text, font, theme["accent"], SCREEN_WIDTH // 2, y)


def draw_status_badge(status, x, y):
    color = STATUS_COLORS.get(status, GRAY)
    label = font_dashboard_small.render(status, True, WHITE)
    rect = label.get_rect(center=(x, y))
    rect.inflate_ip(20, 10)
    pygame.draw.rect(screen, color, rect, border_radius=8)
    screen.blit(label, label.get_rect(center=(x, y)))
    return rect


def draw_progress_bar(x, y, width, height, fraction, color):
    fraction = max(0.0, min(1.0, fraction))
    back_rect = pygame.Rect(x, y, width, height)
    pygame.draw.rect(screen, (215, 218, 224), back_rect, border_radius=height // 2)
    fill_rect = pygame.Rect(x, y, int(width * fraction), height)
    if fill_rect.width > 0:
        pygame.draw.rect(screen, color, fill_rect, border_radius=height // 2)
    pygame.draw.rect(screen, (170, 174, 182), back_rect, 2, border_radius=height // 2)


def draw_content_panel(rect, theme_key, fill=(255, 255, 255, 235)):
    theme = WORLD_THEMES[theme_key]
    panel_surface = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    pygame.draw.rect(panel_surface, fill, panel_surface.get_rect(), border_radius=22)
    screen.blit(panel_surface, rect.topleft)
    pygame.draw.rect(screen, theme["border"], rect, 4, border_radius=22)


def draw_card(rect, icon, title, subtitle=None, selected=False, theme_key="HOME"):
    theme = WORLD_THEMES[theme_key]
    draw_rect = rect.copy()
    
    if selected:
        draw_rect.inflate_ip(12, 12)
        
    shadow_rect = draw_rect.move(0, 6)
    pygame.draw.rect(screen, (0, 0, 0, 50), shadow_rect, border_radius=18)
    
    fill = theme["button_selected"] if selected else theme["button"]
    pygame.draw.rect(screen, fill, draw_rect, border_radius=18)
    
    border_color = (255, 255, 255) if selected else theme["border"]
    border_width = 5 if selected else 3
    pygame.draw.rect(screen, border_color, draw_rect, border_width, border_radius=18)
    
    if subtitle:
        # Topic Screen Horizontal Style Card
        draw_text(icon, font_icon_small, BLACK, draw_rect.left + 50, draw_rect.centery)
        
        text_x = draw_rect.left + 100
        max_text_w = draw_rect.right - text_x - 24
        title_font = fit_font(title, [font_ui_button, font_dashboard, font_dashboard_small], max_text_w)
        sub_font = fit_font(subtitle, [font_hint, font_dashboard_small], max_text_w)

        # Title + subtitle are laid out as one block centred in the card,
        # with a clear gap between them (title sits above centre).
        gap = 8
        title_h = title_font.get_height()
        sub_h = sub_font.get_height()
        block_h = title_h + gap + sub_h
        block_top = draw_rect.centery - block_h // 2
        title_cy = block_top + title_h // 2
        sub_cy = block_top + title_h + gap + sub_h // 2
        title_surf = title_font.render(str(title), True, theme["text_on_button"])
        screen.blit(title_surf, title_surf.get_rect(midleft=(text_x, title_cy)))
        sub_surf = sub_font.render(str(subtitle), True, (60, 60, 60) if selected else (80, 80, 80))
        screen.blit(sub_surf, sub_surf.get_rect(midleft=(text_x, sub_cy)))
    else:
        # Game Selection Grid Style Card
        draw_text(icon, font_icon_large, BLACK, draw_rect.centerx, draw_rect.top + 50)
        
        title_font_scaled = fit_font(title, [font_dashboard, font_dashboard_small], draw_rect.width - 20)
        draw_text(title, title_font_scaled, theme["text_on_button"], draw_rect.centerx, draw_rect.bottom - 32)
        
    return draw_rect


def draw_back_button(theme_key, action):
    """Clear '<- BACK' button in the top-left corner (click / touch + registers a click target)."""
    rect = pygame.Rect(20, 20, 110, 40)
    drawn = draw_game_button(rect, "\u2190 BACK", theme_key, False, font=font_back)
    dashboard_click_targets.append((drawn, action))
    return drawn


def draw_form_field(cx, top, width, label, value, placeholder, active, theme_key,
                    password=False, action=None):
    """One labelled input: label centred above a rounded box. Returns the bottom y.
    Password fields are shown as bullets."""
    theme = WORLD_THEMES[theme_key]
    label_h = font_instruction.get_height()
    draw_text(label, font_instruction, theme["accent"], cx, top + label_h // 2)

    box = pygame.Rect(0, 0, width, 58)
    box.centerx = cx
    box.top = top + label_h + 8
    pygame.draw.rect(screen, WHITE, box, border_radius=14)
    pygame.draw.rect(screen, theme["border"] if active else GRAY, box,
                     4 if active else 2, border_radius=14)

    shown = ("\u2022" * len(value)) if (password and value) else value
    text = shown if shown else placeholder
    font = fit_font(text, [font_ui_button, font_dashboard, font_dashboard_small], box.width - 32)
    draw_text(text, font, BLACK if shown else GRAY, box.centerx, box.centery)

    if action:
        dashboard_click_targets.append((box.copy(), action))
    return box.bottom


def draw_form_button(rect, text, theme_key, focused, action):
    drawn = draw_game_button(rect, text, theme_key, focused, font=font_dashboard)
    dashboard_click_targets.append((drawn, action))
    return drawn


# =========================================================
# LOAD STUDENTS (always filtered by the selected section)
# =========================================================

def load_students():
    global students
    if current_section_id is None:
        students = []
        return
    try:
        students = [norm_student(r) for r in get_students_by_section(current_section_id)]
    except Exception as e:
        print("Could not load students:", e)
        students = []


def load_login_sections():
    """Sections shown on the student-side 'SELECT SECTION' screen."""
    global login_sections
    rows = []
    fn = getattr(db, "get_all_sections", None)
    if fn:
        try:
            rows = list(fn())
        except Exception as e:
            print("get_all_sections error:", e)
    else:
        # No get_all_sections() in database.py: gather every teacher's sections
        for tid in range(1, 51):
            try:
                rows.extend(get_teacher_sections(tid))
            except Exception:
                pass

    result = []
    for row in rows:
        sid, name, _tid = norm_section(row)
        if sid is None:
            continue
        try:
            count = int(get_section_student_count(sid) or 0)
        except Exception:
            count = 0
        result.append({"id": sid, "name": name, "count": count})
    result.sort(key=lambda s: s["name"].upper())
    login_sections = result


# =========================================================
# HOME SCREEN
# =========================================================

def draw_home():

    draw_world_background("HOME")
    draw_world_particles("HOME", animation_time)

    draw_world_title("MATHEMATICS ADVENTURE", "HOME", 70)
    draw_text("CAPSTONE 2 - MATHEMATICS LEARNING SYSTEM", font_instruction, BLACK, SCREEN_WIDTH // 2, 118)

    start_y = 230
    for index, option in enumerate(home_menu_options):
        rect = pygame.Rect(0, 0, 340, 65)
        rect.centerx = SCREEN_WIDTH // 2
        rect.y = start_y + index * 90
        drawn = draw_game_button(rect, option, "HOME", index == selected_home_option)
        dashboard_click_targets.append((drawn, lambda i=index: home_activate(i)))

    draw_text(
        "UP / DOWN = Select   |   ENTER = Confirm",
        font_instruction,
        BLACK,
        SCREEN_WIDTH // 2,
        start_y + len(home_menu_options) * 90 + 20
    )


def home_activate(index=None):
    global selected_home_option, current_screen
    global selected_section_option, section_select_scroll
    global teacher_username_input, teacher_password_input, teacher_login_field, teacher_login_error
    if index is not None:
        selected_home_option = index
    if selected_home_option == 0:
        load_login_sections()
        selected_section_option, section_select_scroll = 0, 0
        current_screen = SECTION_SELECTION
    else:
        teacher_username_input = TEACHER_USERNAME_DEFAULT
        teacher_password_input = ""
        teacher_login_field = 1
        teacher_login_error = ""
        current_screen = TEACHER_LOGIN


def go_home():
    global current_screen
    current_screen = HOME


# =========================================================
# STUDENT SIDE: SELECT SECTION
# =========================================================

def draw_section_selection():
    global section_select_scroll

    draw_world_background("HOME")
    draw_world_particles("HOME", animation_time)

    draw_world_title("SELECT GRADE 1 SECTION", "HOME", 45)
    draw_back_button("HOME", go_home)

    if not login_sections:
        draw_text("NO SECTIONS YET", large_font, GRAY, SCREEN_WIDTH // 2, 240)
        draw_text("ASK YOUR TEACHER TO CREATE ONE", font_instruction, BLACK, SCREEN_WIDTH // 2, 310)
        draw_text("ESC = Back", font_instruction, BLACK, SCREEN_WIDTH // 2, 400)
        return

    visible_items = 4
    total = len(login_sections)

    if selected_section_option < section_select_scroll:
        section_select_scroll = selected_section_option
    elif selected_section_option >= section_select_scroll + visible_items:
        section_select_scroll = selected_section_option - visible_items + 1

    card_w, card_h, gap_y, start_y = 580, 80, 14, 115
    for i in range(section_select_scroll, min(total, section_select_scroll + visible_items)):
        sec = login_sections[i]
        rect = pygame.Rect(0, start_y + (i - section_select_scroll) * (card_h + gap_y), card_w, card_h)
        rect.centerx = SCREEN_WIDTH // 2
        subtitle = "Grade 1  -  " + str(sec["count"]) + (" student" if sec["count"] == 1 else " students")
        drawn = draw_card(rect, section_icon(sec["id"]), sec["name"].upper(), subtitle,
                          selected=(i == selected_section_option), theme_key="HOME")
        dashboard_click_targets.append((drawn, lambda i=i: choose_section(i)))

    if total > visible_items:
        draw_text(f"{section_select_scroll + 1}-{min(total, section_select_scroll + visible_items)} of {total}",
                  font_hint, BLACK, SCREEN_WIDTH - 70, 88)

    draw_text("UP / DOWN = Select   |   ENTER = Confirm   |   ESC = Back",
              font_instruction, BLACK, SCREEN_WIDTH // 2, start_y + visible_items * (card_h + gap_y) + 15)


def choose_section(index=None):
    global selected_section_option, current_section_id, current_section_name
    global selected_student_option, student_scroll_offset, current_screen
    if index is not None:
        selected_section_option = index
    if not login_sections:
        return
    sec = login_sections[selected_section_option]
    current_section_id = sec["id"]
    current_section_name = sec["name"]
    load_students()
    selected_student_option, student_scroll_offset = 0, 0
    current_screen = STUDENT_SELECTION


# =========================================================
# STUDENT SELECTION (card grid, filtered by section)
# =========================================================

STUDENT_GRID_COLS = 4
STUDENT_GRID_VISIBLE_ROWS = 3


def draw_student_card(rect, icon, line1, line2, selected, label="[ SELECT ]"):
    theme = WORLD_THEMES["HOME"]
    draw_rect = rect.copy()
    if selected:
        draw_rect.inflate_ip(12, 12)

    pygame.draw.rect(screen, (0, 0, 0, 50), draw_rect.move(0, 6), border_radius=18)
    pygame.draw.rect(screen, theme["button_selected"] if selected else theme["button"],
                     draw_rect, border_radius=18)
    pygame.draw.rect(screen, (255, 255, 255) if selected else theme["border"], draw_rect,
                     5 if selected else 3, border_radius=18)

    inner = draw_rect.width - 20
    draw_text(icon, font_icon_small, BLACK, draw_rect.centerx, draw_rect.top + 26)
    f1 = fit_font(line1, [font_dashboard, font_dashboard_small], inner)
    draw_text(line1, f1, theme["text_on_button"], draw_rect.centerx, draw_rect.top + 55)
    if line2:
        f2 = fit_font(line2, [font_dashboard, font_dashboard_small], inner)
        draw_text(line2, f2, theme["text_on_button"], draw_rect.centerx, draw_rect.top + 77)
    if label:
        draw_text(label, font_hint, (60, 60, 60), draw_rect.centerx, draw_rect.bottom - 14)
    return draw_rect


def draw_student_selection():
    global student_scroll_offset

    draw_world_background("HOME")
    draw_world_particles("HOME", animation_time)

    draw_world_title(section_title(current_section_name), "HOME", 45)
    draw_text("SELECT YOUR NAME", font_instruction, BLACK, SCREEN_WIDTH // 2, 88)
    draw_back_button("HOME", student_selection_back)

    total_options = len(students) + 2
    cols = STUDENT_GRID_COLS
    total_rows = (total_options + cols - 1) // cols

    sel_row = selected_student_option // cols
    if sel_row < student_scroll_offset:
        student_scroll_offset = sel_row
    elif sel_row >= student_scroll_offset + STUDENT_GRID_VISIBLE_ROWS:
        student_scroll_offset = sel_row - STUDENT_GRID_VISIBLE_ROWS + 1
    student_scroll_offset = max(0, min(student_scroll_offset, max(0, total_rows - STUDENT_GRID_VISIBLE_ROWS)))

    card_w, card_h, gap_x, gap_y = 210, 112, 18, 16
    start_x = (SCREEN_WIDTH - (cols * card_w + (cols - 1) * gap_x)) // 2
    start_y = 120

    first_index = student_scroll_offset * cols
    last_index = min(total_options, (student_scroll_offset + STUDENT_GRID_VISIBLE_ROWS) * cols)

    for i in range(first_index, last_index):
        local = i - first_index
        row, col = divmod(local, cols)
        rect = pygame.Rect(start_x + col * (card_w + gap_x), start_y + row * (card_h + gap_y), card_w, card_h)
        selected = (i == selected_student_option)

        if i < len(students):
            _sid, _display, first, last = students[i]
            drawn = draw_student_card(rect, "\U0001F9D2", first, last, selected)
        elif i == len(students):
            drawn = draw_student_card(rect, "\u2795", "REGISTER", "NEW STUDENT", selected, label="")
        else:
            drawn = draw_student_card(rect, "\U0001F5D1", "DELETE", "STUDENT", selected, label="")
        dashboard_click_targets.append((drawn, lambda i=i: activate_student_option(i)))

    if not students:
        draw_text("NO STUDENTS IN THIS SECTION YET", font_instruction, BLACK, SCREEN_WIDTH // 2, 470)

    draw_text("ARROWS = Select   |   ENTER = Confirm   |   ESC = Back",
              font_instruction, BLACK, SCREEN_WIDTH // 2, 550)


def student_selection_back():
    global current_screen
    current_screen = SECTION_SELECTION


def activate_student_option(index=None):
    global selected_student_option, current_player_id, current_player, current_screen
    global delete_student_index, delete_scroll_offset
    if index is not None:
        selected_student_option = index
    register_index = len(students)
    delete_index = len(students) + 1
    if selected_student_option < len(students):
        current_player_id = students[selected_student_option][0]
        current_player = students[selected_student_option][1]
        current_screen = CURRENT_PLAYER
    elif selected_student_option == register_index:
        open_student_form("STUDENT", current_section_id, current_section_name)
    elif selected_student_option == delete_index:
        if students:
            delete_student_index, delete_scroll_offset = 0, 0
            current_screen = DELETE_STUDENT
        else:
            print("NO STUDENTS TO DELETE")


def move_student_selection(dx, dy):
    global selected_student_option
    total = len(students) + 2
    cols = STUDENT_GRID_COLS
    sel = selected_student_option
    if dx:
        selected_student_option = (sel + dx) % total
    elif dy < 0:
        if sel - cols >= 0:
            selected_student_option = sel - cols
    elif dy > 0:
        if sel + cols <= total - 1:
            selected_student_option = sel + cols
        elif sel // cols < (total - 1) // cols:
            selected_student_option = total - 1


# =========================================================
# REUSABLE VIRTUAL KEYBOARD
# =========================================================

def open_keyboard(title, value, callback, return_screen, password=False, lower=False, max_len=30):
    """Open the shared virtual keyboard for ANY text field.
    callback(text) is called when DONE is pressed; ESC cancels without calling it."""
    global keyboard_title, keyboard_value, keyboard_callback, keyboard_return_screen
    global keyboard_password, keyboard_lower, keyboard_max_len
    global keyboard_row, keyboard_col, current_screen
    keyboard_title = title
    keyboard_value = value or ""
    keyboard_callback = callback
    keyboard_return_screen = return_screen
    keyboard_password = password
    keyboard_lower = lower
    keyboard_max_len = max_len
    keyboard_row, keyboard_col = 0, 0
    current_screen = VIRTUAL_KEYBOARD


def finish_keyboard():
    global current_screen
    value = keyboard_value
    callback = keyboard_callback
    current_screen = keyboard_return_screen
    if callback:
        callback(value)


def cancel_keyboard():
    global current_screen
    current_screen = keyboard_return_screen


def keyboard_key_width(key):
    return 120 if key in SPECIAL_KEYS else 70


def draw_virtual_keyboard():

    draw_world_background("HOME")
    draw_world_particles("HOME", animation_time)

    draw_world_title(keyboard_title, "HOME", 40)

    name_box = pygame.Rect(0, 0, 640, 55)
    name_box.centerx = SCREEN_WIDTH // 2
    name_box.y = 85

    pygame.draw.rect(screen, WHITE, name_box, border_radius=10)
    pygame.draw.rect(screen, WORLD_THEMES["HOME"]["border"], name_box, 3, border_radius=10)

    if keyboard_password:
        display_name = "\u2022" * len(keyboard_value)
    else:
        display_name = keyboard_value
    empty = (display_name == "")
    if empty:
        display_name = "TYPE HERE"
    shown_font = fit_font(display_name, [input_font, small_font, font_dashboard], name_box.width - 30)
    draw_text(display_name, shown_font, GRAY if empty else BLACK, name_box.centerx, name_box.centery)

    key_height = 42
    gap = 6
    keyboard_start_y = 155

    for row_index, row in enumerate(keyboard_rows):
        widths = [keyboard_key_width(k) for k in row]
        row_width = sum(widths) + (len(row) - 1) * gap
        x = (SCREEN_WIDTH - row_width) // 2
        y = keyboard_start_y + row_index * (key_height + gap)

        for col_index, key in enumerate(row):
            rect = pygame.Rect(x, y, widths[col_index], key_height)
            selected = (row_index == keyboard_row and col_index == keyboard_col)

            fill = WORLD_THEMES["HOME"]["button_selected"] if selected else WHITE
            pygame.draw.rect(screen, fill, rect, border_radius=8)
            pygame.draw.rect(screen, WORLD_THEMES["HOME"]["border"] if selected else GRAY, rect,
                             3 if selected else 2, border_radius=8)

            label = key
            if len(key) == 1 and key.isalpha():
                label = key.lower() if keyboard_lower else key.upper()
            font = font_key_small if key in SPECIAL_KEYS or key == "aA" else small_font
            draw_text(label, font, BLACK, rect.centerx, rect.centery)

            dashboard_click_targets.append((rect.copy(), lambda r=row_index, c=col_index: click_keyboard_key(r, c)))
            x += widths[col_index] + gap

    instructions_y = keyboard_start_y + len(keyboard_rows) * (key_height + gap) + 22
    draw_text("UP / DOWN / LEFT / RIGHT = Move", font_instruction, WORLD_THEMES["HOME"]["accent"], SCREEN_WIDTH // 2, instructions_y)
    draw_text("ENTER = Select   |   aA = Upper/Lower   |   DONE = Finish   |   ESC = Cancel",
              font_instruction, (40, 140, 60), SCREEN_WIDTH // 2, instructions_y + 32)


# =========================================================
# VIRTUAL KEYBOARD MOVEMENT
# =========================================================

def move_keyboard_up():
    global keyboard_row, keyboard_col
    keyboard_row -= 1
    if keyboard_row < 0:
        keyboard_row = len(keyboard_rows) - 1
    if keyboard_col >= len(keyboard_rows[keyboard_row]):
        keyboard_col = len(keyboard_rows[keyboard_row]) - 1

def move_keyboard_down():
    global keyboard_row, keyboard_col
    keyboard_row += 1
    if keyboard_row >= len(keyboard_rows):
        keyboard_row = 0
    if keyboard_col >= len(keyboard_rows[keyboard_row]):
        keyboard_col = len(keyboard_rows[keyboard_row]) - 1

def move_keyboard_left():
    global keyboard_col
    keyboard_col -= 1
    if keyboard_col < 0:
        keyboard_col = len(keyboard_rows[keyboard_row]) - 1

def move_keyboard_right():
    global keyboard_col
    keyboard_col += 1
    if keyboard_col >= len(keyboard_rows[keyboard_row]):
        keyboard_col = 0


# =========================================================
# SELECT VIRTUAL KEYBOARD KEY
# =========================================================

def select_keyboard_key():
    """Press the highlighted key. Returns True when DONE was pressed."""
    global keyboard_value, keyboard_lower
    key = keyboard_rows[keyboard_row][keyboard_col]

    if key == "SPACE":
        if len(keyboard_value) < keyboard_max_len:
            keyboard_value += " "
        return False
    elif key == "BACKSPACE":
        keyboard_value = keyboard_value[:-1]
        return False
    elif key == "CLEAR":
        keyboard_value = ""
        return False
    elif key == "aA":
        keyboard_lower = not keyboard_lower
        return False
    elif key == "DONE":
        return True
    else:
        if len(keyboard_value) < keyboard_max_len:
            if key.isalpha():
                keyboard_value += key.lower() if keyboard_lower else key.upper()
            else:
                keyboard_value += key
        return False


def click_keyboard_key(row, col):
    global keyboard_row, keyboard_col
    keyboard_row, keyboard_col = row, col
    if select_keyboard_key():
        finish_keyboard()


# =========================================================
# TEACHER LOGIN
# =========================================================

def set_teacher_username(value):
    global teacher_username_input, teacher_login_field, teacher_login_error
    teacher_username_input = value.strip()
    teacher_login_error = ""
    teacher_login_field = 1


def set_teacher_password(value):
    global teacher_password_input, teacher_login_field, teacher_login_error
    teacher_password_input = value
    teacher_login_error = ""
    teacher_login_field = 2


def attempt_teacher_login():
    global teacher_login_error, teacher_logged_in, teacher_id, teacher_password_input
    global teacher_dash_sel, teacher_dash_scroll, current_screen
    result = verify_teacher(teacher_username_input, teacher_password_input)
    tid = resolve_teacher_id(result, teacher_username_input) if result else None
    if tid is not None:
        teacher_login_error = ""
        teacher_logged_in = True
        teacher_id = tid
        teacher_password_input = ""
        teacher_dash_sel, teacher_dash_scroll = 0, 0
        load_teacher_dashboard()
        current_screen = TEACHER_DASHBOARD
    else:
        teacher_login_error = "INCORRECT USERNAME OR PASSWORD"
        teacher_password_input = ""


def teacher_login_activate(index=None):
    """ENTER / click on a login item. Fields open the virtual keyboard automatically."""
    global teacher_login_field
    if index is not None:
        teacher_login_field = index
    if teacher_login_field == 0:
        open_keyboard("TEACHER USERNAME", teacher_username_input, set_teacher_username,
                      TEACHER_LOGIN, password=False, lower=True, max_len=24)
    elif teacher_login_field == 1:
        open_keyboard("TEACHER PASSWORD", teacher_password_input, set_teacher_password,
                      TEACHER_LOGIN, password=True, lower=True, max_len=24)
    else:
        attempt_teacher_login()


def draw_teacher_login():
    draw_world_background("TEACHER")
    theme = WORLD_THEMES["TEACHER"]

    draw_world_title("TEACHER LOGIN", "TEACHER", 50)
    draw_back_button("TEACHER", go_home)

    panel = pygame.Rect(0, 0, 620, 440)
    panel.centerx = SCREEN_WIDTH // 2
    panel.y = 95
    draw_content_panel(panel, "TEACHER")
    cx = panel.centerx

    y = panel.top + 24
    y = draw_form_field(cx, y, 500, "USERNAME", teacher_username_input, "teacher",
                        teacher_login_field == 0, "TEACHER",
                        action=lambda: teacher_login_activate(0))
    y += 16
    y = draw_form_field(cx, y, 500, "PASSWORD", teacher_password_input, "ENTER PASSWORD",
                        teacher_login_field == 1, "TEACHER", password=True,
                        action=lambda: teacher_login_activate(1))

    # Reserved row for the error message so the layout never shifts
    if teacher_login_error:
        err_font = fit_font(teacher_login_error, [font_instruction, font_dashboard_small], panel.width - 60)
        draw_text(teacher_login_error, err_font, RED, cx, y + 26)
    y += 52

    login_rect = pygame.Rect(0, 0, 300, 50)
    login_rect.centerx = cx
    login_rect.top = y
    draw_form_button(login_rect, "LOGIN", "TEACHER", teacher_login_field == 2,
                     lambda: teacher_login_activate(2))

    draw_text("UP / DOWN = Move   |   ENTER = Select / Type   |   ESC = Back",
              font_hint, BLACK, cx, panel.bottom - 24)


# =========================================================
# TEACHER DASHBOARD: MY GRADE 1 SECTIONS
# =========================================================

def load_teacher_dashboard():
    """Reload this teacher's sections + live statistics from SQLite."""
    global teacher_sections
    teacher_sections = []
    if teacher_id is None:
        return
    try:
        rows = get_teacher_sections(teacher_id)
    except Exception as e:
        print("Could not load sections:", e)
        return
    for row in rows:
        sid, name, _tid = norm_section(row)
        if sid is None:
            continue
        count, average, attempts = section_stats(sid)
        teacher_sections.append({
            "id": sid, "name": name, "count": count,
            "average": average, "attempts": attempts
        })


def teacher_logout():
    global teacher_logged_in, teacher_id, teacher_sections, current_screen
    teacher_logged_in = False
    teacher_id = None
    teacher_sections = []
    current_screen = HOME


def teacher_back_to_dashboard():
    global current_screen
    load_teacher_dashboard()
    current_screen = TEACHER_DASHBOARD


def draw_section_card(rect, section, selected):
    theme = WORLD_THEMES["TEACHER"]
    pygame.draw.rect(screen, WHITE, rect, border_radius=16)
    pygame.draw.rect(screen, theme["button_selected"] if selected else (200, 204, 214), rect,
                     5 if selected else 2, border_radius=16)

    draw_text(section_icon(section["id"]), font_icon_large, BLACK, rect.left + 55, rect.centery)

    name = section["name"].upper()
    name_font = fit_font(name, [font_topic_title, font_ui_button, font_dashboard], 380)
    draw_text(name, name_font, theme["accent"], rect.left + 110, rect.top + 12, center=False)

    count = section["count"]
    draw_text(f"{count} STUDENT{'' if count == 1 else 'S'}", font_dashboard, BLACK,
              rect.left + 110, rect.top + 58, center=False)

    if section["average"] is None:
        draw_text("NO DATA YET", font_dashboard, GRAY, rect.left + 330, rect.top + 58, center=False)
    else:
        draw_text(f"CLASS AVERAGE: {section['average']:.0f}%", font_dashboard, (40, 140, 60),
                  rect.left + 330, rect.top + 58, center=False)

    open_rect = pygame.Rect(rect.right - 200, rect.centery - 24, 180, 48)
    draw_game_button(open_rect, "OPEN SECTION", "TEACHER", selected, font=font_dashboard_small)


def draw_teacher_dashboard():
    global teacher_dash_scroll

    draw_world_background("TEACHER")
    theme = WORLD_THEMES["TEACHER"]
    draw_world_title("TEACHER DASHBOARD", "TEACHER", 45)
    draw_text("MY GRADE 1 SECTIONS", font_topic_title, theme["accent"], SCREEN_WIDTH // 2, 100)
    draw_back_button("TEACHER", teacher_logout)

    create_rect = pygame.Rect(0, 0, 440, 50)
    create_rect.centerx = SCREEN_WIDTH // 2
    create_rect.y = 132
    drawn = draw_game_button(create_rect, "+ CREATE NEW SECTION", "TEACHER",
                             teacher_dash_sel == 0, font=font_dashboard)
    dashboard_click_targets.append((drawn, open_create_section))

    total = len(teacher_sections)
    if total == 0:
        draw_text("NO SECTIONS YET", button_font, GRAY, SCREEN_WIDTH // 2, 290)
        draw_text("PRESS  + CREATE NEW SECTION  TO START", font_instruction, BLACK, SCREEN_WIDTH // 2, 340)
        draw_text("UP / DOWN = Select   |   ENTER = Confirm   |   ESC = Logout",
                  font_instruction, BLACK, SCREEN_WIDTH // 2, 540)
        return

    visible_items = 3
    if teacher_dash_sel >= 1:
        si = teacher_dash_sel - 1
        if si < teacher_dash_scroll:
            teacher_dash_scroll = si
        elif si >= teacher_dash_scroll + visible_items:
            teacher_dash_scroll = si - visible_items + 1
    teacher_dash_scroll = max(0, min(teacher_dash_scroll, max(0, total - visible_items)))

    start_y, card_h, pitch = 200, 96, 108
    for i in range(teacher_dash_scroll, min(total, teacher_dash_scroll + visible_items)):
        rect = pygame.Rect(0, 0, 780, card_h)
        rect.centerx = SCREEN_WIDTH // 2
        rect.y = start_y + (i - teacher_dash_scroll) * pitch
        draw_section_card(rect, teacher_sections[i], teacher_dash_sel == i + 1)
        dashboard_click_targets.append((rect.copy(), lambda i=i: open_section(teacher_sections[i])))

    if total > visible_items:
        draw_text(f"{teacher_dash_scroll + 1}-{min(total, teacher_dash_scroll + visible_items)} of {total}",
                  font_hint, GRAY, SCREEN_WIDTH - 70, 100)

    draw_text("UP / DOWN = Select   |   ENTER = Open   |   ESC = Logout",
              font_instruction, BLACK, SCREEN_WIDTH // 2, 555)


# =========================================================
# CREATE SECTION
# =========================================================

def open_create_section():
    global create_section_name, create_section_focus, create_section_error, current_screen
    create_section_name = ""
    create_section_focus = 0
    create_section_error = ""
    current_screen = TEACHER_CREATE_SECTION


def cancel_create_section():
    teacher_back_to_dashboard()


def set_create_section_name(value):
    global create_section_name, create_section_focus, create_section_error
    create_section_name = " ".join(value.split()).upper()
    create_section_error = ""
    create_section_focus = 1


def submit_create_section():
    global create_section_error, create_section_focus, teacher_dash_sel, teacher_dash_scroll
    global current_screen
    name = " ".join(create_section_name.split()).upper()
    if not name:
        create_section_error = "SECTION NAME CANNOT BE EMPTY"
        create_section_focus = 0
        return
    if teacher_id is None:
        create_section_error = "PLEASE LOG IN AGAIN"
        return

    try:
        existing = [norm_section(r)[1].strip().upper() for r in get_teacher_sections(teacher_id)]
    except Exception as e:
        print("Section lookup error:", e)
        existing = []
    if name in existing:
        create_section_error = "THAT SECTION ALREADY EXISTS"
        create_section_focus = 0
        return

    try:
        result = create_section(teacher_id, name)
    except Exception as e:
        text = str(e).upper()
        if "UNIQUE" in text or "EXISTS" in text or "DUPLICATE" in text:
            create_section_error = "THAT SECTION ALREADY EXISTS"
        else:
            create_section_error = "COULD NOT CREATE SECTION"
            print("create_section error:", e)
        return
    if result is False:
        create_section_error = "THAT SECTION ALREADY EXISTS"
        return

    load_teacher_dashboard()
    teacher_dash_sel = 0
    for index, sec in enumerate(teacher_sections):
        if sec["name"].strip().upper() == name:
            teacher_dash_sel = index + 1
    teacher_dash_scroll = 0
    print("SECTION CREATED:", name)
    current_screen = TEACHER_DASHBOARD


def create_section_activate(index=None):
    global create_section_focus
    if index is not None:
        create_section_focus = index
    if create_section_focus == 0:
        open_keyboard("SECTION NAME", create_section_name, set_create_section_name,
                      TEACHER_CREATE_SECTION, password=False, lower=False, max_len=24)
    elif create_section_focus == 1:
        submit_create_section()
    else:
        cancel_create_section()


def draw_teacher_create_section():
    draw_world_background("TEACHER")
    theme = WORLD_THEMES["TEACHER"]

    draw_world_title("CREATE GRADE 1 SECTION", "TEACHER", 50)
    draw_back_button("TEACHER", cancel_create_section)

    panel = pygame.Rect(0, 0, 640, 400)
    panel.centerx = SCREEN_WIDTH // 2
    panel.y = 110
    draw_content_panel(panel, "TEACHER")
    cx = panel.centerx

    y = panel.top + 26
    y = draw_form_field(cx, y, 520, "SECTION NAME", create_section_name, "ENTER SECTION NAME",
                        create_section_focus == 0, "TEACHER",
                        action=lambda: create_section_activate(0))

    if create_section_error:
        err_font = fit_font(create_section_error, [font_instruction, font_dashboard_small], panel.width - 60)
        draw_text(create_section_error, err_font, RED, cx, y + 26)
    y += 56

    create_rect = pygame.Rect(0, 0, 320, 50)
    create_rect.centerx = cx
    create_rect.top = y
    draw_form_button(create_rect, "CREATE SECTION", "TEACHER", create_section_focus == 1,
                     lambda: create_section_activate(1))

    cancel_rect = pygame.Rect(0, 0, 320, 50)
    cancel_rect.centerx = cx
    cancel_rect.top = y + 64
    draw_form_button(cancel_rect, "CANCEL", "TEACHER", create_section_focus == 2,
                     lambda: create_section_activate(2))

    draw_text("UP / DOWN = Move   |   ENTER = Select / Type   |   ESC = Cancel",
              font_hint, BLACK, cx, panel.bottom - 24)


# =========================================================
# TEACHER SECTION VIEW (students in one section)
# =========================================================

def load_teacher_section_students():
    global teacher_section_students
    teacher_section_students = []
    if teacher_section_id is None:
        return
    try:
        teacher_section_students = [norm_student(r) for r in get_students_by_section(teacher_section_id)]
    except Exception as e:
        print("Could not load section students:", e)


def open_section(entry):
    """Open one of THIS teacher's sections (ownership is verified)."""
    global teacher_section_id, teacher_section_name
    global section_sel, section_scroll, section_delete_focus, section_confirm, current_screen

    try:
        sec = get_section(entry["id"])
        owner = _field(sec, ["teacher_id"], 2)
        if teacher_id is not None and owner is not None and owner != teacher_id:
            print("ACCESS DENIED: section belongs to another teacher.")
            return
    except Exception as e:
        print("Section lookup error:", e)
        return

    teacher_section_id = entry["id"]
    teacher_section_name = entry["name"]
    section_sel, section_scroll = 0, 0
    section_delete_focus = False
    section_confirm = None
    load_teacher_section_students()
    current_screen = TEACHER_SECTION


def open_teacher_student(index):
    """Open the existing performance screen for a student (index into teacher_section_students)."""
    global current_screen, dashboard_detail_section_name
    if not (0 <= index < len(teacher_section_students)):
        return
    sid, display, _first, _last = teacher_section_students[index]

    sec_name = teacher_section_name
    try:
        sec = get_student_section(sid)
        if isinstance(sec, str):
            found = sec
        else:
            found = _field(sec, ["section_name", "name"], 1)
        if found:
            sec_name = str(found)
    except Exception:
        pass

    open_student_detail(sid, display)
    dashboard_detail_section_name = sec_name
    current_screen = TEACHER_STUDENT_DETAIL


def section_row_click(index):
    global section_sel, section_delete_focus
    section_sel = index + 1
    section_delete_focus = False
    open_teacher_student(index)


def ask_delete_student(index):
    global section_sel, section_confirm, section_confirm_yes, section_delete_focus
    if 0 <= index < len(teacher_section_students):
        section_sel = index + 1
        sid, display, _f, _l = teacher_section_students[index]
        section_confirm = (sid, display)
        section_confirm_yes = False
        section_delete_focus = False


def confirm_delete_section_student():
    global section_confirm, section_sel, section_delete_focus
    if section_confirm:
        sid = section_confirm[0]
        # Only students that are really in this teacher's open section can be deleted
        if sid in [s[0] for s in teacher_section_students]:
            try:
                delete_student(sid)
            except Exception as e:
                print("delete_student error:", e)
    section_confirm = None
    section_delete_focus = False
    load_teacher_section_students()
    section_sel = min(section_sel, len(teacher_section_students))


def cancel_delete_section_student():
    global section_confirm
    section_confirm = None


def set_confirm_yes(value):
    global section_confirm_yes
    section_confirm_yes = value


def open_add_student_teacher():
    open_student_form("TEACHER", teacher_section_id, teacher_section_name)


def draw_teacher_section():
    global section_scroll

    draw_world_background("TEACHER")
    theme = WORLD_THEMES["TEACHER"]
    draw_world_title(section_title(teacher_section_name), "TEACHER", 45)
    draw_back_button("TEACHER", teacher_back_to_dashboard)

    count = len(teacher_section_students)
    draw_text(f"{count} STUDENT{'' if count == 1 else 'S'}", font_topic_title, theme["accent"],
              70, 96, center=False)

    add_rect = pygame.Rect(0, 0, 270, 46)
    add_rect.right = SCREEN_WIDTH - 70
    add_rect.y = 96
    drawn = draw_game_button(add_rect, "+ ADD STUDENT", "TEACHER", section_sel == 0, font=font_dashboard)
    dashboard_click_targets.append((drawn, open_add_student_teacher))

    if count == 0:
        draw_text("NO STUDENTS IN THIS SECTION YET", button_font, GRAY, SCREEN_WIDTH // 2, 300)
        draw_text("PRESS  + ADD STUDENT  TO REGISTER ONE", font_instruction, BLACK, SCREEN_WIDTH // 2, 350)
    else:
        visible_items = 6
        if section_sel >= 1:
            si = section_sel - 1
            if si < section_scroll:
                section_scroll = si
            elif si >= section_scroll + visible_items:
                section_scroll = si - visible_items + 1
        section_scroll = max(0, min(section_scroll, max(0, count - visible_items)))

        start_y, row_h, pitch = 160, 50, 58
        for i in range(section_scroll, min(count, section_scroll + visible_items)):
            _sid, display, _f, _l = teacher_section_students[i]
            row = pygame.Rect(0, 0, 860, row_h)
            row.centerx = SCREEN_WIDTH // 2
            row.y = start_y + (i - section_scroll) * pitch
            selected = (section_sel == i + 1)

            pygame.draw.rect(screen, WHITE, row, border_radius=12)
            pygame.draw.rect(screen, theme["button_selected"] if selected else (200, 204, 214), row,
                             4 if selected else 2, border_radius=12)
            draw_text("\U0001F9D2", font_icon_small, BLACK, row.left + 38, row.centery)
            name_font = fit_font(display, [font_ui_button, font_dashboard, font_dashboard_small], 520)
            surf = name_font.render(display, True, BLACK)
            screen.blit(surf, surf.get_rect(midleft=(row.left + 80, row.centery)))

            draw_text("VIEW PERFORMANCE", font_dashboard_small, theme["accent"],
                      row.right - 290, row.centery)

            del_rect = pygame.Rect(row.right - 130, row.top + 7, 116, 36)
            del_focus = selected and section_delete_focus
            pygame.draw.rect(screen, RED if del_focus else (240, 205, 205), del_rect, border_radius=10)
            pygame.draw.rect(screen, RED, del_rect, 3 if del_focus else 2, border_radius=10)
            draw_text("DELETE", font_dashboard_small, WHITE if del_focus else (120, 40, 40),
                      del_rect.centerx, del_rect.centery)

            dashboard_click_targets.append((row.copy(), lambda i=i: section_row_click(i)))
            dashboard_click_targets.append((del_rect.copy(), lambda i=i: ask_delete_student(i)))

        if count > visible_items:
            draw_text(f"{section_scroll + 1}-{min(count, section_scroll + visible_items)} of {count}",
                      font_hint, GRAY, SCREEN_WIDTH - 70, 150)

    draw_text("UP / DOWN = Select   |   ENTER = Open   |   RIGHT = Delete   |   ESC = Back",
              font_hint, BLACK, SCREEN_WIDTH // 2, 550)

    if section_confirm:
        draw_confirm_delete_overlay()


def draw_confirm_delete_overlay():
    dim = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 150))
    screen.blit(dim, (0, 0))
    # Full-screen blocker: appended before the buttons so the buttons are checked first
    dashboard_click_targets.append((pygame.Rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT), lambda: None))

    box = pygame.Rect(0, 0, 560, 240)
    box.center = (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
    draw_content_panel(box, "TEACHER", fill=(255, 255, 255, 255))

    name = section_confirm[1]
    line = f"DELETE {name}?"
    draw_text(line, fit_font(line, [font_topic_title, font_ui_button, font_dashboard], box.width - 40),
              RED, box.centerx, box.top + 55)
    draw_text("This cannot be undone.", font_instruction, BLACK, box.centerx, box.top + 100)

    yes_rect = pygame.Rect(0, 0, 200, 50)
    yes_rect.center = (box.centerx - 120, box.bottom - 60)
    no_rect = pygame.Rect(0, 0, 200, 50)
    no_rect.center = (box.centerx + 120, box.bottom - 60)
    draw_form_button(yes_rect, "YES, DELETE", "TEACHER", section_confirm_yes, confirm_delete_section_student)
    draw_form_button(no_rect, "NO, KEEP", "TEACHER", not section_confirm_yes, cancel_delete_section_student)


# =========================================================
# ADD / REGISTER STUDENT FORM (shared: teacher + student side)
# =========================================================

def open_student_form(kind, section_id, section_name):
    global form_kind, form_first, form_last, form_focus, form_error
    global form_section_id, form_section_name, current_screen
    form_kind = kind
    form_first, form_last = "", ""
    form_focus = 0
    form_error = ""
    form_section_id = section_id
    form_section_name = section_name
    current_screen = TEACHER_ADD_STUDENT if kind == "TEACHER" else REGISTER_STUDENT


def student_form_cancel():
    global current_screen
    current_screen = TEACHER_SECTION if form_kind == "TEACHER" else STUDENT_SELECTION


def set_form_first(value):
    global form_first, form_focus, form_error
    form_first = " ".join(value.split())
    form_error = ""
    form_focus = 1


def set_form_last(value):
    global form_last, form_focus, form_error
    form_last = " ".join(value.split())
    form_error = ""
    form_focus = 2


def submit_student_form():
    global form_error, form_focus, current_screen
    global section_sel, section_scroll
    global current_player, current_player_id, selected_student_option

    first = " ".join(form_first.split()).title()
    last = " ".join(form_last.split()).title()

    if not first:
        form_error = "FIRST NAME CANNOT BE EMPTY"
        form_focus = 0
        return
    if not last:
        form_error = "LAST NAME CANNOT BE EMPTY"
        form_focus = 1
        return
    if form_section_id is None:
        form_error = "NO SECTION SELECTED"
        return

    try:
        existing = [norm_student(r) for r in get_students_by_section(form_section_id)]
    except Exception as e:
        print("Student lookup error:", e)
        existing = []
    if any(s[2].strip().lower() == first.lower() and s[3].strip().lower() == last.lower() for s in existing):
        form_error = "THIS STUDENT IS ALREADY IN THE SECTION"
        form_focus = 0
        return

    try:
        result = add_student(first, last, form_section_id)
    except Exception as e:
        form_error = "COULD NOT ADD STUDENT"
        print("add_student error:", e)
        return
    if result is False:
        form_error = "COULD NOT ADD STUDENT"
        return

    print("STUDENT REGISTERED:", first, last, "->", section_title(form_section_name))

    if form_kind == "TEACHER":
        load_teacher_section_students()
        section_sel, section_scroll = 0, 0
        for index, s in enumerate(teacher_section_students):
            if s[2].lower() == first.lower() and s[3].lower() == last.lower():
                section_sel = index + 1
        current_screen = TEACHER_SECTION
    else:
        load_students()
        matches = [(i, s) for i, s in enumerate(students)
                   if s[2].lower() == first.lower() and s[3].lower() == last.lower()]
        if matches:
            index, s = max(matches, key=lambda m: (m[1][0] or 0))
            selected_student_option = index
            current_player_id = s[0]
            current_player = s[1]
            current_screen = CURRENT_PLAYER
        else:
            current_screen = STUDENT_SELECTION


def student_form_activate(index=None):
    global form_focus
    if index is not None:
        form_focus = index
    if form_focus == 0:
        open_keyboard("FIRST NAME", form_first, set_form_first, current_screen,
                      password=False, lower=False, max_len=30)
    elif form_focus == 1:
        open_keyboard("LAST NAME", form_last, set_form_last, current_screen,
                      password=False, lower=False, max_len=30)
    elif form_focus == 2:
        submit_student_form()
    else:
        student_form_cancel()


def draw_student_form():
    is_teacher = (form_kind == "TEACHER")
    theme_key = "TEACHER" if is_teacher else "HOME"
    theme = WORLD_THEMES[theme_key]

    draw_world_background(theme_key)
    if not is_teacher:
        draw_world_particles("HOME", animation_time)

    draw_world_title("ADD STUDENT" if is_teacher else "REGISTER NEW STUDENT", theme_key, 50)
    draw_back_button(theme_key, student_form_cancel)

    panel = pygame.Rect(0, 0, 640, 450)
    panel.centerx = SCREEN_WIDTH // 2
    panel.y = 95
    draw_content_panel(panel, theme_key)
    cx = panel.centerx

    y = panel.top + 20
    y = draw_form_field(cx, y, 520, "FIRST NAME", form_first, "ENTER FIRST NAME",
                        form_focus == 0, theme_key, action=lambda: student_form_activate(0))
    y += 12
    y = draw_form_field(cx, y, 520, "LAST NAME", form_last, "ENTER LAST NAME",
                        form_focus == 1, theme_key, action=lambda: student_form_activate(1))
    y += 16

    section_line = "SECTION:  " + section_title(form_section_name)
    draw_text(section_line, fit_font(section_line, [font_dashboard, font_dashboard_small], panel.width - 50),
              theme["accent"], cx, y + 12)
    y += 32

    if form_error:
        err_font = fit_font(form_error, [font_instruction, font_dashboard_small], panel.width - 60)
        draw_text(form_error, err_font, RED, cx, y + 12)
    y += 30

    add_rect = pygame.Rect(0, 0, 300, 46)
    add_rect.centerx = cx
    add_rect.top = y
    draw_form_button(add_rect, "ADD STUDENT", theme_key, form_focus == 2, lambda: student_form_activate(2))

    cancel_rect = pygame.Rect(0, 0, 300, 46)
    cancel_rect.centerx = cx
    cancel_rect.top = y + 56
    draw_form_button(cancel_rect, "CANCEL", theme_key, form_focus == 3, lambda: student_form_activate(3))

    draw_text("UP / DOWN = Move   |   ENTER = Select / Type   |   ESC = Cancel",
              font_hint, BLACK, cx, panel.bottom - 20)


# =========================================================
# DELETE STUDENT SCREEN (student side, current section only)
# =========================================================

def draw_delete_student():

    draw_world_background("HOME")
    draw_world_particles("HOME", animation_time)

    draw_world_title("DELETE STUDENT", "HOME", 60)
    draw_text(section_title(current_section_name), font_instruction, BLACK, SCREEN_WIDTH // 2, 100)

    if len(students) == 0:
        draw_text("NO STUDENTS TO DELETE", large_font, GRAY, SCREEN_WIDTH // 2, 220)
        draw_text("ESC = Back", font_instruction, BLACK, SCREEN_WIDTH // 2, 400)
        return

    global delete_scroll_offset
    visible_items = 5

    if delete_student_index < delete_scroll_offset:
        delete_scroll_offset = delete_student_index
    elif delete_student_index >= delete_scroll_offset + visible_items:
        delete_scroll_offset = delete_student_index - visible_items + 1

    start_y = 130

    for i in range(delete_scroll_offset, min(len(students), delete_scroll_offset + visible_items)):

        display_index = i - delete_scroll_offset
        student = students[i]
        name = student[1]

        student_rect = pygame.Rect(0, 0, 440, 45)
        student_rect.centerx = SCREEN_WIDTH // 2
        student_rect.y = start_y + display_index * 55

        draw_game_button(student_rect, name, "HOME", i == delete_student_index, font=font_dashboard)

    draw_text("ENTER = Delete Selected Student", font_instruction, RED, SCREEN_WIDTH // 2, 430)
    draw_text("ESC = Cancel", font_instruction, BLACK, SCREEN_WIDTH // 2, 465)


# =========================================================
# CURRENT PLAYER
# =========================================================

def draw_current_player():
    draw_world_background("HOME")
    draw_world_particles("HOME", animation_time)
    draw_world_title("CURRENT PLAYER", "HOME", 90)
    draw_text(current_player, fit_font(current_player, [large_font, button_font, small_font], SCREEN_WIDTH - 80),
              (40, 140, 60), SCREEN_WIDTH // 2, 220)
    draw_text(section_title(current_section_name), font_topic_title, BLACK, SCREEN_WIDTH // 2, 285)
    draw_text("Press ENTER to continue", font_topic_title, BLACK, SCREEN_WIDTH // 2, 355)
    draw_text("ESC = Back", font_instruction, BLACK, SCREEN_WIDTH // 2, 430)


# =========================================================
# GAME SELECTION (CARD GRID)
# =========================================================

def draw_game_selection():
    draw_world_background("HOME")
    draw_world_particles("HOME", animation_time)

    draw_world_title("CHOOSE A GAME", "HOME", 45)
    draw_text("PLAYER: " + current_player, font_instruction, BLACK, SCREEN_WIDTH // 2, 85)

    card_w, card_h = 220, 145
    start_x = 110
    gap_x = 50
    gap_y = 25
    start_y = 120

    for index, game_data in enumerate(game_cards_data):
        row = index // 3
        col = index % 3
        
        # Center the bottom row if it has fewer items
        if row == 1:
            row_start_x = start_x + (card_w + gap_x) // 2
        else:
            row_start_x = start_x

        x = row_start_x + col * (card_w + gap_x)
        y = start_y + row * (card_h + gap_y)

        card_rect = pygame.Rect(x, y, card_w, card_h)
        draw_card(card_rect, game_data["icon"], game_data["name"], selected=(index == selected_game), theme_key="HOME")

    draw_text("ARROWS = Navigate   |   ENTER = Confirm   |   ESC = Back", font_instruction, BLACK, SCREEN_WIDTH // 2, 530)



# =========================================================
# SHARED GAME-SCREEN HELPERS (consistent look for every game)
# =========================================================

GAME_PANEL_PAD = 30


def game_colors(theme_key):
    """Readable text colours on the white game panel for each world."""
    if theme_key == "MONEY":
        return {"title": (10, 70, 130), "accent": (10, 70, 130), "good": (40, 140, 60)}
    return {"title": WORLD_THEMES[theme_key]["accent"], "accent": WORLD_THEMES[theme_key]["accent"],
            "good": (40, 140, 60)}


def wrap_lines(text, font, max_width):
    lines, current = [], []
    for word in str(text).split(" "):
        test = " ".join(current + [word])
        if font.size(test)[0] <= max_width or not current:
            current.append(word)
        else:
            lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))
    return lines


def draw_wrapped_fit(text, fonts, color, center_x, top, max_width, max_height):
    """Wrap text and pick the largest font whose block fits max_height.
    Text is centred vertically inside [top, top + max_height]."""
    chosen, lines = fonts[-1], None
    for f in fonts:
        f = peso_safe(f) if "\u20b1" in str(text) else f
        candidate = wrap_lines(text, f, max_width)
        if len(candidate) * f.get_linesize() <= max_height:
            chosen, lines = f, candidate
            break
        chosen, lines = f, candidate
    block_h = len(lines) * chosen.get_linesize()
    y = top + (max_height - block_h) // 2 + chosen.get_linesize() // 2
    for line in lines:
        draw_text(line, chosen, color, center_x, y)
        y += chosen.get_linesize()


def make_game_panel(theme_key, width, height, y=None):
    panel = pygame.Rect(0, 0, width, height)
    panel.centerx = SCREEN_WIDTH // 2
    panel.y = y if y is not None else (SCREEN_HEIGHT - height) // 2
    draw_content_panel(panel, theme_key)
    return panel


def draw_game_header(panel, theme_key, title, question_text):
    colors = game_colors(theme_key)
    inner_w = panel.width - 2 * GAME_PANEL_PAD
    title_font = fit_font(title, [font_topic_title, font_ui_button, font_dashboard], inner_w)
    draw_text(title, title_font, colors["title"], panel.centerx, panel.top + 46)
    draw_text(question_text, font_instruction, BLACK, panel.centerx, panel.top + 92)


def draw_answer_box(rect, text, theme_key, font=None):
    colors = game_colors(theme_key)
    font = font or font_answer_big
    pygame.draw.rect(screen, WHITE, rect, border_radius=14)
    pygame.draw.rect(screen, colors["accent"], rect, 4, border_radius=14)
    label = str(text)
    if "\u20b1" in label:
        font = peso_safe(font)
    font = fit_font(label, [font, font_ui_button, font_dashboard], rect.width - 24)
    draw_text(label, font, BLACK, rect.centerx, rect.centery)


def draw_instruction_block(panel, theme_key, top, line1, chips, hint):
    """ESP32 gameplay instructions, centred inside the panel.
    top = y of the first line's centre. Layout: line1 / chip row / hint.
    Returns the bottom y of the block."""
    theme = WORLD_THEMES[theme_key]
    inner_w = panel.width - 2 * GAME_PANEL_PAD

    # Line 1 - what to do (font_instruction, shrinks if ever too long)
    f1 = peso_safe(fit_font(line1, [font_instruction, font_dashboard_small], inner_w))
    draw_text(line1, f1, BLACK, panel.centerx, top)

    # Chip row - the physical positions / buttons, e.g. ONES | TENS
    chip_font = peso_safe(font_dashboard)
    chip_h, chip_gap, pad_x = 36, 26, 22
    widths = [chip_font.size(c)[0] + 2 * pad_x for c in chips]
    total_w = sum(widths) + chip_gap * (len(chips) - 1)
    if total_w > inner_w:  # squeeze padding on very narrow panels
        pad_x = 10
        widths = [chip_font.size(c)[0] + 2 * pad_x for c in chips]
        total_w = sum(widths) + chip_gap * (len(chips) - 1)
    chip_cy = top + 20 + chip_h // 2 + 6
    x = panel.centerx - total_w // 2
    for i, (label, w) in enumerate(zip(chips, widths)):
        rect = pygame.Rect(x, chip_cy - chip_h // 2, w, chip_h)
        pygame.draw.rect(screen, theme["button"], rect, border_radius=12)
        pygame.draw.rect(screen, theme["border"], rect, 3, border_radius=12)
        draw_text(label, chip_font, theme["text_on_button"], rect.centerx, rect.centery)
        if i < len(chips) - 1:
            draw_text("|", font_ui_button, (90, 90, 90), rect.right + chip_gap // 2, rect.centery)
        x += w + chip_gap

    # Hint line - secondary helper text (font_hint)
    hint_cy = chip_cy + chip_h // 2 + 24
    hf = peso_safe(fit_font(hint, [font_hint, font_dashboard_small], inner_w))
    draw_text(hint, hf, (70, 70, 70), panel.centerx, hint_cy)
    return hint_cy + hf.get_height() // 2


NUMBER_BLOCK_HINT = "Then press the SUBMIT button"

def draw_simple_math_game(theme_key, title, current, total, expression, user_answer, panel_w=760):
    """Shared layout for Addition 20 / Addition 100 / Subtraction 100."""
    panel = make_game_panel(theme_key, panel_w, 500, y=50)
    colors = game_colors(theme_key)
    inner_w = panel.width - 2 * GAME_PANEL_PAD

    draw_game_header(panel, theme_key, title, f"Question {current} / {total}")

    q_font = fit_font(expression, [font_question_big, font_question_mid, font_answer_big], inner_w)
    draw_text(expression, q_font, BLACK, panel.centerx, panel.top + 165)

    draw_text("YOUR ANSWER", font_ui_button, colors["accent"], panel.centerx, panel.top + 235)
    answer_box = pygame.Rect(0, 0, 240, 80)
    answer_box.centerx = panel.centerx
    answer_box.top = panel.top + 260
    draw_answer_box(answer_box, user_answer, theme_key)

    draw_instruction_block(panel, theme_key, panel.top + 376,
                           "Place the number blocks in the correct positions",
                           ["TENS", "ONES"], NUMBER_BLOCK_HINT)


# =========================================================
# GAME RESULT (shared)
# =========================================================

def draw_game_result(theme_key, title, message, score, total, message_color=None, extra=None):
    colors = game_colors(theme_key)
    panel = make_game_panel(theme_key, 700, 400)
    inner_w = panel.width - 2 * GAME_PANEL_PAD
    y = panel.top + 60
    if title:
        tf = fit_font(title, [font_topic_title, font_ui_button, font_dashboard], inner_w)
        draw_text(title, tf, colors["title"], panel.centerx, y)
        y += 80
    else:
        y += 10
    mf = fit_font(message, [font_score_big, font_topic_title, font_ui_button], inner_w)
    draw_text(message, mf, message_color or colors["title"], panel.centerx, y)
    y += 85
    score_text = f"SCORE: {score} / {total}"
    sf = fit_font(score_text, [font_score_big, font_topic_title, font_ui_button], inner_w)
    draw_text(score_text, sf, BLACK, panel.centerx, y)
    y += 65
    if extra:
        draw_text(extra, font_ui_button, colors["good"], panel.centerx, y)
        y += 55
    prompt = "PRESS ENTER TO RETURN TO GAME SELECTION"
    pf = fit_font(prompt, [font_instruction, font_dashboard_small], inner_w)
    draw_text(prompt, pf, BLACK, panel.centerx, panel.bottom - GAME_PANEL_PAD - 10)


def result_message(score):
    return "WELL DONE!" if score >= 8 else "GOOD JOB! KEEP PRACTICING!" if score >= 4 else "KEEP PRACTICING!"


# =========================================================
# NUMBER BLOCK TOPICS (CARDS)
# =========================================================

def draw_number_block_topics():
    draw_world_background("NUMBER BLOCK")
    draw_world_particles("NUMBER BLOCK", animation_time)

    draw_world_title("NUMBER BLOCK", "NUMBER BLOCK", 45)
    draw_text("SELECT TOPIC", font_instruction, WORLD_THEMES["NUMBER BLOCK"]["accent"], SCREEN_WIDTH // 2, 85)

    card_w, card_h = 580, 88
    start_y = 120
    gap_y = 14

    for index, topic in enumerate(number_block_topics_data):
        rect = pygame.Rect(0, start_y + index * (card_h + gap_y), card_w, card_h)
        rect.centerx = SCREEN_WIDTH // 2
        draw_card(rect, topic["icon"], topic["title"], topic["subtitle"], selected=(index == selected_number_topic), theme_key="NUMBER BLOCK")

    draw_text("UP / DOWN = Select   |   ENTER = Confirm   |   ESC = Back", font_instruction, BLACK, SCREEN_WIDTH // 2, start_y + len(number_block_topics_data) * (card_h + gap_y) + 15)


# =========================================================
# MONEY TOPICS (CARDS)
# =========================================================

def draw_money_topics():
    draw_world_background("MONEY")
    draw_world_particles("MONEY", animation_time)

    draw_world_title("MONEY", "MONEY", 45)
    draw_text("SELECT TOPIC", font_instruction, WHITE, SCREEN_WIDTH // 2, 85)

    card_w, card_h = 580, 88
    start_y = 120
    gap_y = 14

    for index, topic in enumerate(money_topics_data):
        rect = pygame.Rect(0, start_y + index * (card_h + gap_y), card_w, card_h)
        rect.centerx = SCREEN_WIDTH // 2
        draw_card(rect, topic["icon"], topic["title"], topic["subtitle"], selected=(index == selected_money_topic), theme_key="MONEY")

    draw_text("UP / DOWN = Select   |   ENTER = Confirm   |   ESC = Back", font_instruction, WHITE, SCREEN_WIDTH // 2, start_y + len(money_topics_data) * (card_h + gap_y) + 15)


# =========================================================
# MONEY GAME
# =========================================================

def draw_money_game():

    draw_world_background("MONEY")
    draw_world_particles("MONEY", animation_time)

    panel = make_game_panel("MONEY", 900, 560, y=20)
    colors = game_colors("MONEY")
    inner_w = panel.width - 2 * GAME_PANEL_PAD

    if money_game.mode == "total":
        title = "MONEY - FINDING TOTAL SPENT"
    elif money_game.mode == "change":
        title = "MONEY - FINDING CHANGE"
    elif money_game.mode == "savings":
        title = "MONEY - CALCULATING SAVINGS"
    else:
        title = "MONEY - MAKE THE EXACT AMOUNT"

    draw_game_header(panel, "MONEY", title, f"Question {money_game.question_number} / {money_game.total_questions}")

    # Question text: wrapped and scaled so it always stays inside the panel
    draw_wrapped_fit(money_game.question, [font_ui_button, font_dashboard, font_dashboard_small],
                     BLACK, panel.centerx, panel.top + 112, inner_w, 112)

    draw_text("YOUR ANSWER", font_ui_button, colors["accent"], panel.centerx, panel.top + 250)
    answer_box = pygame.Rect(0, 0, 260, 68)
    answer_box.centerx = panel.centerx
    answer_box.top = panel.top + 274
    draw_answer_box(answer_box, f"\u20b1{money_game.user_answer}", "MONEY")

    # Selected money row (coin + amount, joined by "+")
    row_cy = panel.top + 378
    text_font = peso_safe(font_dashboard)
    if not money_game.selected_money:
        draw_text("No money selected", font_dashboard, BLACK, panel.centerx, row_cy)
    else:
        plus_surface = text_font.render(" + ", True, BLACK)

        def build_items(entries):
            items, total_w = [], 0
            for i, (value, count) in enumerate(entries):
                label = f"\u20b1{value}" + (f" x{count}" if count > 1 else "")
                text_surf = text_font.render(label, True, BLACK)
                img = coin_images.get(value)
                seg = (img.get_width() + 5 if img else 0) + text_surf.get_width()
                if i < len(entries) - 1:
                    seg += plus_surface.get_width()
                total_w += seg
                items.append((img, text_surf))
            return items, total_w

        entries = [(v, 1) for v in money_game.selected_money]
        drawn_items, total_width = build_items(entries)
        if total_width > inner_w:
            # Too many coins to list one by one: group them (e.g. "P20 x2 + P5 x1")
            grouped = {}
            for v in money_game.selected_money:
                grouped[v] = grouped.get(v, 0) + 1
            entries = sorted(grouped.items(), reverse=True)
            drawn_items, total_width = build_items(entries)

        current_x = panel.centerx - total_width // 2
        for i, (img, text_surf) in enumerate(drawn_items):
            if img:
                screen.blit(img, (current_x, row_cy - img.get_height() // 2))
                current_x += img.get_width() + 5
            screen.blit(text_surf, (current_x, row_cy - text_surf.get_height() // 2))
            current_x += text_surf.get_width()
            if i < len(drawn_items) - 1:
                screen.blit(plus_surface, (current_x, row_cy - plus_surface.get_height() // 2))
                current_x += plus_surface.get_width()

    if money_game.mode == "make":
        instruction = "Press the money buttons to make the exact amount"
    else:
        instruction = "Press the correct money buttons to answer the question"
    draw_instruction_block(panel, "MONEY", panel.top + 424, instruction,
                           ["\u20b11", "\u20b15", "\u20b110", "\u20b120"],
                           "Then press the SUBMIT button   |   Maximum answer: \u20b150")


# =========================================================
# MONEY RESULT
# =========================================================

def draw_money_result():
    draw_world_background("MONEY")
    draw_world_particles("MONEY", animation_time)

    draw_game_result("MONEY", "MONEY GAME RESULT", result_message(money_game.score),
                     money_game.score, money_game.total_questions, extra="Great job!")


# =========================================================
# TEACHER: STUDENT PERFORMANCE (existing dashboard logic)
# =========================================================

def topic_of(game_type):
    return game_type.split(" - ")[0].strip() if " - " in game_type else "OTHER"


MONEY_ACTIVITY_NAMES = {
    "TOTAL": "FINDING TOTAL SPENT",
    "CHANGE": "FINDING CHANGE",
    "SAVINGS": "CALCULATING SAVINGS",
    "MAKE": "MAKE THE EXACT AMOUNT",
}


def activity_of(game_type):
    name = game_type.split(" - ", 1)[1].strip() if " - " in game_type else game_type
    if topic_of(game_type) == "MONEY":
        return MONEY_ACTIVITY_NAMES.get(name, name)
    return name


def build_activity_summary(game_type, sessions):
    total_questions = sum(x["total_questions"] for x in sessions)
    total_correct = sum(x["score"] for x in sessions)
    weighted_time = sum(x["average_time"] * x["total_questions"] for x in sessions)
    best = max(sessions, key=lambda x: (x["score"], -x["average_time"]))
    latest = sessions[-1]
    return {
        "game_type": game_type,
        "attempts": len(sessions),
        "best_score": best["score"],
        "best_total": best["total_questions"],
        "average_time": weighted_time / total_questions if total_questions else 0.0,
        "accuracy": (100.0 * total_correct / total_questions) if total_questions else 0.0,
        "status": latest["status"],
        "last_timestamp": latest.get("last_timestamp") or ""
    }


def refresh_detail_rows():
    global dashboard_detail_rows, dashboard_detail_selected, dashboard_detail_scroll

    if dashboard_detail_view == "SUMMARY":
        wanted = dashboard_detail_topics[dashboard_detail_filter]
        rows = [
            build_activity_summary(gt, sessions)
            for gt, sessions in dashboard_detail_summary.items()
            if sessions and (wanted == "ALL" or topic_of(gt) == wanted)
        ]
        rows.sort(key=lambda r: r["game_type"])
    else:
        sessions = dashboard_detail_summary.get(dashboard_detail_activity, [])
        rows = []
        count = len(sessions)
        for number, session in enumerate(reversed(sessions)):
            rows.append({"attempt_number": count - number, **session})

    dashboard_detail_rows = rows
    dashboard_detail_selected = min(dashboard_detail_selected, max(0, len(rows) - 1))
    dashboard_detail_scroll = 0


def open_student_detail(student_id, student_name):
    global dashboard_detail_student_id, dashboard_detail_student_name
    global dashboard_detail_summary, dashboard_detail_view, dashboard_detail_activity
    global dashboard_detail_topics, dashboard_detail_filter, dashboard_detail_selected

    dashboard_detail_student_id = student_id
    dashboard_detail_student_name = student_name
    dashboard_detail_summary = get_student_dashboard_summary(student_id)
    dashboard_detail_view = "SUMMARY"
    dashboard_detail_activity = None
    dashboard_detail_topics = ["ALL"] + sorted({topic_of(gt) for gt in dashboard_detail_summary})
    dashboard_detail_filter = 0
    dashboard_detail_selected = 0
    refresh_detail_rows()


def detail_open_selected():
    global dashboard_detail_view, dashboard_detail_activity, dashboard_detail_selected
    if dashboard_detail_view == "SUMMARY" and dashboard_detail_rows:
        dashboard_detail_activity = dashboard_detail_rows[dashboard_detail_selected]["game_type"]
        dashboard_detail_view = "HISTORY"
        dashboard_detail_selected = 0
        refresh_detail_rows()


def detail_go_back():
    global dashboard_detail_view, dashboard_detail_selected, current_screen
    if dashboard_detail_view == "HISTORY":
        dashboard_detail_view = "SUMMARY"
        dashboard_detail_selected = 0
        refresh_detail_rows()
    else:
        # Back to the section's student list
        load_teacher_section_students()
        current_screen = TEACHER_SECTION


def detail_cycle_filter(step):
    global dashboard_detail_filter, dashboard_detail_selected
    if dashboard_detail_view != "SUMMARY":
        return
    dashboard_detail_filter = (dashboard_detail_filter + step) % len(dashboard_detail_topics)
    dashboard_detail_selected = 0
    refresh_detail_rows()


def dashboard_scroll_clamped(total, visible_items):
    global dashboard_detail_scroll
    if dashboard_detail_selected < dashboard_detail_scroll:
        dashboard_detail_scroll = dashboard_detail_selected
    elif dashboard_detail_selected >= dashboard_detail_scroll + visible_items:
        dashboard_detail_scroll = dashboard_detail_selected - visible_items + 1
    dashboard_detail_scroll = max(0, min(dashboard_detail_scroll, max(0, total - visible_items)))
    return dashboard_detail_scroll


def draw_teacher_student_detail():
    global dashboard_click_targets, dashboard_detail_selected

    draw_world_background("TEACHER")
    theme = WORLD_THEMES["TEACHER"]
    draw_world_title(dashboard_detail_student_name, "TEACHER", 38)
    header = f"STUDENT PERFORMANCE   |   SECTION: {section_title(dashboard_detail_section_name)}"
    draw_text_fit(header, [font_dashboard_small, font_hint], theme["accent"], SCREEN_WIDTH // 2, 74, SCREEN_WIDTH - 60)

    draw_back_button("TEACHER", detail_go_back)

    in_summary = (dashboard_detail_view == "SUMMARY")

    if in_summary:
        draw_text("ACTIVITY SUMMARY", font_instruction, theme["accent"], SCREEN_WIDTH // 2, 96)
        chip_w, chip_h, gap = 190, 32, 12
        total_w = len(dashboard_detail_topics) * chip_w + (len(dashboard_detail_topics) - 1) * gap
        x = (SCREEN_WIDTH - total_w) // 2
        for index, topic in enumerate(dashboard_detail_topics):
            chip = pygame.Rect(x, 112, chip_w, chip_h)
            drawn = draw_game_button(chip, topic, "TEACHER", index == dashboard_detail_filter, font=font_dashboard_small)
            def make_filter(i=index):
                def action():
                    global dashboard_detail_filter, dashboard_detail_selected
                    dashboard_detail_filter = i
                    dashboard_detail_selected = 0
                    refresh_detail_rows()
                return action
            dashboard_click_targets.append((drawn, make_filter()))
            x += chip_w + gap
    else:
        draw_text(f"{activity_of(dashboard_detail_activity)}  -  PREVIOUS ATTEMPTS (newest first)",
                  font_instruction, theme["accent"], SCREEN_WIDTH // 2, 100)

    if not dashboard_detail_rows:
        message = "NO SAVED ATTEMPTS YET" if not dashboard_detail_summary else "NO ACTIVITIES IN THIS TOPIC"
        draw_text(message, button_font, GRAY, SCREEN_WIDTH // 2, 280)
        draw_text("ESC = Back", font_instruction, BLACK, SCREEN_WIDTH // 2, 430)
        return

    visible_items = 4
    total = len(dashboard_detail_rows)
    card_height = 88
    start_y = 156
    scroll = dashboard_scroll_clamped(total, visible_items)

    for i in range(scroll, min(total, scroll + visible_items)):
        row = dashboard_detail_rows[i]
        card = pygame.Rect(0, 0, 880, card_height - 10)
        card.centerx = SCREEN_WIDTH // 2
        card.y = start_y + (i - scroll) * card_height
        selected = (i == dashboard_detail_selected)

        pygame.draw.rect(screen, WHITE, card, border_radius=12)
        pygame.draw.rect(screen, theme["button_selected"] if selected else (200, 204, 214), card,
                          4 if selected else 2, border_radius=12)

        if in_summary:
            best_fraction = row["best_score"] / row["best_total"] if row["best_total"] else 0
            draw_text(topic_of(row["game_type"]), font_dashboard_small, GRAY, card.left + 150, card.top + 18)
            draw_text_fit(activity_of(row["game_type"]), [font_dashboard, font_dashboard_small], theme["accent"], card.left + 150, card.top + 42, 290)
            draw_text(f"ATTEMPTS: {row['attempts']}", font_dashboard_small, BLACK, card.left + 150, card.top + 64)
            draw_progress_bar(card.left + 305, card.top + 18, 190, 16, best_fraction, STATUS_COLORS.get(row["status"], GRAY))
            draw_text(f"BEST SCORE: {row['best_score']} / {row['best_total']}", font_dashboard_small, BLACK, card.left + 400, card.top + 50)
            draw_text(f"AVG TIME: {row['average_time']:.2f} sec", font_dashboard_small, BLACK, card.left + 615, card.top + 24)
            draw_text(f"ACCURACY: {row['accuracy']:.0f}%", font_dashboard_small, BLACK, card.left + 615, card.top + 50)
            draw_status_badge(row["status"], card.left + 800, card.top + 34)
            draw_text("LATEST", font_hint, GRAY, card.left + 800, card.top + 58)

            def make_open(i=i):
                def action():
                    global dashboard_detail_selected
                    dashboard_detail_selected = i
                    detail_open_selected()
                return action
            dashboard_click_targets.append((card.copy(), make_open()))
        else:
            fraction = row["score"] / row["total_questions"] if row["total_questions"] else 0
            accuracy = 100.0 * fraction
            draw_text(f"ATTEMPT #{row['attempt_number']}", font_dashboard, theme["accent"], card.left + 130, card.top + 26)
            draw_text((row.get("last_timestamp") or "")[:16], font_dashboard_small, GRAY, card.left + 130, card.top + 52)
            draw_progress_bar(card.left + 265, card.top + 18, 190, 16, fraction, STATUS_COLORS.get(row["status"], GRAY))
            draw_text(f"SCORE: {row['score']} / {row['total_questions']}", font_dashboard_small, BLACK, card.left + 360, card.top + 50)
            draw_text(f"AVG TIME: {row['average_time']:.2f} sec", font_dashboard_small, BLACK, card.left + 615, card.top + 24)
            draw_text(f"ACCURACY: {accuracy:.0f}%", font_dashboard_small, BLACK, card.left + 615, card.top + 50)
            draw_status_badge(row["status"], card.left + 800, card.top + 38)

            def make_select(i=i):
                def action():
                    global dashboard_detail_selected
                    dashboard_detail_selected = i
                return action
            dashboard_click_targets.append((card.copy(), make_select()))

    if total > visible_items:
        draw_text(f"{scroll + 1}-{min(total, scroll + visible_items)} of {total}", font_hint, GRAY, SCREEN_WIDTH - 70, 96)

    hint = ("UP / DOWN = Select   |   LEFT / RIGHT = Topic Filter   |   ENTER = Previous Attempts   |   ESC = Back"
            if in_summary else "UP / DOWN = Scroll   |   ESC = Back to Summary")
    draw_text(hint, font_hint, BLACK, SCREEN_WIDTH // 2, start_y + visible_items * card_height + 20)


# =========================================================
# PLACEHOLDER GAME SCREENS
# =========================================================

def draw_placeholder(title, description):
    theme_key = title if title in WORLD_THEMES else "HOME"
    draw_world_background(theme_key)
    draw_world_particles(theme_key, animation_time)

    theme = WORLD_THEMES[theme_key]
    draw_world_title(title, theme_key, 80)
    draw_text(theme["title"], font_topic_title, theme["accent"], SCREEN_WIDTH // 2, 135)

    panel = pygame.Rect(0, 0, 640, 140)
    panel.centerx = SCREEN_WIDTH // 2
    panel.y = 190
    pygame.draw.rect(screen, (255, 255, 255), panel, border_radius=16)
    pygame.draw.rect(screen, theme["border"], panel, 4, border_radius=16)

    draw_text(description, button_font, BLACK, panel.centerx, panel.top + 45)
    draw_text("THIS ACTIVITY IS COMING SOON", small_font, theme["accent"], panel.centerx, panel.top + 95)

    draw_text("ESC = Back", font_instruction, BLACK, SCREEN_WIDTH // 2, 420)


# =========================================================
# COUNTING GAME
# =========================================================

def draw_counting_game():
    draw_world_background("NUMBER BLOCK")
    draw_world_particles("NUMBER BLOCK", animation_time)

    panel = make_game_panel("NUMBER BLOCK", 820, 500, y=50)
    colors = game_colors("NUMBER BLOCK")
    inner_w = panel.width - 2 * GAME_PANEL_PAD

    draw_game_header(panel, "NUMBER BLOCK", "COUNTING - FILL IN THE BLANKS",
                     f"Question {counting_game.current_question + 1} / {counting_game.total_questions}")

    numbers = counting_game.question
    slot_w = min(130, inner_w // max(1, len(numbers)))
    start_x = panel.centerx - (len(numbers) - 1) * slot_w // 2
    num_font = fit_font("88", [font_question_big, font_question_mid, font_answer_big], slot_w - 10)
    for index, number in enumerate(numbers):
        x = start_x + index * slot_w
        if number is None:
            draw_text("__", num_font, colors["accent"], x, panel.top + 165)
        else:
            draw_text(str(number), num_font, BLACK, x, panel.top + 165)

    draw_text("YOUR ANSWER", font_ui_button, colors["accent"], panel.centerx, panel.top + 235)
    answer_box = pygame.Rect(0, 0, 240, 80)
    answer_box.centerx = panel.centerx
    answer_box.top = panel.top + 260
    draw_answer_box(answer_box, counting_game.user_answer, "NUMBER BLOCK")

    draw_instruction_block(panel, "NUMBER BLOCK", panel.top + 376,
                           "Place the missing number block in the correct position",
                           ["TENS", "ONES"], NUMBER_BLOCK_HINT)


# =========================================================
# COUNTING RESULT
# =========================================================

def draw_counting_result():
    draw_world_background("NUMBER BLOCK")
    draw_world_particles("NUMBER BLOCK", animation_time)

    draw_game_result("NUMBER BLOCK", None, "WELL DONE!", counting_game.score,
                     counting_game.total_questions, message_color=(40, 140, 60), extra="Great job!")


# =========================================================
# ADDITION UP TO 20
# =========================================================

def draw_addition_game():
    draw_world_background("NUMBER BLOCK")
    draw_world_particles("NUMBER BLOCK", animation_time)

    draw_simple_math_game("NUMBER BLOCK", "ADDITION UP TO 20", addition_game.current_question + 1,
                          addition_game.total_questions,
                          f"{addition_game.num1} + {addition_game.num2} = ?", addition_game.user_answer)


# =========================================================
# ADDITION RESULT
# =========================================================

def draw_addition_result():
    draw_world_background("NUMBER BLOCK")
    draw_world_particles("NUMBER BLOCK", animation_time)

    draw_game_result("NUMBER BLOCK", "ADDITION UP TO 20", result_message(addition_game.score),
                     addition_game.score, addition_game.total_questions)


# =========================================================
# ADDITION UP TO 100
# =========================================================

def draw_addition100_game():
    draw_world_background("NUMBER BLOCK")
    draw_world_particles("NUMBER BLOCK", animation_time)

    draw_simple_math_game("NUMBER BLOCK", "ADDITION UP TO 100", addition100_game.current_question + 1,
                          addition100_game.total_questions,
                          f"{addition100_game.num1} + {addition100_game.num2} = ?", addition100_game.user_answer)


# =========================================================
# ADDITION 100 RESULT
# =========================================================

def draw_addition100_result():
    draw_world_background("NUMBER BLOCK")
    draw_world_particles("NUMBER BLOCK", animation_time)

    draw_game_result("NUMBER BLOCK", "ADDITION UP TO 100", result_message(addition100_game.score),
                     addition100_game.score, addition100_game.total_questions)


# =========================================================
# SUBTRACTION UP TO 100
# =========================================================

def draw_subtraction100_game():
    draw_world_background("NUMBER BLOCK")
    draw_world_particles("NUMBER BLOCK", animation_time)

    draw_simple_math_game("NUMBER BLOCK", "SUBTRACTION UP TO 100", subtraction100_game.current_question + 1,
                          subtraction100_game.total_questions,
                          f"{subtraction100_game.num1} - {subtraction100_game.num2} = ?",
                          subtraction100_game.user_answer)


# =========================================================
# SUBTRACTION RESULT
# =========================================================

def draw_subtraction100_result():
    draw_world_background("NUMBER BLOCK")
    draw_world_particles("NUMBER BLOCK", animation_time)

    draw_game_result("NUMBER BLOCK", "SUBTRACTION UP TO 100", result_message(subtraction100_game.score),
                     subtraction100_game.score, subtraction100_game.total_questions)


# =========================================================
# ESP32 SERIAL INPUT
# =========================================================

try:
    esp32_serial = serial.Serial(
        "/dev/ttyACM0" if sys.platform.startswith("linux") else "COM14",
        115200,
        timeout=0
    )
    print("ESP32 SERIAL CONNECTED: " + ("/dev/ttyACM0" if sys.platform.startswith("linux") else "COM14"))
except:
    esp32_serial = None
    print("WARNING: ESP32 not connected. Hardware inputs disabled.")

esp32_ones = None
esp32_tens = None


def read_esp32_input():
    if esp32_serial is None or esp32_serial.in_waiting <= 0:
        return None
    line = esp32_serial.readline().decode("utf-8", errors="ignore").strip()
    if not line: return None
    print("ESP32 RAW:", line)
    
    if line.startswith("---") or line.startswith("==="): return None
    if line == "UP": return ("BUTTON_UP", None)
    if line == "DOWN": return ("BUTTON_DOWN", None)
    if line == "LEFT": return ("BUTTON_LEFT", None)
    if line == "RIGHT": return ("BUTTON_RIGHT", None)
    if line == "BACK": return ("BUTTON_BACK", None) 
    if line == "SUBMIT PRESSED": return ("BUTTON_SUBMIT", None)

    if line.startswith("MONEY TOTAL:"):
        try: return ("MONEY_TOTAL", int(line.split(":", 1)[1].strip()))
        except ValueError: return None
    if line.startswith("SUBMITTED MONEY INPUT:"):
        try: return ("MONEY_SUBMIT", int(line.split(":", 1)[1].strip()))
        except ValueError: return None
    if line.startswith("NFC TENS:"):
        val = line.split(":", 1)[1].strip()
        if val == "BLANK": return ("TENS_REMOVED", None)
        try: return ("TENS", int(val))
        except ValueError: return None
    if line.startswith("NFC ONES:"):
        val = line.split(":", 1)[1].strip()
        if val == "BLANK": return ("ONES_REMOVED", None)
        try: return ("ONES", int(val))
        except ValueError: return None
    if line.startswith("SUBMITTED NFC INPUT:"):
        try: return ("SUBMITTED", int(line.split(":", 1)[1].strip()))
        except ValueError: return None
    if line == "NO ANSWER INPUT": return ("NO_NUMBER", None)
    return None

def update_nfc_answer(game):
    global esp32_ones, esp32_tens
    if esp32_tens is not None:
        if esp32_ones is not None: game.user_answer = str(esp32_tens) + str(esp32_ones)
        else: game.user_answer = str(esp32_tens)
    elif esp32_ones is not None:
        game.user_answer = str(esp32_ones)
    else:
        game.user_answer = ""

def reset_nfc_input():
    global esp32_ones, esp32_tens
    esp32_ones, esp32_tens = None, None

def post_esp32_key(key):
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, {"key": key, "unicode": ""}))

# =========================================================
# MAIN LOOP
# =========================================================

running = True

while running:

    dt = clock.tick(60) / 1000.0
    animation_time += dt

    # Drain ALL pending ESP32 messages before drawing this frame.
    # This keeps rapid money-button presses from waiting several frames
    # before they appear on the Pygame display.
    while True:
        esp32_input = read_esp32_input()
        if esp32_input is None:
            break

        input_type, number = esp32_input
        if input_type == "BUTTON_UP": post_esp32_key(pygame.K_UP)
        elif input_type == "BUTTON_DOWN": post_esp32_key(pygame.K_DOWN)
        elif input_type == "BUTTON_LEFT": post_esp32_key(pygame.K_LEFT)
        elif input_type == "BUTTON_RIGHT": post_esp32_key(pygame.K_RIGHT)
        elif input_type == "BUTTON_BACK": post_esp32_key(pygame.K_ESCAPE)
        elif input_type == "BUTTON_SUBMIT": post_esp32_key(pygame.K_RETURN)
        elif input_type == "ONES":
            esp32_ones = number
            if current_screen == COUNTING_GAME: update_nfc_answer(counting_game)
            elif current_screen == ADDITION_GAME: update_nfc_answer(addition_game)
            elif current_screen == ADDITION100_GAME: update_nfc_answer(addition100_game)
            elif current_screen == SUBTRACTION100_GAME: update_nfc_answer(subtraction100_game)
        elif input_type == "TENS":
            esp32_tens = number
            if current_screen == COUNTING_GAME: update_nfc_answer(counting_game)
            elif current_screen == ADDITION_GAME: update_nfc_answer(addition_game)
            elif current_screen == ADDITION100_GAME: update_nfc_answer(addition100_game)
            elif current_screen == SUBTRACTION100_GAME: update_nfc_answer(subtraction100_game)
        elif input_type == "ONES_REMOVED":
            esp32_ones = None
            if current_screen == COUNTING_GAME: update_nfc_answer(counting_game)
            elif current_screen == ADDITION_GAME: update_nfc_answer(addition_game)
            elif current_screen == ADDITION100_GAME: update_nfc_answer(addition100_game)
            elif current_screen == SUBTRACTION100_GAME: update_nfc_answer(subtraction100_game)
        elif input_type == "TENS_REMOVED":
            esp32_tens = None
            if current_screen == COUNTING_GAME: update_nfc_answer(counting_game)
            elif current_screen == ADDITION_GAME: update_nfc_answer(addition_game)
            elif current_screen == ADDITION100_GAME: update_nfc_answer(addition100_game)
            elif current_screen == SUBTRACTION100_GAME: update_nfc_answer(subtraction100_game)
        elif input_type == "NUMBER_CLEARED":
            reset_nfc_input()
            if current_screen == COUNTING_GAME: counting_game.user_answer = ""
            elif current_screen == ADDITION_GAME: addition_game.user_answer = ""
            elif current_screen == ADDITION100_GAME: addition100_game.user_answer = ""
            elif current_screen == SUBTRACTION100_GAME: subtraction100_game.user_answer = ""
        elif input_type == "MONEY_TOTAL":
            if current_screen in [
                MONEY_TOTAL_GAME,
                MONEY_CHANGE_GAME,
                MONEY_SAVINGS_GAME,
                MONEY_MAKE_GAME
            ]:
                # ESP32 sends the CURRENT TOTAL.
                # Display it immediately.
                if number == 0:
                    money_game.clear_answer()
                else:
                    money_game.user_answer = number

    # =====================================================
    # PYGAME EVENTS
    # =====================================================

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # Mouse / touch: targets were registered by the last frame's draw functions
            for target_rect, target_action in reversed(dashboard_click_targets):
                if target_rect.collidepoint(event.pos):
                    target_action()
                    break

        elif event.type == pygame.KEYDOWN:

            if current_screen == HOME:
                if event.key == pygame.K_UP:
                    selected_home_option -= 1
                    if selected_home_option < 0: selected_home_option = len(home_menu_options) - 1
                elif event.key == pygame.K_DOWN:
                    selected_home_option += 1
                    if selected_home_option >= len(home_menu_options): selected_home_option = 0
                elif event.key == pygame.K_RETURN:
                    home_activate()

            elif current_screen == SECTION_SELECTION:
                if event.key == pygame.K_ESCAPE:
                    current_screen = HOME
                elif login_sections:
                    if event.key == pygame.K_UP:
                        selected_section_option -= 1
                        if selected_section_option < 0: selected_section_option = len(login_sections) - 1
                    elif event.key == pygame.K_DOWN:
                        selected_section_option += 1
                        if selected_section_option >= len(login_sections): selected_section_option = 0
                    elif event.key == pygame.K_RETURN:
                        choose_section()

            elif current_screen == STUDENT_SELECTION:
                if event.key == pygame.K_UP: move_student_selection(0, -1)
                elif event.key == pygame.K_DOWN: move_student_selection(0, 1)
                elif event.key == pygame.K_LEFT: move_student_selection(-1, 0)
                elif event.key == pygame.K_RIGHT: move_student_selection(1, 0)
                elif event.key == pygame.K_RETURN:
                    activate_student_option()
                elif event.key == pygame.K_ESCAPE:
                    current_screen = SECTION_SELECTION

            elif current_screen == REGISTER_STUDENT:
                if event.key == pygame.K_ESCAPE:
                    student_form_cancel()
                elif event.key in (pygame.K_UP, pygame.K_LEFT):
                    form_focus = (form_focus - 1) % 4
                elif event.key in (pygame.K_DOWN, pygame.K_RIGHT, pygame.K_TAB):
                    form_focus = (form_focus + 1) % 4
                elif event.key == pygame.K_RETURN:
                    student_form_activate()

            elif current_screen == VIRTUAL_KEYBOARD:
                if event.key == pygame.K_UP: move_keyboard_up()
                elif event.key == pygame.K_DOWN: move_keyboard_down()
                elif event.key == pygame.K_LEFT: move_keyboard_left()
                elif event.key == pygame.K_RIGHT: move_keyboard_right()
                elif event.key == pygame.K_RETURN:
                    if select_keyboard_key():
                        finish_keyboard()
                elif event.key == pygame.K_ESCAPE:
                    cancel_keyboard()
                elif event.key == pygame.K_BACKSPACE:
                    keyboard_value = keyboard_value[:-1]
                elif event.unicode and event.unicode.isprintable():
                    # Physical keyboard typing is also accepted
                    if len(keyboard_value) < keyboard_max_len:
                        keyboard_value += event.unicode

            elif current_screen == DELETE_STUDENT:
                if not students:
                    if event.key == pygame.K_ESCAPE: current_screen = STUDENT_SELECTION
                else:
                    if event.key == pygame.K_UP:
                        delete_student_index -= 1
                        if delete_student_index < 0: delete_student_index = len(students) - 1
                    elif event.key == pygame.K_DOWN:
                        delete_student_index += 1
                        if delete_student_index >= len(students): delete_student_index = 0
                    elif event.key == pygame.K_RETURN:
                        student = students[delete_student_index]
                        deleted = delete_student(student[0])
                        load_students()
                        selected_student_option, delete_scroll_offset = 0, 0
                        student_scroll_offset = 0
                        current_screen = STUDENT_SELECTION
                    elif event.key == pygame.K_ESCAPE:
                        current_screen = STUDENT_SELECTION

            elif current_screen == CURRENT_PLAYER:
                if event.key == pygame.K_RETURN:
                    selected_game = 0
                    current_screen = GAME_SELECTION
                elif event.key == pygame.K_ESCAPE:
                    current_screen = STUDENT_SELECTION

            elif current_screen == GAME_SELECTION:
                if event.key == pygame.K_LEFT:
                    if selected_game > 0: selected_game -= 1
                elif event.key == pygame.K_RIGHT:
                    if selected_game < len(game_modules) - 1: selected_game += 1
                elif event.key == pygame.K_UP:
                    if selected_game >= 3: selected_game -= 3
                elif event.key == pygame.K_DOWN:
                    if selected_game + 3 < len(game_modules): selected_game += 3
                elif event.key == pygame.K_RETURN:
                    selected_game_name = game_modules[selected_game]
                    if selected_game_name == "NUMBER BLOCK":
                        selected_number_topic = 0
                        current_screen = NUMBER_BLOCK_TOPICS
                    elif selected_game_name == "MONEY":
                        selected_money_topic = 0
                        current_screen = MONEY_TOPICS
                    elif selected_game_name == "CLOCK":
                        current_screen = CLOCK_GAME
                    elif selected_game_name == "PIZZA FRACTION":
                        current_screen = PIZZA_FRACTION_GAME
                    elif selected_game_name == "MIXED QUICKSTART":
                        current_screen = MIXED_QUICKSTART
                elif event.key == pygame.K_ESCAPE:
                    current_screen = CURRENT_PLAYER

            elif current_screen == NUMBER_BLOCK_TOPICS:
                if event.key == pygame.K_UP:
                    selected_number_topic -= 1
                    if selected_number_topic < 0: selected_number_topic = len(number_block_topics) - 1
                elif event.key == pygame.K_DOWN:
                    selected_number_topic += 1
                    if selected_number_topic >= len(number_block_topics): selected_number_topic = 0
                elif event.key == pygame.K_RETURN:
                    if selected_number_topic == 0:
                        counting_game = CountingGame()
                        reset_nfc_input()
                        current_screen = COUNTING_GAME
                    elif selected_number_topic == 1:
                        addition_game = AdditionGame()
                        reset_nfc_input()
                        current_screen = ADDITION_GAME
                    elif selected_number_topic == 2:
                        addition100_game = Addition100Game()
                        reset_nfc_input()
                        current_screen = ADDITION100_GAME
                    elif selected_number_topic == 3:
                        subtraction100_game = Subtraction100Game()
                        reset_nfc_input()
                        current_screen = SUBTRACTION100_GAME
                elif event.key == pygame.K_ESCAPE:
                    current_screen = GAME_SELECTION

            elif current_screen == COUNTING_GAME:
                if event.key == pygame.K_ESCAPE:
                    current_screen = NUMBER_BLOCK_TOPICS
                    reset_nfc_input()
                elif event.key == pygame.K_BACKSPACE: counting_game.remove_digit()
                elif event.key == pygame.K_RETURN:
                    result = counting_game.submit_answer()
                    if result:
                        save_attempt(
                            student_id=current_player_id, game_type="NUMBER BLOCK - COUNTING",
                            question=result["question"], student_answer=result["user_answer"] if result["user_answer"] is not None else -1,
                            correct_answer=result["correct_answer"], is_correct=result["correct"],
                            response_time=result["time"], difficulty_before=result["difficulty"],
                            difficulty_after=result["next_difficulty"], decision=result["adaptation"],
                            decision_reason=result.get("decision_reason", "System adaptation"),
                            session_id=counting_game.session_id
                        )
                        if counting_game.is_finished(): current_screen = COUNTING_RESULT
                        reset_nfc_input()
                elif event.unicode.isdigit(): counting_game.add_digit(event.unicode)

            elif current_screen == ADDITION_GAME:
                if event.key == pygame.K_ESCAPE:
                    current_screen = NUMBER_BLOCK_TOPICS
                    reset_nfc_input()
                elif event.key == pygame.K_BACKSPACE: addition_game.remove_digit()
                elif event.key == pygame.K_RETURN:
                    result = addition_game.submit_answer()
                    if result:
                        save_attempt(
                            student_id=current_player_id, game_type="NUMBER BLOCK - ADDITION UP TO 20",
                            question=result["question"], student_answer=result["user_answer"] if result["user_answer"] is not None else -1,
                            correct_answer=result["correct_answer"], is_correct=result["correct"],
                            response_time=result["time"], difficulty_before=result["difficulty"],
                            difficulty_after=result["next_difficulty"], decision=result["adaptation"],
                            decision_reason=result.get("decision_reason", "System adaptation"),
                            session_id=addition_game.session_id
                        )
                        if addition_game.is_finished(): current_screen = ADDITION_RESULT
                        reset_nfc_input()
                elif event.unicode.isdigit(): addition_game.add_digit(event.unicode)

            elif current_screen == ADDITION100_GAME:
                if event.key == pygame.K_ESCAPE:
                    current_screen = NUMBER_BLOCK_TOPICS
                    reset_nfc_input()
                elif event.key == pygame.K_BACKSPACE: addition100_game.remove_digit()
                elif event.key == pygame.K_RETURN:
                    result = addition100_game.submit_answer()
                    if result:
                        save_attempt(
                            student_id=current_player_id, game_type="NUMBER BLOCK - ADDITION UP TO 100",
                            question=result["question"], student_answer=result["user_answer"] if result["user_answer"] is not None else -1,
                            correct_answer=result["correct_answer"], is_correct=result["correct"],
                            response_time=result["time"], difficulty_before=result["difficulty"],
                            difficulty_after=result["next_difficulty"], decision=result["adaptation"],
                            decision_reason=result.get("decision_reason", "System adaptation"),
                            session_id=addition100_game.session_id
                        )
                        if addition100_game.is_finished(): current_screen = ADDITION100_RESULT
                        reset_nfc_input()
                elif event.unicode.isdigit(): addition100_game.add_digit(event.unicode)

            elif current_screen == SUBTRACTION100_GAME:
                if event.key == pygame.K_ESCAPE:
                    current_screen = NUMBER_BLOCK_TOPICS
                    reset_nfc_input()
                elif event.key == pygame.K_BACKSPACE: subtraction100_game.remove_digit()
                elif event.key == pygame.K_RETURN:
                    result = subtraction100_game.submit_answer()
                    if result:
                        save_attempt(
                            student_id=current_player_id, game_type="NUMBER BLOCK - SUBTRACTION UP TO 100",
                            question=result["question"], student_answer=result["user_answer"] if result["user_answer"] is not None else -1,
                            correct_answer=result["correct_answer"], is_correct=result["correct"],
                            response_time=result["time"], difficulty_before=result["difficulty"],
                            difficulty_after=result["next_difficulty"], decision=result["adaptation"],
                            decision_reason=result.get("decision_reason", "System adaptation"),
                            session_id=subtraction100_game.session_id
                        )
                        if subtraction100_game.is_finished(): current_screen = SUBTRACTION100_RESULT
                        reset_nfc_input()
                elif event.unicode.isdigit(): subtraction100_game.add_digit(event.unicode)

            elif current_screen in [COUNTING_RESULT, ADDITION_RESULT, ADDITION100_RESULT, SUBTRACTION100_RESULT, MONEY_RESULT]:
                if event.key in [pygame.K_RETURN, pygame.K_ESCAPE]:
                    current_screen = GAME_SELECTION
                    reset_nfc_input()

            elif current_screen == MONEY_TOPICS:
                if event.key == pygame.K_UP:
                    selected_money_topic -= 1
                    if selected_money_topic < 0: selected_money_topic = len(money_topics) - 1
                elif event.key == pygame.K_DOWN:
                    selected_money_topic += 1
                    if selected_money_topic >= len(money_topics): selected_money_topic = 0
                elif event.key == pygame.K_RETURN:
                    if selected_money_topic == 0: money_game = MoneyGame("total"); current_screen = MONEY_TOTAL_GAME
                    elif selected_money_topic == 1: money_game = MoneyGame("change"); current_screen = MONEY_CHANGE_GAME
                    elif selected_money_topic == 2: money_game = MoneyGame("savings"); current_screen = MONEY_SAVINGS_GAME
                    elif selected_money_topic == 3: money_game = MoneyGame("make"); current_screen = MONEY_MAKE_GAME
                elif event.key == pygame.K_ESCAPE:
                    current_screen = GAME_SELECTION

            elif current_screen in [MONEY_TOTAL_GAME, MONEY_CHANGE_GAME, MONEY_SAVINGS_GAME, MONEY_MAKE_GAME]:
                if event.key == pygame.K_RETURN:
                    result = money_game.submit_answer()
                    if result:
                        save_attempt(
                            student_id=current_player_id, game_type=f"MONEY - {money_game.mode.upper()}",
                            question=result["question"], student_answer=result["user_answer"],
                            correct_answer=result["correct_answer"], is_correct=result["correct"],
                            response_time=result["time"], difficulty_before=result["difficulty"],
                            difficulty_after=result["next_difficulty"], decision=result["adaptation"],
                            decision_reason=result.get("decision_reason", ""),
                            session_id=money_game.session_id
                        )
                        if money_game.finished: current_screen = MONEY_RESULT
                elif event.key == pygame.K_ESCAPE:
                    current_screen = GAME_SELECTION

            elif current_screen in [CLOCK_GAME, PIZZA_FRACTION_GAME, MIXED_QUICKSTART]:
                if event.key == pygame.K_ESCAPE:
                    current_screen = GAME_SELECTION

            elif current_screen == TEACHER_LOGIN:
                if event.key == pygame.K_ESCAPE:
                    current_screen = HOME
                elif event.key == pygame.K_UP:
                    teacher_login_field = (teacher_login_field - 1) % 3
                elif event.key in (pygame.K_DOWN, pygame.K_TAB):
                    teacher_login_field = (teacher_login_field + 1) % 3
                elif event.key == pygame.K_BACKSPACE:
                    if teacher_login_field == 0:
                        teacher_username_input = teacher_username_input[:-1]
                    elif teacher_login_field == 1:
                        teacher_password_input = teacher_password_input[:-1]
                elif event.key == pygame.K_RETURN:
                    # On a field: opens the virtual keyboard automatically. On LOGIN: signs in.
                    teacher_login_activate()
                else:
                    if event.unicode and event.unicode.isprintable():
                        if teacher_login_field == 0:
                            if len(teacher_username_input) < 24:
                                teacher_username_input += event.unicode
                        elif teacher_login_field == 1:
                            if len(teacher_password_input) < 24:
                                teacher_password_input += event.unicode

            elif current_screen == TEACHER_DASHBOARD:
                total_rows = len(teacher_sections) + 1     # +1 for "+ CREATE NEW SECTION"
                if event.key == pygame.K_ESCAPE:
                    teacher_logout()
                elif event.key == pygame.K_UP:
                    teacher_dash_sel = (teacher_dash_sel - 1) % total_rows
                elif event.key == pygame.K_DOWN:
                    teacher_dash_sel = (teacher_dash_sel + 1) % total_rows
                elif event.key == pygame.K_RETURN:
                    if teacher_dash_sel == 0:
                        open_create_section()
                    elif teacher_dash_sel - 1 < len(teacher_sections):
                        open_section(teacher_sections[teacher_dash_sel - 1])

            elif current_screen == TEACHER_CREATE_SECTION:
                if event.key == pygame.K_ESCAPE:
                    cancel_create_section()
                elif event.key == pygame.K_UP:
                    create_section_focus = (create_section_focus - 1) % 3
                elif event.key in (pygame.K_DOWN, pygame.K_TAB):
                    create_section_focus = (create_section_focus + 1) % 3
                elif event.key == pygame.K_RETURN:
                    create_section_activate()

            elif current_screen == TEACHER_SECTION:
                if section_confirm:
                    if event.key in (pygame.K_LEFT, pygame.K_UP):
                        section_confirm_yes = True
                    elif event.key in (pygame.K_RIGHT, pygame.K_DOWN):
                        section_confirm_yes = False
                    elif event.key == pygame.K_RETURN:
                        if section_confirm_yes:
                            confirm_delete_section_student()
                        else:
                            cancel_delete_section_student()
                    elif event.key == pygame.K_ESCAPE:
                        cancel_delete_section_student()
                else:
                    total_rows = len(teacher_section_students) + 1   # +1 for "+ ADD STUDENT"
                    if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                        teacher_back_to_dashboard()
                    elif event.key == pygame.K_UP:
                        section_sel = (section_sel - 1) % total_rows
                        section_delete_focus = False
                    elif event.key == pygame.K_DOWN:
                        section_sel = (section_sel + 1) % total_rows
                        section_delete_focus = False
                    elif event.key == pygame.K_RIGHT:
                        if section_sel >= 1:
                            section_delete_focus = True
                    elif event.key == pygame.K_LEFT:
                        section_delete_focus = False
                    elif event.key == pygame.K_DELETE:
                        if section_sel >= 1:
                            ask_delete_student(section_sel - 1)
                    elif event.key == pygame.K_RETURN:
                        if section_sel == 0:
                            open_add_student_teacher()
                        elif section_delete_focus:
                            ask_delete_student(section_sel - 1)
                        else:
                            open_teacher_student(section_sel - 1)

            elif current_screen == TEACHER_ADD_STUDENT:
                if event.key == pygame.K_ESCAPE:
                    student_form_cancel()
                elif event.key == pygame.K_UP:
                    form_focus = (form_focus - 1) % 4
                elif event.key in (pygame.K_DOWN, pygame.K_TAB):
                    form_focus = (form_focus + 1) % 4
                elif event.key == pygame.K_RETURN:
                    student_form_activate()

            elif current_screen == TEACHER_STUDENT_DETAIL:
                if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                    detail_go_back()
                elif event.key == pygame.K_LEFT:
                    detail_cycle_filter(-1)
                elif event.key == pygame.K_RIGHT:
                    detail_cycle_filter(1)
                elif dashboard_detail_rows:
                    if event.key == pygame.K_UP:
                        dashboard_detail_selected = max(0, dashboard_detail_selected - 1)
                    elif event.key == pygame.K_DOWN:
                        dashboard_detail_selected = min(len(dashboard_detail_rows) - 1, dashboard_detail_selected + 1)
                    elif event.key == pygame.K_RETURN:
                        detail_open_selected()

    # =====================================================
    # SCREEN RENDERING
    # =====================================================

    screen.fill(WHITE)
    dashboard_click_targets.clear()      # rebuilt by whichever screen is drawn below

    if current_screen == HOME:
        draw_home()
    elif current_screen == SECTION_SELECTION:
        draw_section_selection()
    elif current_screen == STUDENT_SELECTION:
        draw_student_selection()
    elif current_screen in (REGISTER_STUDENT, TEACHER_ADD_STUDENT):
        draw_student_form()
    elif current_screen == DELETE_STUDENT:
        draw_delete_student()
    elif current_screen == VIRTUAL_KEYBOARD:
        draw_virtual_keyboard()
    elif current_screen == CURRENT_PLAYER:
        draw_current_player()
    elif current_screen == GAME_SELECTION:
        draw_game_selection()
    elif current_screen == NUMBER_BLOCK_TOPICS:
        draw_number_block_topics()
    elif current_screen == MONEY_TOPICS:
        draw_money_topics()
    elif current_screen == COUNTING_GAME:
        draw_counting_game()
    elif current_screen == COUNTING_RESULT:
        draw_counting_result()
    elif current_screen == ADDITION_GAME:
        draw_addition_game()
    elif current_screen == ADDITION_RESULT:
        draw_addition_result()
    elif current_screen == ADDITION100_GAME:
        draw_addition100_game()
    elif current_screen == ADDITION100_RESULT:
        draw_addition100_result()
    elif current_screen == SUBTRACTION100_GAME:
        draw_subtraction100_game()
    elif current_screen == SUBTRACTION100_RESULT:
        draw_subtraction100_result()
    elif current_screen in [MONEY_TOTAL_GAME, MONEY_CHANGE_GAME, MONEY_SAVINGS_GAME, MONEY_MAKE_GAME]:
        draw_money_game()
    elif current_screen == MONEY_RESULT:
        draw_money_result()
    elif current_screen == CLOCK_GAME:
        draw_placeholder("CLOCK", "PRACTICE TELLING TIME")
    elif current_screen == PIZZA_FRACTION_GAME:
        draw_placeholder("PIZZA FRACTION", "LEARN FRACTIONS WITH PIZZA")
    elif current_screen == MIXED_QUICKSTART:
        draw_placeholder("MIXED QUICKSTART", "FAST MIXED MATH CHALLENGE")
    elif current_screen == TEACHER_LOGIN:
        draw_teacher_login()
    elif current_screen == TEACHER_DASHBOARD:
        draw_teacher_dashboard()
    elif current_screen == TEACHER_CREATE_SECTION:
        draw_teacher_create_section()
    elif current_screen == TEACHER_SECTION:
        draw_teacher_section()
    elif current_screen == TEACHER_STUDENT_DETAIL:
        draw_teacher_student_detail()

    pygame.display.flip()

pygame.quit()
sys.exit()