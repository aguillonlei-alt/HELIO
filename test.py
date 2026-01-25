import time
import board
import adafruit_dht

DHT_PIN = board.D22
dht_device = adafruit_dht.DHT11(DHT_PIN)

def calculate_heat_index(T_c, R):
    if T_c is None or R is None: return None
    
    if T_c < 26.7:
        return T_c
        
    T = T_c * 1.8 + 32
    c1, c2, c3 = -42.379, 2.04901523, 10.14333127
    c4, c5, c6 = -0.22475541, -6.83783e-3, -5.481717e-2
    c7, c8, c9 = 1.22874e-3, 8.5282e-4, -1.99e-6
    HI = c1 + (c2*T) + (c3*R) + (c4*T*R) + (c5*T**2) + (c6*R**2) + \
         (c7*T**2*R) + (c8*T*R**2) + (c9*T**2*R**2)
    return (HI - 32) * (5/9)

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
        dht_device.exit()
        time.sleep(1)
        dht_device = adafruit_dht.DHT11(DHT_PIN)

    time.sleep(2.0)
