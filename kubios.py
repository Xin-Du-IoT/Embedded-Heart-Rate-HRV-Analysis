from machine import ADC
from piotimer import Piotimer
from time import ticks_ms, ticks_diff
from fifo import Fifo
import ujson as json
from mqtt_publish import connect_mqtt  # mqtt connection on port 21883

def collect_ppi(oled, sw, duration=30, sample_rate=250):
    adc = ADC(26)
    fifo = Fifo(500)
    peaks = []
    index = 0
    min_peak_distance = int(0.4 * sample_rate)
    last_peak_index = -1000
    last_slope = None

    def handler(tid):
        fifo.put(adc.read_u16())

    tmr = Piotimer(mode=Piotimer.PERIODIC, freq=sample_rate, callback=handler)
    start = ticks_ms()
    countdown = duration

    while ticks_diff(ticks_ms(), start) < duration * 1000:
        if not sw.fifo.empty() and sw.fifo.get() == 0:
            tmr.deinit()
            return None

        if (fifo.head - fifo.tail + fifo.size) % fifo.size < 250:
            continue

        window = [fifo.get() for _ in range(250)]
        threshold = min(window) + 0.85 * (max(window) - min(window))
        for i in range(1, len(window) - 1):
            prev = window[i - 1]
            curr = window[i]
            slope = curr - prev
            if last_slope is not None and last_slope >= 0 and slope < 0 and prev > threshold:
                abs_index = index + i - len(window)
                if abs_index - last_peak_index > min_peak_distance:
                    peaks.append(abs_index)
                    last_peak_index = abs_index
            last_slope = slope
        index += len(window)

        time_passed = int(ticks_diff(ticks_ms(), start) / 1000)
        if countdown != (duration - time_passed):
            countdown = duration - time_passed
            oled.fill(0)
            oled.text("Collecting...", 0, 0)
            oled.text(f"{countdown}s", 0, 20)
            oled.show()

    tmr.deinit()
    ppi = [int((peaks[i] - peaks[i - 1]) * 1000 / sample_rate) for i in range(1, len(peaks))]
    print("Collected PPI:", ppi)
    return ppi

# send ppi data to kubios cloud service for hrv analysis
def kubios_mode(oled, sw): 
    oled.fill(0)
    oled.text("Collecting...", 0, 0)
    oled.show()

    # ------step1: collect ppi
    ppi = collect_ppi(oled, sw)
    if ppi is None or len(ppi) < 5:
        oled.fill(0)
        oled.text("Cancelled", 0, 0)
        oled.show()
        return

    oled.fill(0)
    oled.text("Sending to cloud", 0, 0)
    oled.show()

    # ------step2: mqtt subscription and callback
    response_data = {}  # dictionary to store analysis results
    result_ready = False 
    
    # mqtt callback to process response message
    def kubios_response(topic, msg):
        nonlocal response_data, result_ready
        print("Received MQTT msg:", msg)
        try:
            data = json.loads(msg.decode())  # decode byte to string, then parse
            response_data = data.get("data", {}).get("analysis", {})
            result_ready = True
        except Exception as e:
            print("Error decoding message:", e)

    mqtt_kubios = connect_mqtt("pico_kubios", port=21883, callback=kubios_response)
    mqtt_kubios.subscribe("kubios-response")

    # -------step3: publish analysis request
    request_payload = {
        "id": 9994,
        "type": "RRI",
        "data": ppi,
        "analysis": {"type": "readiness"}
    }
    mqtt_kubios.publish("kubios-request", json.dumps(request_payload))
    print("Published to kubios-request:", request_payload)

    oled.fill(0)
    oled.text("Waiting result...", 0, 0)
    oled.show()
    
    # ------step 4: wait for response or allow cancel
    while not result_ready:
        if not sw.fifo.empty() and sw.fifo.get() == 0:
            oled.fill(0)
            oled.text("Cancelled", 0, 0)
            oled.show()
            return
        mqtt_kubios.check_msg()

    # ------step 5: display results (sns and pns indices)
    sns = response_data.get("sns_index", 0)
    pns = response_data.get("pns_index", 0)

    oled.fill(0)
    oled.text("Kubios Result", 0, 0)
    oled.text("SNS: {:.2f}".format(sns), 0, 16)
    oled.text("PNS: {:.2f}".format(pns), 0, 32)
    oled.text("SW_2 to exit", 0, 56)
    oled.show()

    print("Final SNS:", sns, "PNS:", pns)
    
    # wait for user to exit by pressing SW_2
    while True:
        if not sw.fifo.empty() and sw.fifo.get() == 0:
            break