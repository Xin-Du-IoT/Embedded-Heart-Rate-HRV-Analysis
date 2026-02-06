from machine import ADC
from piotimer import Piotimer
from time import ticks_ms, ticks_diff, sleep
from fifo import Fifo
import json
from history import save_entry, get_timestamp

class HRVAnalyzer:
    def __init__(self, adc_pin=26, window_size=250):
        self.adc = ADC(adc_pin)  
        self.sample_rate = 250
        self.window_size = window_size 
        self.fifo = Fifo(500)  
        self.peaks = []  # list to store peak indices
        self.index = 0  # Global index of samples read from FIFO

    def handler(self, tid):
        self.fifo.put(self.adc.read_u16()) 

    def calculate_hrv(self, peaks):
        if len(peaks) < 2:
            return [], 0, 0, 0, 0
        ppi = [(peaks[i] - peaks[i - 1])/ self.sample_rate for i in range(1, len(peaks))]
        
        filtered_ppi = [x for x in ppi if 0.6 < x < 1.2]  # filter out abnormal value
        
        if len(filtered_ppi) < 2:
            return [], [], 0, 0, 0, 0
        
        mean_ppi = sum(filtered_ppi) / len(filtered_ppi)
        diffs = [filtered_ppi[i+1] - filtered_ppi[i] for i in range(len(filtered_ppi)-1)]
        squared_diffs = [d ** 2 for d in diffs]
        rmssd = (sum(squared_diffs) / len(squared_diffs))**0.5 if squared_diffs else 0
        sdnn = (sum((x - mean_ppi) ** 2 for x in filtered_ppi)/len(filtered_ppi))**0.5 if filtered_ppi else 0
        mean_hr = 60 / mean_ppi if mean_ppi > 0 else 0

        return mean_ppi, mean_hr, rmssd, sdnn
        
    def run(self, oled, sw, duration=30, mqtt_client=None):
        last_slope = None
        timer = Piotimer(mode=Piotimer.PERIODIC, freq=self.sample_rate, callback=self.handler)  # Piotimer
        min_peak_distance = int(0.4 * self.sample_rate)  
        start = ticks_ms()
        last_peak_index = -1000  # initialize as far away
        countdown = duration

        oled.fill(0)
        oled.text("Sampling HRV...", 0, 0)
        oled.show()

        while ticks_diff(ticks_ms(), start) < duration * 1000:
            # allow user to cancel with SW_2
            if not sw.fifo.empty():
                if sw.fifo.get() == 0:
                    timer.deinit()
                    oled.fill(0)
                    oled.text("HRV Cancelled", 0, 20)
                    oled.show()
                    sleep(0.5)
                    return

            # wait until at least 1 second of data (250 samples)
            if (self.fifo.head - self.fifo.tail + self.fifo.size) % self.fifo.size < self.window_size:
                continue

            window = [self.fifo.get() for _ in range(250)]
            threshold = min(window) + 0.85 * (max(window) - min(window))
            for i in range(1, len(window) - 1):
                prev = window[i - 1]
                curr = window[i]
                slope = curr - prev
                if last_slope is not None and last_slope >= 0 and slope < 0 and prev > threshold:
                    abs_index = self.index + i - len(window) # absolute sample index
                    if abs_index - last_peak_index > min_peak_distance:
                        self.peaks.append(abs_index)
                        last_peak_index = abs_index
                last_slope = slope
            self.index += len(window)

            # countdown display update
            time_passed = int(ticks_diff(ticks_ms(), start) / 1000)
            if countdown != (duration - time_passed):
                countdown = duration - time_passed
                oled.fill(0)
                oled.text("Collecting...", 0, 0)
                oled.text(f"{countdown}s", 0, 20)
                oled.show()

        timer.deinit()

        # final hrv results
        mean_ppi, mean_hr, rmssd, sdnn = self.calculate_hrv(self.peaks)

        def fmt(x):
            return "{:.1f}".format(x)

        # display results
        oled.fill(0)
        oled.text("HRV Results", 0, 0)
        oled.text("PPI: " + fmt(mean_ppi * 1000), 0, 12)
        oled.text("HR:  " + fmt(mean_hr), 0, 22)
        oled.text("RMSSD: " + fmt(rmssd * 1000), 0, 32)
        oled.text("SDNN:  " + fmt(sdnn * 1000), 0, 42)
        oled.text("SW_2 to exit", 0, 54)
        oled.show()
        
        print("--- HRV Results ---")
        print("Mean PPI (ms):", fmt(mean_ppi * 1000))
        print("Mean HR (bpm):", fmt(mean_hr))
        print("RMSSD (ms):", fmt(rmssd * 1000))
        print("SDNN (ms):", fmt(sdnn * 1000))
        
        if mqtt_client:
            payload = json.dumps({
                "mean_ppi":  fmt(mean_ppi * 1000),
                "mean_hr": fmt(mean_hr),
                "rmssd": fmt(rmssd * 1000),
                "sdnn": fmt(sdnn * 1000)
            })
            mqtt_client.publish("group5/hrv", payload)
            print(" HRV data sent via MQTT")
        
        # Save result to history
        entry = {
            "timestamp": get_timestamp(),
            "mean_hr": mean_hr,
            "mean_ppi": mean_ppi,
            "rmssd": rmssd,
            "sdnn": sdnn
        }
        save_entry(entry)
        
        while True:
            if not sw.fifo.empty() and sw.fifo.get() == 0:
                break
