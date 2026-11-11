# ISXMPL4420ex5 - Python UART Current Loop Receiver Using the IS4420 Module
# https://inacks.com/is4420
#
# Wiring (IS4420-M1 pad -> USB-UART adapter):
#     3V3 -> 3.3 V output of the adapter
#     GND -> GND, and the loop power supply 0 V
#     TX  -> RX
#     TX  -> 2.2 kOhm resistor -> 3.3 V, or 5 V if the adapter works at 5 V.
#            The TX output needs this pull-up.
#     SDA, SCL, ADR and SPD -> GND (the I2C-serial interface is not used in
#            this example).
#     CIN -> current loop: the loop current flows into CIN and returns through
#            GND. Never connect the loop supply straight to CIN.
#     The Kappa4420USB board needs none of this wiring: plug it into a USB port.
#
# Set-up (once):   python -m pip install pyserial
# Run:             python ISXMPL4420ex5.py      (Ctrl+C to stop)

"""IS4420PY - console monitor for the IS4420-M1 current loop receiver.

Reads the IS4420-M1 4-20 mA current loop receiver module from a serial (COM)
port and shows the loop current in mA, in % of the 4-20 mA span and the
module temperature, on one console line that updates about every 0.1 s.

    IS4420-M1 module:  https://inacks.com/is4420
    Kappa4420USB:      https://inacks.com/kappa4420usb

The module's TX pin goes to the RX of a USB-UART adapter and needs a pull-up
resistor (wiring: https://inacks.com/is4420). The Kappa4420USB board needs no
wiring: plug it into a USB port.

  1. Lists the COM ports and listens on all of them at once for 0.6 s
     (Bluetooth ports are listed but not opened).
  2. Marks the port where an IS4420 line was heard and suggests it. If none
     was heard, it warns and asks whether TX has its pull-up.
  3. Asks which port to use. Enter takes the suggestion.
  4. Shows mA, %, the module temperature, the reads per second (valid lines
     received per second) and the total number of reads until Ctrl+C. If the
     port is lost (adapter unplugged), it is reopened as soon as it comes back.

The module only transmits on TX: 115200 baud, 8N1, 3.3 V logic, open-drain.
This program only listens: it never sends a byte, and it opens every port
with DTR and RTS off.

Each line is 37 characters and CR LF:
    12.34mA_+052.1%_+025deg_IS4420M1_ver0    current, %, temperature
    EOVERmA_+EOVER%_+025deg_IS4420M1_ver0    over-range
    ERRORmA_+ERROR%_+ERRdeg_IS4420M1_ver0    no measurement
The temperature is the module temperature in whole degrees C. A line counts
only if exactly 37 characters come before its CR LF and every field is in
place; the shorter line of the older 29-character protocol is not accepted.

Needs Python 3.6 or later and pyserial:   python -m pip install pyserial
Run:                                     python ISXMPL4420ex5.py
"""

import re
import sys
import threading
import time
from collections import deque, namedtuple

try:
    import serial
    import serial.tools.list_ports
except ImportError:          # reported by main()
    serial = None

INACKS_URL = "https://inacks.com"
IS4420_URL = "https://inacks.com/is4420"
KAPPA4420USB_URL = "https://inacks.com/kappa4420usb"

BAUD = 115200
LINE_CHARS = 37              # characters before the CR LF
SCAN_LISTEN_S = 0.6          # listening time per port; a line comes about every 103 ms
SCAN_OPEN_ALLOWANCE_S = 1.4  # extra time for slow drivers before a port is left out
NO_DATA_S = 1.0              # this long without a valid line: "no data"
RETRY_S = 1.0                # a lost port is reopened this often
REOPEN_S = 5.0               # a port quiet for this long is closed and reopened
READ_TIMEOUT_S = 0.05
RATE_WINDOW_S = 2.0          # the reads per second are measured over this time

LOGO = (
    " ___ _   _    _    ____ _  ______",
    "|_ _| \\ | |  / \\  / ___| |/ / ___|",
    " | ||  \\| | / _ \\| |   | ' /\\___ \\",
    " | || |\\  |/ ___ \\ |___| . \\ ___) |",
    "|___|_| \\_/_/   \\_\\____|_|\\_\\____/",
)

DETECTED_MARK = "   <-- IS4420 detected!"

