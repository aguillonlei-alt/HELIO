import time
import board
import adafruit_dht
import os
import csv
import serial  # New library for ESP8266 communication
import json    # Used to format data nicely for the ESP8266
import smbus2
from datetime import datetime

# --- Configuration ---
DHT_SENSOR_PIN = board.D#    # GPIO 4 for DHT11 Data
LCD_I2C_ADDRESS = 0x27       # I2C Address for LCD
LOG_FILE_PATH = "/home/pi/helio_data.csv" # Log location (Change if using external SD mount)
LOG_INTERVAL = 3600          # 1 Hour interval

# --- Serial Configuration for ESP8266 ---
# The Pi Zero W uses /dev/serial0 for the GPIO pins 14/15
# Ensure your ESP8266 is running code that listens at this baud rate (usually 9600 or 115200)
SERIAL_PORT = '/dev/serial0' #check muna anong serial port sa raspberry pi 
BAUD_RATE = 9600 

# --- Hardware Initialization ---
dht_device = adafruit_dht.DHT11(DHT_SENSOR_PIN)

# Initialize Serial Connection to ESP8266
##try:
  ##  ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
  ##  ser.flush()
  ##  print(f"Serial connected on {SERIAL_PORT}")
## except Exception as e:
 ##   print(f"Serial Error: {e}")
  ##  ser = None

# --- LCD Class ---
class I2CLCD1602:
    def __init__(self, address, bus_num=1):
        self.address = address
        self.bus = smbus2.SMBus(bus_num)
        self.init_lcd()

    def write_command(self, cmd):
        try: self.bus.write_byte_data(self.address, 0x80, cmd)
        except: pass

    def write_data(self, data):
        try: self.bus.write_byte_data(self.address, 0x40, data)
        except: pass

    def init_lcd(self):
        try:
            time.sleep(0.05)
            self.write_command(0x30); time.sleep(0.005)
            self.write_command(0x30); time.sleep(0.001)
            self.write_command(0x30); self.write_command(0x20)
            self.write_command(0x28); self.write_command(0x0C)
            self.write_command(0x01); time.sleep(0.002)
        except: pass

    def display_string(self, string, line):
        if line == 1: addr = 0x80
        elif line == 2: addr = 0xC0
        else: return
        self.write_command(addr)
        for char in string: self.write_data(ord(char))

try: lcd = I2CLCD1602(LCD_I2C_ADDRESS)
except: lcd = None

# --- Calculations ---
def calculate_heat_index(T_c, R):
    if T_c is None or R is None: return None
    T = T_c * 1.8 + 32
    c1, c2, c3 = -42.379, 2.04901523, 10.14333127
    c4, c5, c6 = -0.22475541, -6.83783e-3, -5.481717e-2
    c7, c8, c9 = 1.22874e-3, 8.5282e-4, -1.99e-6
    HI = c1 + (c2*T) + (c3*R) + (c4*T*R) + (c5*T**2) + (c6*R**2) + \
         (c7*T**2*R) + (c8*T*R**2) + (c9*T**2*R**2)
    return (HI - 32) * (5/9)

# --- Main Logic ---
def main():
    print("HELIO Serial System Started...")
    last_log_time = time.time() - LOG_INTERVAL
    
    while True:
        try:
            temp_c = dht_device.temperature
            hum = dht_device.humidity
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            if temp_c is not None and hum is not None:
                hi_c = calculate_heat_index(temp_c, hum)

                # 1. Display on LCD
                if lcd:
                    lcd.display_string(f"T:{temp_c:.1f}C H:{hum:.0f}%", 1)
                    lcd.display_string(f"HI: {hi_c:.1f} C", 2)

                print(f"[{timestamp}] T:{temp_c} H:{hum} HI:{hi_c:.2f}")

                # 2. Check Timer for Logging & Sending
                if time.time() - last_log_time >= LOG_INTERVAL:
                    
                    # A. Prepare Data Packet
                    data_packet = {
                        "ts": timestamp,
                        "t": round(temp_c, 2),
                        "h": round(hum, 2),
                        "hi": round(hi_c, 2)
                    }
                    
                    # B. Log to CSV (SD Card)
                    # Note: If you mounted your external SD card to /mnt/sdcard, 
                    # change LOG_FILE_PATH to "/mnt/sdcard/helio_data.csv"
                    file_exists = os.path.isfile(LOG_FILE_PATH)
                    with open(LOG_FILE_PATH, 'a', newline='') as f:
                        writer = csv.DictWriter(f, fieldnames=data_packet.keys())
                        if not file_exists: writer.writeheader()
                        writer.writerow(data_packet)
                    print(">> Data Logged to SD")

                    # C. Send to ESP8266 via Serial
                    if ser:
                        # Convert dict to JSON string and add newline (\n)
                        # Newline is crucial for the ESP8266 to know the message is done
                        message = json.dumps(data_packet) + "\n"
                        ser.write(message.encode('utf-8'))
                        print(f">> Sent to ESP8266: {message.strip()}")
                    
                    last_log_time = time.time()

            else:
                print("Sensor Read Failed")

        except RuntimeError:
            time.sleep(2.0)
            continue
        except Exception as e:
            print(f"Error: {e}")
            break

        time.sleep(2)

if __name__ == '__main__':
    main()
