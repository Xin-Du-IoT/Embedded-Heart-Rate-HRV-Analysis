import json
from time import localtime

history_file = "data/history.json"

# get current timestamp as a string
def get_timestamp():
    t = localtime()
    return "{:02d}.{:02d}.{:04d} {:02d}:{:02d}".format(t[2], t[1], t[0], t[3], t[4])

# load saved history records
def load_history():
    with open(history_file, "r") as f:
        return json.load(f)

# save a new entry into history
def save_entry(entry):
    history = load_history()
    history.insert(0, entry)
    history = history[:5]  # keep only the latest 5 entries
    with open(history_file, "w") as f:
        json.dump(history, f)

# show details of a selected entry
def show_detail(oled, entry, sw):
    oled.fill(0)
    oled.text(entry["timestamp"], 0, 0)
    oled.text("HR:  {:.1f}".format(entry["mean_hr"]), 0, 12)
    oled.text("PPI: {:.0f}".format(entry["mean_ppi"] * 1000), 0, 22)
    oled.text("RMSSD:{:.0f}".format(entry["rmssd"] * 1000), 0, 32)
    oled.text("SDNN: {:.0f}".format(entry["sdnn"] * 1000), 0, 42)
    oled.text("SW_2 to exit", 0, 54)
    oled.show()

    # wait for SW_2 button press to return
    while sw.fifo.empty():
        pass
    if sw.fifo.get() == 0:
        return

# show history menu and allow user to browse entries
def show_history(oled, sw, rot):
    history = load_history()
    if not history:
        oled.fill(0)
        oled.text("No history yet", 0, 0)
        oled.show()
        while sw.fifo.empty():
            pass
        return

    index = 0
    max_index = len(history)

    while True:
        oled.fill(0)
        oled.text("Select Entry:", 0, 0)
        for i in range(max_index):
            y = 12 + i * 10
            prefix = ">" if i == index else " "
            oled.text(f"{prefix}Measurement {i+1}", 0, y) 
        oled.show()

        while True:
            if not sw.fifo.empty():
                if sw.fifo.get() == 0:
                    return

            if not rot.fifo.empty():
                action = rot.fifo.get()
                if action == 1:
                    index = (index + 1) % max_index
                    break
                elif action == -1:
                    index = (index - 1 + max_index) % max_index
                    break
                elif action == 0:
                    show_detail(oled, history[index], sw)
                    break