_LINE = re.compile(
    rb"(?:(?P<ma>\d\d\.\d\d)mA_(?P<pct>[+-]\d\d\d\.\d)%_(?P<temp>[+-]\d\d\d)deg"
    rb"|(?P<over>EOVER)mA_\+EOVER%_(?P<otemp>[+-]\d\d\d)deg"
    rb"|(?P<error>ERROR)mA_\+ERROR%_\+ERRdeg)"
    rb"_(?P<model>IS4420M1)_ver(?P<ver>\d)"
)

# kind: "value", "over" (over-range) or "error" (no measurement).
# ma and pct are floats for "value", None otherwise. temp is the temperature in
# whole degrees C (int) for "value" and "over", None for "error".
Reading = namedtuple("Reading", "kind ma pct temp model version")

RESCAN = object()            # answer of ask_port(): scan the ports again


# ---------------------------------------------------------------- the line

def parse_line(line):
    """One line without its CR LF -> Reading, or None if it is not a valid IS4420 line."""
    if len(line) != LINE_CHARS:
        return None
    m = _LINE.fullmatch(line)
    if m is None:
        return None
    model = m.group("model").decode("ascii")
    version = "ver" + m.group("ver").decode("ascii")
    if m.group("error"):
        return Reading("error", None, None, None, model, version)
    if m.group("over"):
        return Reading("over", None, None, int(m.group("otemp")), model, version)
    # "+ 0.0" turns a -0.0 into 0.0
    return Reading("value", float(m.group("ma")), float(m.group("pct")) + 0.0,
                   int(m.group("temp")), model, version)


class LineSplitter:
    """Cuts the received bytes into lines at each CR LF."""

    MAX_PENDING = 256        # bytes without a CR LF are dropped beyond this

    def __init__(self):
        self._pending = b""

    def feed(self, data):
        """Add received bytes; return the complete lines, without their CR LF."""
        *lines, self._pending = (self._pending + data).split(b"\r\n")
        if len(self._pending) > self.MAX_PENDING:
            self._pending = b""
        return lines


def format_reading(reading):
    """Text of the live line for one reading: current, % and temperature."""
    if reading.kind == "error":
        return "NO MEASUREMENT"
    if reading.kind == "over":
        main = "OVER-RANGE"
    else:
        main = "{:5.2f} mA   {:6.1f} %".format(reading.ma, reading.pct)
    return "{:<19}   {:3d} C".format(main, reading.temp)


# ---------------------------------------------------------------- ports

def list_serial_ports():
    """The serial ports of this computer, sorted COM1, COM2, ..., COM10."""
    def key(port):
        m = re.match(r"(.*?)(\d+)$", port.device)
        return (m.group(1), int(m.group(2))) if m else (port.device, -1)
    return sorted(serial.tools.list_ports.comports(), key=key)


def is_bluetooth(port):
    """Bluetooth serial ports are not scanned: opening one can block for many seconds."""
    text = "{} {}".format(port.hwid or "", port.description or "").upper()
    return "BTHENUM" in text or "BLUETOOTH" in text


def open_port(name, timeout=READ_TIMEOUT_S):
    """Open a port at 115200 baud, 8N1, with DTR and RTS off."""
    ser = serial.Serial()
    ser.port = name
    ser.baudrate = BAUD
    ser.bytesize = serial.EIGHTBITS
    ser.parity = serial.PARITY_NONE
    ser.stopbits = serial.STOPBITS_ONE
    ser.timeout = timeout
    ser.dtr = False
    ser.rts = False
    ser.open()
    return ser


def close_port(ser):
    if ser is not None:
        try:
            ser.close()
        except Exception:
            pass


def open_error_text(exc):
    """Short reason why a port could not be opened."""
    text = str(exc)
    low = text.lower()
    if "access is denied" in low or "resource busy" in low or "temporarily unavailable" in low:
        return "in use by another program"
    if "filenotfounderror" in low or "cannot find the file" in low or "no such file" in low:
        return "no such port"
    return text


# ---------------------------------------------------------------- scan

def listen_for_line(ser, cancel):
    """Listen for SCAN_LISTEN_S. Returns ("detected", Reading), ("other", None) or ("silent", None)."""
    splitter = LineSplitter()
    heard = False
    end = time.monotonic() + SCAN_LISTEN_S
    while time.monotonic() < end and not cancel.is_set():
        data = ser.read(ser.in_waiting or 1)
        heard = heard or bool(data)
        for line in splitter.feed(data):
            reading = parse_line(line)
            if reading is not None:
                return "detected", reading
    return ("other" if heard else "silent"), None


