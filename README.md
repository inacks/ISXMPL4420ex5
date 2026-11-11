# Python UART Current Loop Receiver Using the IS4420 Module

<p align="center">
  <a href="https://inacks.com/product/4-20ma-receiver-is4420-m1/">
    <img src="https://inacks.com/wp-content/uploads/IS4420-M1-I2C-UART-Current-Loop-Receiver-1.jpg" alt="IS4420-M1 I2C/UART 4-20 mA current loop receiver module" width="250">
  </a>
</p>

This example is powered by the **IS4420-M1**, a 4-20 mA current loop receiver module that sends every measurement as a line of text on its TX pad. A Python program on your PC reads it through a USB-to-UART adapter, finds the right serial port by itself and shows the current live in the terminal.

No analog circuitry to design. No calibration needed: INACKS calibrates every module at 4 mA and 20 mA.  
The IS4420-M1 contains the complete measurement side of the receiver: the loop current flows into its CIN pad, and about every 100 ms the module sends the current in mA, the percentage of the 4-20 mA span and the module temperature.

Perfect for checking a 4-20 mA transmitter on the bench, for commissioning and troubleshooting a current loop, and for reading pressure, temperature, flow, level and weight transmitters from a PC.

### 🛒 [Buy the IS4420-M1 and learn more](https://inacks.com/product/4-20ma-receiver-is4420-m1/)

---

## What this example does

- Lists the serial ports of your PC and listens on all of them at once for the line that the IS4420-M1 sends, at 115200 baud.
- Marks the port where it heard the module with `<-- IS4420 detected!` and suggests it, so you only press Enter.
- Shows the current, the percentage of the 4-20 mA span and the module temperature on one live line, together with the reads per second and the total number of reads.
- Shows `OVER-RANGE` when the current is above 21.50 mA, and `NO MEASUREMENT` when the module has no valid measurement.
- Warns you when it hears no module, and reconnects by itself if you unplug and plug the adapter again.
- Only listens: it never sends a byte to the module.

