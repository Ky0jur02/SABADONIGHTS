import serial
import time

# =========================================================
# SERIAL SETTINGS
# =========================================================

SERIAL_PORT = "COM14"
BAUD_RATE = 115200

ser = serial.Serial(
    SERIAL_PORT,
    BAUD_RATE,
    timeout=0.1
)

time.sleep(2)

# =========================================================
# CURRENT INPUT
# =========================================================

ones = None
tens = None
current_number = None

# =========================================================
# START
# =========================================================

print("ESP32 connected.")
print("Waiting for ESP32 input...")
print("--------------------------------")

# =========================================================
# MAIN LOOP
# =========================================================

while True:

    line = ser.readline().decode(
        "utf-8",
        errors="ignore"
    ).strip()

    if not line:
        continue

    # =====================================================
    # UP
    # =====================================================

    if line == "UP":
        print("BUTTON: UP")
        print("ACTION: MOVE UP")

    # =====================================================
    # DOWN
    # =====================================================

    elif line == "DOWN":
        print("BUTTON: DOWN")
        print("ACTION: MOVE DOWN")

    # =====================================================
    # LEFT
    # =====================================================

    elif line == "LEFT":
        print("BUTTON: LEFT")
        print("ACTION: MOVE LEFT")

    # =====================================================
    # RIGHT
    # =====================================================

    elif line == "RIGHT":
        print("BUTTON: RIGHT")
        print("ACTION: MOVE RIGHT")

    # =====================================================
    # SUBMIT / ENTER
    # =====================================================

    elif line == "SUBMIT BUTTON":

        print("BUTTON: SUBMIT")
        print("ACTION: ENTER / CONFIRM")

    # =====================================================
    # SUBMITTED NUMBER
    # =====================================================

    elif line.startswith("SUBMITTED:"):

        number = line.split(":", 1)[1].strip()

        print("SUBMITTED NUMBER:", number)

        # Reset entered digits after submission
        ones = None
        tens = None
        current_number = None

    # =====================================================
    # ONES NFC
    # =====================================================

    elif line.startswith("ONES UPDATED:"):

        number = int(
            line.split(":", 1)[1].strip()
        )

        ones = number

        print("ONES UPDATED:", ones)

        if tens is not None:
            current_number = (tens * 10) + ones
        else:
            current_number = ones

        print("CURRENT NUMBER:", current_number)

    elif line.startswith("ONES:"):

        number = int(
            line.split(":", 1)[1].strip()
        )

        ones = number

        print("ONES:", ones)

        if tens is not None:
            current_number = (tens * 10) + ones
        else:
            current_number = ones

        print("CURRENT NUMBER:", current_number)

    elif line == "ONES REMOVED":

        ones = None

        if tens is not None:
            current_number = tens
        else:
            current_number = None

        print("ONES REMOVED")

        if current_number is not None:
            print("CURRENT NUMBER:", current_number)

    # =====================================================
    # TENS NFC
    # =====================================================

    elif line.startswith("TENS UPDATED:"):

        number = int(
            line.split(":", 1)[1].strip()
        )

        tens = number

        print("TENS UPDATED:", tens)

        if ones is not None:
            current_number = (tens * 10) + ones
        else:
            current_number = tens

        print("CURRENT NUMBER:", current_number)

    elif line.startswith("TENS:"):

        number = int(
            line.split(":", 1)[1].strip()
        )

        tens = number

        print("TENS:", tens)

        if ones is not None:
            current_number = (tens * 10) + ones
        else:
            current_number = tens

        print("CURRENT NUMBER:", current_number)

    elif line == "TENS REMOVED":

        tens = None

        if ones is not None:
            current_number = ones
        else:
            current_number = None

        print("TENS REMOVED")

        if current_number is not None:
            print("CURRENT NUMBER:", current_number)

    # =====================================================
    # CURRENT NUMBER FROM ESP32
    # =====================================================

    elif line.startswith("CURRENT NUMBER:"):

        number = int(
            line.split(":", 1)[1].strip()
        )

        current_number = number

        print("CURRENT NUMBER:", current_number)

    # =====================================================
    # READY
    # =====================================================

    elif line == "READY FOR NEXT INPUT":

        ones = None
        tens = None
        current_number = None

        print("READY FOR NEXT INPUT")

    # =====================================================
    # OTHER ESP32 MESSAGE
    # =====================================================

    else:

        print("ESP32:", line)