def probe_port(name, results, cancel):
    """Open one port and listen; put (state, detail) in results[name]."""
    try:
        ser = open_port(name, timeout=0.05)
    except (serial.SerialException, OSError, ValueError) as exc:
        state = "busy" if open_error_text(exc) == "in use by another program" else "failed"
        results[name] = (state, str(exc))
        return
    try:
        results[name] = listen_for_line(ser, cancel)
    except (serial.SerialException, OSError) as exc:
        results[name] = ("failed", str(exc))
    finally:
        close_port(ser)


def scan_ports(ports):
    """Listen on all the ports at once. Returns {port name: (state, detail)}.

    state: "detected" (detail = the first valid Reading), "silent", "other"
    (bytes but no IS4420 line), "busy", "failed", "slow" (did not open in
    time) or "bluetooth" (not scanned).
    """
    results = {}
    cancel = threading.Event()
    threads = []
    for port in ports:
        if is_bluetooth(port):
            results[port.device] = ("bluetooth", None)
            continue
        thread = threading.Thread(target=probe_port, args=(port.device, results, cancel))
        thread.daemon = True     # a port stuck in its driver must not keep the program alive
        thread.start()
        threads.append(thread)
    deadline = time.monotonic() + SCAN_LISTEN_S + SCAN_OPEN_ALLOWANCE_S
    for thread in threads:
        thread.join(max(0.0, deadline - time.monotonic()))
    cancel.set()
    return {port.device: results.get(port.device, ("slow", None)) for port in ports}


# ---------------------------------------------------------------- console

def choose_port():
    """Scan, list the ports, ask. Returns a port name, or None to quit."""
    while True:
        print("Listening on the COM ports for an IS4420 line...")
        ports = list_serial_ports()
        states = scan_ports(ports)
        names = [port.device for port in ports]
        detected = [n for n in names if states[n][0] == "detected"]
        busy = [n for n in names if states[n][0] == "busy"]

        print()
        for number, n in enumerate(names, 1):
            print("  {:2d}  {}{}".format(number, n, DETECTED_MARK if n in detected else ""))
        if names:
            print()
        if not names:
            print("No COM port found. Plug in the USB-UART adapter or the Kappa4420USB.")
        elif len(detected) == 1:
            reading = states[detected[0]][1]
            print("{} {} detected on {}.".format(reading.model, reading.version, detected[0]))
        elif detected:
            print("IS4420 lines on {}.".format(", ".join(detected)))
        else:
            print("WARNING: no IS4420 detected.")
            if busy:
                print("  {} {} in use by another program: close it, then scan again.".format(
                    ", ".join(busy), "is" if len(busy) == 1 else "are"))
            print("  Does the TX pin have its pull-up resistor to 3.3 V? TX is an open-drain")
            print("  output: without the pull-up, no data comes out.")
            print("  Also check 3V3, GND, and TX to the adapter's RX. Wiring: " + IS4420_URL)

        choice = ask_port(names, detected[0] if detected else None)
        if choice is not RESCAN:
            return choice
        print()


def ask_port(names, suggestion):
    """Ask for a port. Returns its name, None to quit, or RESCAN."""
    if suggestion:
        prompt = "Port [Enter = {}, number or name, R = scan again, Q = quit]: ".format(suggestion)
    else:
        prompt = "Port [number or name, Enter = scan again, Q = quit]: "
    while True:
        answer = input(prompt).strip()
        low = answer.lower()
        if not answer:
            return suggestion if suggestion else RESCAN
        if low == "q":
            return None
        if low == "r":
            return RESCAN
        if answer.isdecimal():
            number = int(answer)
            if 1 <= number <= len(names):
                return names[number - 1]
            print("There is no port {} in the list.".format(number))
            continue
        for n in names:
            if n.lower() == low:
                return n
        if re.fullmatch(r"com\d+", low):
            return answer.upper()
        return answer            # not in the list: try it anyway


class LiveLine:
    """One console line, rewritten in place."""

    WIDTH = 72

    def __init__(self):
        self._shown = None

    def show(self, text):
        line = "  {}".format(text).ljust(self.WIDTH)
        if line != self._shown:
            sys.stdout.write("\r" + line)
            sys.stdout.flush()
            self._shown = line


def reading_text(text, rate, total):
    """Live text of a reading, followed by the reads per second and the total reads."""
    rate_text = "{:4.1f}".format(rate) if rate is not None else "   -"
    return "{:<27}   {} reads/s (Total reads: {})".format(text, rate_text, total)