To read the module on a Raspberry Pi or an Arduino instead, see [ISXMPL4420ex1](https://github.com/inacks/ISXMPL4420ex1) and [ISXMPL4420ex3](https://github.com/inacks/ISXMPL4420ex3). To read it through the I2C-serial interface, see [ISXMPL4420ex2](https://github.com/inacks/ISXMPL4420ex2) and [ISXMPL4420ex4](https://github.com/inacks/ISXMPL4420ex4).

---

## What you need

- An [IS4420-M1 module](https://inacks.com/product/4-20ma-receiver-is4420-m1/)
- A USB-to-UART adapter with a 3.3 V output and an RX pin
- A 2.2 kΩ resistor
- A 4-20 mA transmitter (2-wire or 3-wire) and its loop power supply, or a 4-20 mA current source
- Python 3.6 or later and pyserial (`python -m pip install pyserial`)

If you have a [Kappa4420USB](https://inacks.com/kappa4420usb), you don't need the adapter, the resistor or the wiring below: it's an isolated USB board built around the IS4420-M1. Plug it into a USB port, connect the loop to it and run the same program.

---

## Wiring

| IS4420-M1 pad | Connect to |
|---|---|
| 3V3 | Adapter 3.3 V output |
| GND | Adapter GND and the loop power supply 0 V |
| TX | Adapter RX, and a 2.2 kΩ pull-up to 3.3 V |
| CIN | Current loop input: the loop current flows into CIN and returns through GND |
| SDA, SCL, SPD, ADR | GND (not used in this example) |

- The IS4420-M1 takes its 3.3 V supply from the adapter.
- The TX pad only pulls the line low, so it needs a pull-up. Pull it up to the voltage your adapter's RX pin works at: 3.3 V for most adapters. The IS4420-M1 accepts 3.3 V or 5 V.
- Connect TX to the **RX** pin of the adapter, not to its TX pin.
- You only use the UART here, so connect SDA, SCL, SPD and ADR to GND. Left open, they could pick up noise.
- With a 2-wire transmitter: loop power supply + to the transmitter +, the transmitter - to CIN, and the loop power supply 0 V to GND.
- With a 3-wire transmitter: the transmitter output to CIN, and the transmitter 0 V and the loop power supply 0 V to GND.
- The current loop input isn't isolated: the loop power supply 0 V, the IS4420-M1 GND and the adapter GND (so your PC) are connected together. If you need the loop isolated from your PC, have a look at the Kappa4420USB.

---

## Running the example

1. Install [Python 3](https://www.python.org/downloads/) if you don't have it. On Windows, tick **Add python.exe to PATH** in the installer.
2. Install pyserial. The package is called `pyserial`, not `serial`:
   ```
   python -m pip install pyserial
   ```
3. Wire the circuit and plug the adapter into your PC.
4. Run the example:
   ```
   python ISXMPL4420ex5.py
   ```
5. The program lists your serial ports, listens on all of them at once for a moment and marks the one where it hears the module. Press Enter to take the suggested port, or type another port's number or name.
6. Press Ctrl+C to stop.

The program starts like this:

```
==============================================================

    ___ _   _    _    ____ _  ______
   |_ _| \ | |  / \  / ___| |/ / ___|
    | ||  \| | / _ \| |   | ' /\___ \
    | || |\  |/ ___ \ |___| . \ ___) |
   |___|_| \_/_/   \_\____|_|\_\____/

   IS4420PY - IS4420-M1 console monitor

   Website:        https://inacks.com
   IS4420-M1:      https://inacks.com/is4420
   Kappa4420USB:   https://inacks.com/kappa4420usb

==============================================================

Listening on the COM ports for an IS4420 line...

   1  COM4
   2  COM5   <-- IS4420 detected!
   3  COM6

IS4420M1 ver0 detected on COM5.
Port [Enter = COM5, number or name, R = scan again, Q = quit]:

Connected to COM5, 115200 baud 8N1. Ctrl+C to quit.

  12.00 mA     50.0 %    26 C    9.7 reads/s (Total reads: 128)
```

The last line is rewritten in place about every 100 ms, so it works like a live display. The port names depend on your system: `COM5` on Windows, `/dev/ttyUSB0` on Linux.

The percentage is the position of the current in the 4-20 mA span:

| Loop current | Percentage |
|:---:|:---:|
| Below 4 mA | Negative |
| 4 mA | 0.0 % |
| 12 mA | 50.0 % |
| 20 mA | 100.0 % |
| 21.50 mA | 109.4 % |
| Above 21.50 mA | `OVER-RANGE` |

---

## How it works

The IS4420-M1 sends one line per measurement, about every 100 ms, at 115200 baud, 8 data bits, no parity, 1 stop bit (8N1):

```
12.34mA_+052.1%_+025deg_IS4420M1_ver0
```

Every line has exactly 37 characters, followed by CR LF (39 bytes in total):

| Characters | Content | Example |
|:---:|---|:---:|
| 1–5 | Current in mA | `12.34` |
| 6–8 | `mA_` | |
| 9–14 | Percentage of the 4-20 mA span, with its sign | `+052.1` |
| 15–16 | `%_` | |
| 17–20 | Module temperature in °C, with its sign | `+025` |
| 21–24 | `deg_` | |
| 25–32 | Model | `IS4420M1` |
| 33–37 | `_ver` and the module revision | `_ver0` |

Two special lines keep the same length:

| Line | Meaning |
|---|---|
| `EOVERmA_+EOVER%_+025deg_IS4420M1_ver0` | The current is above 21.50 mA (over-range). The temperature is still valid. |
| `ERRORmA_+ERROR%_+ERRdeg_IS4420M1_ver0` | The module has no valid measurement. |

The program cuts the received bytes into lines at every CR LF and keeps a line only if exactly 37 characters come before its CR LF and every field is in place:

```python
if len(line) != 37:                  # 37 characters before the CR LF
    return None
m = _LINE.fullmatch(line)            # every field must be where it should be
```

That drops the partial line caught when the port is opened, and any stray byte. The same test is what finds the module at the start: the port where a valid line arrives is the IS4420-M1.

The reads per second are the valid lines received per second, measured over the last 2 seconds. The total counts the valid lines since the port was opened. At 100 ms per measurement you should see about 9.7 reads per second.

---

## Notes

- **Only one program per port:** if the port is in use by another program, such as a terminal, close that program and scan again.
- **Bluetooth ports:** they are listed but not opened, because opening one can block for many seconds.
- **Port names:** the messages say COM ports because that's what Windows calls them. On Linux, you may need to add your user to the `dialout` group (`sudo usermod -aG dialout $USER`) and log in again to open `/dev/ttyUSB0`.
- **Temperature:** it's the temperature inside the module, which can be above the ambient temperature.
- **Protection:** CIN has no protection. Never connect the loop power supply straight to CIN, and never reverse the loop: both destroy the module.

---

## Troubleshooting

| The terminal shows | What to check |
|---|---|
| `WARNING: no IS4420 detected.` | The TX wire on the adapter's RX pin, the 2.2 kΩ pull-up, and the 3V3 and GND connections. The first line comes about 0.6 s after power-up. Then press Enter to scan again. |
| `... in use by another program` | Another program has the port open. Close it and scan again. |
| `waiting for data...` | The port is open but no valid line has arrived yet. |
| `no data` | Nothing has arrived for a second. Check the TX wire, the pull-up and the 3V3 supply (3.3 V). |
| `data, but no IS4420 line` | Bytes arrive, but they aren't an IS4420 line. Check that you chose the right port. |
| `port lost, reconnecting...` | The adapter was unplugged. The program reopens the port by itself when it comes back. |
| About `0.00 mA   -25.0 %` | There's no loop current. Check the CIN connection, the transmitter and its loop power supply, and that the loop power supply 0 V goes to GND. |
| `OVER-RANGE` | The loop current is above 21.50 mA. Check the transmitter. |
| `NO MEASUREMENT` | The module couldn't measure during the last 100 ms. Check the 3V3 supply (3.3 V). |

---

## Get the IS4420-M1

- 🛒 **[Buy the IS4420-M1](https://inacks.com/product/4-20ma-receiver-is4420-m1/)**: I2C/UART 4-20 mA Current Loop Receiver Module
- 🛒 **[Kappa4420USB](https://inacks.com/kappa4420usb)**: isolated USB current loop receiver board built around the IS4420-M1

ℹ️ For more information: [www.inacks.com](https://www.inacks.com)
