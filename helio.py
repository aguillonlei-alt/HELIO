import time
import board
import adafruit_dht
import os
import csv
import requests
import smbus2
from datetime import datetime

# --- Configuration ---
DHT_SENSOR_PIN = board.D17   
LCD_I2C_ADDRESS = 0x27       
LOG_INTERVAL = 3600          
LOG_FILE_PATH = "/home/pi/helio_data_log.csv"
SERVER_URL = "http://YOUR_WEBSITE_OR_IP/api/upload_data.php"

# --- LCD DRIVER CLASS (MOVED TO TOP) ---
# This MUST be defined before we try to use 'lcd = I2CLCD(...)'
class I2CLCD:
    def __init__(self, addr, port=1):
        self.addr = addr
        self.bus = smbus2.SMBus(port)
        self.LCD_WIDTH = 20
        
        # DEFINED FIRST
        self.BACKLIGHT = 0x08 
        self.ENABLE = 0b00000100
        self.E_PULSE = 0.0005
        self.E_DELAY = 0.0005
        
        # Initialization Sequence
        self.lcd_byte(0x33, 0) 
        self.lcd_byte(0x32, 0) 
        self.lcd_byte(0x06, 0) 
        self.lcd_byte(0x0C, 0) 
        self.lcd_byte(0x28, 0) 
        self.lcd_byte(0x01, 0) 
        time.sleep(self.E_DELAY)

    def lcd_byte(self, bits, mode):
        bits_high = mode | (bits & 0xF0) | self.BACKLIGHT
        bits_low = mode | ((bits << 4) & 0xF0) | self.BACKLIGHT
        self.bus.write_byte(self.addr, bits_high)
        self.lcd_toggle_enable(bits_high)
        self.bus.write_byte(self.addr, bits_low)
        self.lcd_toggle_enable(bits_low)

    def lcd_toggle_enable(self, bits):
        time.sleep(self.E_DELAY)
        self.bus.write_byte(self.addr, (bits | self.ENABLE))
        time.sleep(self.E_PULSE)
        self.bus.write_byte(self.addr, (bits & ~self.ENABLE))
        time.sleep(self.E_DELAY)

    def display_string(self, message, line):
        message = message.ljust(self.LCD_WIDTH, " ")
        if line == 1: self.lcd_byte(0x80, 0)
        elif line == 2: self.lcd_byte(0xC0, 0)
        elif line == 3: self.lcd_byte(0x94, 0)
        elif line == 4: self.lcd_byte(0xD4, 0)
        for i in range(self.LCD_WIDTH):
            self.lcd_byte(ord(message[i]), 1)

# --- Initialize LCD (Global) ---
try:
    lcd = I2CLCD(LCD_I2C_ADDRESS)
    lcd.display_string("HELIO System", 1)
    lcd.display_string("Booting...", 2)
except Exception as e:
    lcd = None
    print(f"LCD Init Error: {e}") 

# --- Calculation ---
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
    # A. Setup LCD
    # We create the LCD here, AFTER the class is defined
    try:
        lcd = I2CLCD(LCD_I2C_ADDRESS)
        lcd.display_string("HELIO System", 1)
        lcd.display_string("Booting...", 2)
    except Exception as e:
        lcd = None
        print(f"LCD Init Warning: {e}") 

    print("HELIO Started (Sensor on GPIO 17)...")
    last_action_time = time.time() - LOG_INTERVAL
    
    # Start with no sensor
    dht_device = None

    while True:
        try:
            # B. Self-Healing Sensor Logic
            if dht_device is None:
                try:
                    # FIXED: Uses 'adafruit_dht' to match the import at the top
                    dht_device = adafruit_dht.DHT11(DHT_SENSOR_PIN)
                except Exception as e:
                    print(f"Sensor init failed (Retrying in 2s): {e}")
                    time.sleep(2)
                    continue

            # C. Read Data
            try:
                temp_c = dht_device.temperature
                hum = dht_device.humidity
            except RuntimeError:
                # Common checksum error, just retry
                time.sleep(2.0)
                continue
            except Exception as e:
                # Critical sensor crash
                print(f"Sensor Crash: {e}")
                try:
                    dht_device.exit()
                except Exception:
                    pass # Ignore errors while exiting
                dht_device = None
                time.sleep(1)
                continue

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            if temp_c is not None and hum is not None:
                hi_c = calculate_heat_index(temp_c, hum)

                if lcd:
                    lcd.display_string(f"Temp: {temp_c:.1f} C", 1)
                    lcd.display_string(f"Hum:  {hum:.0f} %", 2)
                    lcd.display_string(f"HI:   {hi_c:.1f} C", 3)
                    lcd.display_string(f"Status: LOGGING", 4)
                
                print(f"[{timestamp}] T:{temp_c} H:{hum} HI:{hi_c:.2f}")

                if time.time() - last_action_time >= LOG_INTERVAL:
                    payload = {
                        "timestamp": timestamp,
                        "temperature": f"{temp_c:.2f}",
                        "humidity": f"{hum:.2f}",
                        "heat_index": f"{hi_c:.2f}"
                    }

                    # Log to CSV
                    file_exists = os.path.isfile(LOG_FILE_PATH)
                    with open(LOG_FILE_PATH, 'a', newline='') as f:
                        writer = csv.DictWriter(f, fieldnames=payload.keys())
                        if not file_exists: writer.writeheader()
                        writer.writerow(payload)
                    print(">> Saved to CSV")

                    # Upload
                    try:
                        requests.post(SERVER_URL, data=payload, timeout=10)
                        print(">> Upload Attempted")
                    except Exception as e:
                        print(f">> Upload Warning: {e}")

                    last_action_time = time.time()
            else:
                print("Reading... (Sensor returned None)")

        except KeyboardInterrupt:
            if lcd: lcd.display_string("System Stopped", 1)
            if dht_device: 
                try: dht_device.exit()
                except: pass
            break
        except Exception as e:
            print(f"Main Loop Error: {e}")
            if dht_device:
                try: dht_device.exit()
                except: pass
            dht_device = None
            time.sleep(2)

        time.sleep(2)

if __name__ == '__main__':
    main()