class RateMeter:
    """Valid lines per second over the last RATE_WINDOW_S."""

    def __init__(self):
        self._times = deque()

    def add(self, now):
        self._times.append(now)

    def rate(self, now):
        while self._times and now - self._times[0] > RATE_WINDOW_S:
            self._times.popleft()
        if not self._times:
            return None
        # Lines that arrive in one read share a time stamp: count the lines
        # after the first time stamp over the time they took.
        first = self._times[0]
        span = self._times[-1] - first
        if span <= 0:
            return None
        return sum(1 for t in self._times if t > first) / span


def monitor(name):
    """Show the readings of one port until Ctrl+C.

    Returns True when the user quits, False when the port cannot be opened.
    """
    try:
        ser = open_port(name)
    except (serial.SerialException, OSError, ValueError) as exc:
        print("Could not open {}: {}.".format(name, open_error_text(exc)))
        print()
        return False

    print()
    print("Connected to {}, {} baud 8N1. Ctrl+C to quit.".format(name, BAUD))
    print()
    clock = time.perf_counter   # fine resolution on every system, for the reads per second
    live = LiveLine()
    splitter = LineSplitter()
    meter = RateMeter()
    total = 0                # valid lines received since this port was opened
    text = None              # live text of the last valid line
    last_line = None         # time of the last valid line
    last_byte = None         # time of the last byte received
    unknown_since = None     # start of the bytes received since the last valid line
    since = opened = clock()
    try:
        while True:
            if ser is None:
                live.show("port lost, reconnecting...")
                time.sleep(RETRY_S)
                try:
                    ser = open_port(name)
                except (serial.SerialException, OSError, ValueError):
                    continue
                splitter = LineSplitter()
                meter = RateMeter()
                text = last_line = last_byte = unknown_since = None
                since = opened = clock()

            try:
                data = ser.read(ser.in_waiting or 1)
            except (serial.SerialException, OSError):
                close_port(ser)
                ser = None
                continue

            now = clock()
            if data:
                if last_byte is not None and now - last_byte > NO_DATA_S:
                    unknown_since = None      # bytes again after a silence
                last_byte = now
            new_line = False
            for line in splitter.feed(data):
                reading = parse_line(line)
                if reading is not None:
                    text = format_reading(reading)
                    new_line = True
                    meter.add(now)
                    total += 1
            if new_line:
                last_line = now
                unknown_since = None
            if data and unknown_since is None:
                unknown_since = now

            quiet = now - (last_line if last_line is not None else since)
            if quiet <= NO_DATA_S:
                if text is None:
                    live.show("waiting for data...")
                else:
                    live.show(reading_text(text, meter.rate(now), total))
            elif last_byte is not None and now - last_byte <= NO_DATA_S:
                # Bytes are arriving. Only a second of them without a valid
                # line counts; bytes that have just come back after a silence
                # keep the current text until they make a line.
                if now - unknown_since > NO_DATA_S:
                    live.show("data, but no IS4420 line")
            else:
                live.show("no data")

            # Some drivers go quiet instead of failing when the adapter is
            # unplugged: a quiet port is closed and reopened now and then.
            if quiet > REOPEN_S and now - opened > REOPEN_S:
                close_port(ser)
                try:
                    ser = open_port(name)
                except (serial.SerialException, OSError, ValueError):
                    ser = None
                    continue
                splitter = LineSplitter()
                opened = clock()
    except KeyboardInterrupt:
        pass
    finally:
        close_port(ser)
        print()
    return True


def print_header():
    """The INACKS logo, the program name and the web addresses."""
    rule = "=" * 62
    print(rule)
    print()
    for row in LOGO:
        print("   " + row)
    print()
    print("   IS4420PY - IS4420-M1 console monitor")
    print()
    print("   Website:        " + INACKS_URL)
    print("   IS4420-M1:      " + IS4420_URL)
    print("   Kappa4420USB:   " + KAPPA4420USB_URL)
    print()
    print(rule)
    print()


def pause():
    try:
        input("Press Enter to close.")
    except (KeyboardInterrupt, EOFError):
        pass


def main():
    if serial is None:
        print("This program needs pyserial (the package is pyserial, not serial).")
        print("Install it with:   python -m pip install pyserial")
        pause()
        return 1
    print_header()
    try:
        while True:
            name = choose_port()
            if name is None:
                return 0
            if monitor(name):
                return 0
    except (KeyboardInterrupt, EOFError):
        print()
        return 0


if __name__ == "__main__":
    sys.exit(main())
