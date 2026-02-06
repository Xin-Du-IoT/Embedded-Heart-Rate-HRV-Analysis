from machine import ADC
from piotimer import Piotimer
from time import ticks_ms, ticks_diff
from fifo import Fifo

class Measurement:
    def __init__(self, adc_pin, fifo_size=500):
        self.adc = ADC(adc_pin) 
        self.fifo = Fifo(fifo_size) 
        self.sample_rate = 250 

    def handler(self, tid):
        self.fifo.put(self.adc.read_u16())

    def detect_peak(self, data, threshold): 
        peaks = []
        last_slope = None
        min_peak_distance = int(0.4 * self.sample_rate) 
        for i in range(1, len(data) - 1):
            prev = data[i - 1]
            curr = data[i]
            slope = curr - prev
            if last_slope is not None:
                if last_slope >= 0 and slope < 0 and prev > threshold:
                    if not peaks or (i - peaks[-1] > min_peak_distance):
                        peaks.append(i)
            last_slope = slope
        return peaks

    def calc_ppi_hr(self, peaks):
        ppi = []
        for i in range(1, len(peaks)):
            interval = (peaks[i] - peaks[i - 1]) / self.sample_rate
            ppi.append(interval)
        hr = [int(60 / p) for p in ppi if p > 0]
        return ppi, hr
    
    def run(self, oled, sw):
        last_update = ticks_ms()
        last_bpm = None
        signal_from_fifo = []
        timer =Piotimer(mode=Piotimer.PERIODIC, freq=self.sample_rate, callback=self.handler) #Piotimer
        
        while True:
            if not sw.fifo.empty() and sw.fifo.get() == 0:
                    break
                
            while (self.fifo.head - self.fifo.tail + self.fifo.size) % self.fifo.size >= 20:
                signal_from_fifo += [self.fifo.get() for _ in range(20)]
                
                if len(signal_from_fifo) > 640:
                    signal_from_fifo = signal_from_fifo[-640:]  

            # ---------- update hr every 5 seconds----------
            if ticks_diff(ticks_ms(), last_update) > 5000 and len(signal_from_fifo) >= 640:
                last_update = ticks_ms()
                max_val = max(signal_from_fifo)
                min_val = min(signal_from_fifo)
                threshold = min_val + 0.75 * (max_val - min_val) # adaptive threshold

                peaks = self.detect_peak(signal_from_fifo, threshold)
                ppi, hr = self.calc_ppi_hr(peaks)

                valid_hr = [bpm for bpm in hr if 30 <= bpm <= 240] # only save the hr between 30 and 240
                last_bpm = valid_hr[-1] if valid_hr else None  # only display last heart rate
                print("HR:", last_bpm, "BPM")

            # ---------- show a live PPG signal ---------- #task4.2
            if len(signal_from_fifo) >= 640:
                oled.fill(0)
                oled.text("HR: {} BPM".format(last_bpm) if last_bpm else "HR: --", 0, 0)
                
                min_val_s = min(signal_from_fifo)  
                max_val_s = max(signal_from_fifo)
                range_val = max_val_s - min_val_s or 1
                
                scaled_y = []
                for i in range(128):
                    segment = signal_from_fifo[i * 5:(i + 1) * 5]
                    avg = int(sum(segment) / len(segment))
                    y = int((avg - min_val_s) * 45 / range_val)
                    y = max(0, min(45, y))
                    y = 18 + (45 - y)
                    scaled_y.append(y)
                
                x_step = 1
                prev_x = 0
                prev_y = scaled_y[0]
                for i,y in enumerate(scaled_y[1:], start=1):
                    x = int(i * x_step)
                    if (0 <= x < 128) and (0 <= y < 64) and (0 <= prev_x < 128) and (0 <= prev_y < 64):
                        oled.line(prev_x, prev_y, x, y, 1)
                    prev_x = x
                    prev_y = y
                    
                oled.show()

        timer.deinit()
        return






