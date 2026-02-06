from machine import Pin, I2C
from time import ticks_ms, ticks_diff
from ssd1306 import SSD1306_I2C
from fifo import Fifo
from hr_measure import Measurement
from hrv_analyze import HRVAnalyzer
from history import show_history
from mqtt_publish import mqtt_client
from kubios import kubios_mode

# OLED initialization
i2c = I2C(1, scl=Pin(15), sda=Pin(14), freq=400000)
oled = SSD1306_I2C(128, 64, i2c)

# Menu 
menu = ["Measure HR", "HRV Analysis", "History", "Kubios Cloud"]
selected = 0
        
# Rotary Encoder
class Encoder:
    def __init__(self, pin_a, pin_b, button_pin):
        self.a = Pin(pin_a, Pin.IN, Pin.PULL_UP)
        self.b = Pin(pin_b, Pin.IN, Pin.PULL_UP)
        self.button = Pin(button_pin, Pin.IN, Pin.PULL_UP)

        self.fifo = Fifo(20, "i")
        self.last_press = 0
        self.debounce = 500

        self.a.irq(trigger=Pin.IRQ_RISING, handler=self.rotation_handler)
        self.button.irq(trigger=Pin.IRQ_FALLING, handler=self.button_handler)

    def rotation_handler(self, pin):
        if self.b.value():
            self.fifo.put(-1)
        else:
            self.fifo.put(1)

    def button_handler(self, pin):
        now = ticks_ms()
        if ticks_diff(now, self.last_press) > self.debounce:
            self.last_press = now
            self.fifo.put(0)  # 0 means button press

rot = Encoder(10, 11, 12)

# Start and stop buttons
class Sw:
    def __init__(self, sw_0, sw_2):
        self.sw0 = Pin(sw_0, Pin.IN, Pin.PULL_UP)
        self.sw2 = Pin(sw_2, Pin.IN, Pin.PULL_UP)

        self.fifo = Fifo(10, "i")
        self.last_press = 0
        self.debounce = 500

        self.sw2.irq(trigger=Pin.IRQ_FALLING, handler=self.stop_handler)

    def stop_handler(self, sw2):
        now = ticks_ms()
        if ticks_diff(now, self.last_press) > self.debounce:
            self.last_press = now
            self.fifo.put(0)  # 0 means SW2 pressed

sw = Sw(9, 7)  # sw0 for Start, sw2 for Stop

hr = Measurement(26)     # Hr measure instance
hrv = HRVAnalyzer(26)    # Hrv analyze instance

# Display startup screen
def show_start_screen():
    oled.fill(0)
    oled.text("Welcome!", 30, 10)
    oled.text("Press SW_0", 0, 30)
    oled.text("to begin check ", 0, 45)
    oled.show()

    start_time = ticks_ms()
    while True:
        now = ticks_ms()
        if sw.sw0.value() == 0 and ticks_diff(now, start_time) > 100: #press the button
            break

# Draw menu on OLED
def draw_menu(selected_index):
    oled.fill(0)
    for i, item in enumerate(menu):
        y = i * 12
        if i == selected_index: # if i is selected
            oled.fill_rect(0, y, 128, 12, 1) # draws a black rectangle to highlight it.
            oled.text(item, 2, y + 2, 0)
        else:
            oled.text(item, 2, y + 2, 1)
    oled.show()

# Stop screen
def show_stop_screen():
    oled.fill(0)
    oled.text("Program Stopped", 0, 10)
    oled.text("SW_0 to Restart", 0, 30)
    oled.show()

# Show selected item temporarily
def show_selected(item):
    oled.fill(0)
    oled.text(item, 0, 10)
    oled.text("Starting", 0, 30)
    oled.show()

# ========== Run the program ===========
show_start_screen() # show the welcome page, wait user to press the start button
draw_menu(selected) # show the menu, highlight the selected option
in_menu = True # for encoder which only works in the menu

while True:
    if not rot.fifo.empty():
        action = rot.fifo.get()

        if in_menu:  # in_menu = True , rotate the encoder to select the options
            if action == 1: # move down
                selected = (selected + 1) % len(menu)
                draw_menu(selected)
            elif action == -1: # move up
                selected = (selected - 1) % len(menu)
                draw_menu(selected)
            elif action == 0:  # press the rotator to select the option 
                show_selected(menu[selected])
                in_menu = False  #

                if selected == 0: # to measure
                    hr.run(oled, sw) 
                    show_stop_screen() # if the sw_2 is pressed
                    while sw.sw0.value(): # wait until press sw_0 and release
                        pass
                    draw_menu(selected)
                    in_menu = True # continue selecting
                    
                elif selected == 1:
                    hrv.run(oled, sw, mqtt_client=mqtt_client)#replace None with   
                    show_stop_screen()
                    while sw.sw0.value():
                        pass
                    draw_menu(selected)
                    in_menu = True
                    
                elif selected == 2:
                    show_history(oled, sw, rot)  
                    draw_menu(selected)
                    in_menu = True
                    
                elif selected == 3:
                    kubios_mode(oled, sw) 
                    show_stop_screen()
                    while sw.sw0.value():
                        pass
                    draw_menu(selected)
                    in_menu = True
                              
    if not sw.fifo.empty(): 
        event = sw.fifo.get()
        if event == 0:
            show_stop_screen()
            while sw.sw0.value():  # wait until sw_0 is released
                pass
            draw_menu(selected)
            in_menu = True

