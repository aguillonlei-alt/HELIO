import time
import board
import adafruit_dht
import os
import csv
import requests  # Uses Pi's internal Wi-Fi to send data
import smbus2
from datetime import datetime

# --- Configuration ---
DHT_SENSOR_PIN = board.D4    # GPIO 4 (Pin 7)
LCD_I2C_ADDRESS = 0x27       # Standard I2C address
LOG_INTERVAL = 3600          # Log and Upload every 1 Hour (3600 seconds)

# FILE PATH: 
# If using the Pi's internal SD card, keep as is.
# If using your external SPI SD card module, change this to your mount path (e.g., "/mnt/mysdcard/helio.csv")
LOG_FILE_PATH = "/home/pi/helio_data_log.csv"

# SERVER URL:
# Replace this with the actual URL of your pre-made web server's upload script
SERVER_URL = "http://YOUR_WEBSITE_OR_IP/api/upload_data.php"

# --- Hardware Initialization ---
# Initialize DHT11
dht_device = adafruit_dht.DHT11(DHT_SENSOR_PIN)

# Initialize LCD (I2C)
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

try:
    lcd = I2CLCD1602(LCD_I2C_ADDRESS)
except:
    lcd = None
    print("LCD not found. Check wiring.")

# --- Calculation Function ---
def calculate_heat_index(T_c, R):
    """NOAA Heat Index Equation"""
    if T_c is None or R is None: return None
    T = T_c * 1.8 + 32  # Convert to Fahrenheit
    
    c1, c2, c3 = -42.379, 2.04901523, 10.14333127
    c4, c5, c6 = -0.22475541, -6.83783e-3, -5.481717e-2
    c7, c8, c9 = 1.22874e-3, 8.5282e-4, -1.99e-6

    HI = c1 + (c2*T) + (c3*R) + (c4*T*R) + (c5*T**2) + (c6*R**2) + \
         (c7*T**2*R) + (c8*T*R**2) + (c9*T**2*R**2)
    
    return (HI - 32) * (5/9) # Return Celsius

# --- Main Logic ---
def main():
    print("HELIO (Wi-Fi Edition) Started...")
    last_action_time = time.time() - LOG_INTERVAL
    
    while True:
        try:
            # 1. Read Sensors
            temp_c = dht_device.temperature
            hum = dht_device.humidity
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            if temp_c is not None and hum is not None:
                # 2. Process
                hi_c = calculate_heat_index(temp_c, hum)

                # 3. Display
                if lcd:
                    lcd.display_string(f"T:{temp_c:.1f}C H:{hum:.0f}%", 1)
                    lcd.display_string(f"HI: {hi_c:.1f} C", 2)
                
                print(f"[{timestamp}] T:{temp_c} H:{hum} HI:{hi_c:.2f}")

                # 4. Log and Upload (Timer Check)
                if time.time() - last_action_time >= LOG_INTERVAL:
                    
                    payload = {
                        "timestamp": timestamp,
                        "temperature": f"{temp_c:.2f}",
                        "humidity": f"{hum:.2f}",
                        "heat_index": f"{hi_c:.2f}"
                    }

                    # A. Save to CSV
                    file_exists = os.path.isfile(LOG_FILE_PATH)
                    with open(LOG_FILE_PATH, 'a', newline='') as f:
                        writer = csv.DictWriter(f, fieldnames=payload.keys())
                        if not file_exists: writer.writeheader()
                        writer.writerow(payload)
                    print(">> Saved to CSV")

                    # B. Upload to Server
                    try:
                        response = requests.post(SERVER_URL, data=payload, timeout=10)
                        if response.status_code == 200:
                            print(f">> Upload Success: {response.text}")
                        else:
                            print(f">> Upload Error: {response.status_code}")
                    except Exception as e:
                        print(f">> Upload Failed: {e}")

                    last_action_time = time.time()

            else:
                print("Sensor read error. Retrying...")

        except RuntimeError:
            time.sleep(2.0)
            continue
        except Exception as e:
            print(f"Critical Error: {e}")
            break

        time.sleep(2)

if __name__ == '__main__':
    main()
