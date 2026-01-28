import time
import board
import adafruit_dht

DHT_PIN = board.D22
dht_device = adafruit_dht.DHT11(DHT_PIN)

def calculate_heat_index(T_c, R):
    if T_c is None or R is None: return None
    
    T_f = T_c * 1.8 + 32
    
    if T_f < 80:
        return T_c

    c1 = -42.379
    c2 = 2.04901523
    c3 = 10.14333127
    c4 = -0.22475541
    c5 = -6.83783e-3
    c6 = -5.481717e-2
    c7 = 1.22874e-3
    c8 = 8.5282e-4
    c9 = -1.99e-6

    HI = c1 + (c2 * T_f) + (c3 * R) + (c4 * T_f * R) + (c5 * T_f**2) + \
         (c6 * R**2) + (c7 * T_f**2 * R) + (c8 * T_f * R**2) + (c9 * T_f**2 * R**2)

    HI_c = (HI - 32) * 0.55555
    
    return HI_c

print(f"--- DIAGNOSTIC MODE: GPIO {DHT_PIN} ---")
print("Waiting for sensor pulse...")

while True:
    try:
        dht_device.measure()
        
        t = dht_device.temperature
        h = dht_device.humidity
        
        if t is not None and h is not None:
            hi = calculate_heat_index(t, h)
            print(f"SUCCESS! -> Temp: {t}C   Hum: {h}%   Heat Index: {hi:.2f}C")
        
    except RuntimeError as e:
        print(f"Failed: {e}")
        
    except Exception as e:
        print(f"Critical Error: {e}")
        try:
            dht_device.exit()
        except:
            pass
        time.sleep(1)
        dht_device = adafruit_dht.DHT11(DHT_PIN)

    time.sleep(2.0)
