import tkinter as tk
from datetime import datetime

# Font sizes for labels
letra_title = 36
letra_time = 72

class DigitalClock:
    def __init__(self, master):
        self.master = master
        self.master.title("Digital Clock")

        # Set background color for the main window
        self.master.config(bg="#020332")  # Change to your desired color

        # Make the window as wide as possible and minimum height
        self.master.attributes('-fullscreen', True)  # Fullscreen mode
        self.master.overrideredirect(True)  # Removes the title bar for a cleaner look

        # Create a frame to hold the title and time label
        self.frame = tk.Frame(master, bg="#020332")
        self.frame.pack(expand=True)  # Allow the frame to expand and fill the space

        # Define labels for the title and the time display
        self.title_label = tk.Label(self.frame, text="Current Time", font=("Courier", letra_title), fg='white', bg="#020332")  # Change background color
        self.title_label.pack(pady=(20, 0))  # Top padding for title

        self.time_label = tk.Label(self.frame, text="", font=("Courier", letra_time), fg='red', bg="#020332")  # Change background color
        self.time_label.pack(pady=(20, 20))  # Padding for time display

        self.update_clock()  # Start updating the clock

    def update_clock(self):
        now = datetime.now()
        current_time = now.strftime("%H:%M:%S")  # Format the time as HH:MM:SS
        self.time_label.config(text=current_time)  # Update the label with the current time

        # Continue updating every second
        self.master.after(1000, self.update_clock)

# Load the application and start the main loop
if __name__ == "__main__":
    root = tk.Tk()
    clock_app = DigitalClock(root)
    root.mainloop()
