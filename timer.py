import tkinter as tk
from datetime import datetime
import pandas as pd

# Font sizes for labels
letra_current = 72
letra_time = 90
letra_time2 = 120
letra_next = 48
space_on_top = 100
pannic_time = 1  # time in minutes

class SeminarTracker:
    def __init__(self, master, agenda_file):
        self.master = master
        self.agenda_file = agenda_file
        self.master.title("Enea Tech Summit Session Tracker")

        # Set background color for the main window
        self.master.config(bg="#020332")  # Change to your desired color

        # Create a frame to hold the content and center it vertically
        self.frame = tk.Frame(master, bg="#020332")
        self.frame.pack(expand=True)  # This allows the frame to expand and fill the space
        
        # Make the window as wide as possible and minimum height
        #self.master.attributes('-fullscreen', True)  # Fullscreen mode
        #self.master.overrideredirect(True)  # Removes the title bar for a cleaner look

        # Define labels for current and next session
        self.current_session_label = tk.Label(self.frame, text="", font=("Courier", letra_current), bg="#020332", fg="white")
        self.current_session_label.pack(pady=(20, 20))  # Padding around current session

        self.current_timer_label = tk.Label(self.frame, text="", font=("Courier", letra_time), fg='red', bg="#020332")
        self.current_timer_label.pack(pady=10)  # Padding around timer

        self.next_session_label = tk.Label(self.frame, text="", font=("Courier", letra_next), bg="#020332", fg="white")
        self.next_session_label.pack(pady=(100, 20))  # Padding around next session

        # Bind Ctrl+U to update agenda
        self.master.bind("<Control-u>", self.update_agenda)

        self.current_session_index = 0
        self.blinking = False  # Control blinking state

        self.load_agenda()
        self.update_session()

    def load_agenda(self):
        """Load agenda from Excel file."""
        self.agenda = pd.read_excel(self.agenda_file)
        self.agenda['start_time'] = pd.to_datetime(self.agenda['start_time'], format='%H:%M:%S')
        self.agenda['end_time'] = pd.to_datetime(self.agenda['end_time'], format='%H:%M:%S')

    def update_agenda(self, event=None):
        """Reloads the agenda from the Excel file and resets the session tracker."""
        self.current_session_index = 0
        self.load_agenda()
        self.update_session(force_update=True)

    def update_session(self, force_update=False):
        now = datetime.now()  # Keep the actual time with seconds and microseconds

        if self.current_session_index < len(self.agenda):
            current_session = self.agenda.iloc[self.current_session_index]
            next_session = self.agenda.iloc[self.current_session_index + 1] if self.current_session_index + 1 < len(self.agenda) else None
            
            # Display start and end times without seconds
            start_time = current_session['start_time'].strftime('%H:%M')
            end_time = current_session['end_time'].strftime('%H:%M')
            session_name = current_session['session_name']
            speaker_name = current_session['speaker_name']

            # Update the current session information
            self.current_session_label.config(text=f"Current: {session_name} by {speaker_name}\nStart: {start_time}, End: {end_time}")

            # Calculate remaining time until the session starts
            start_time_with_date = datetime.combine(now.date(), current_session['start_time'].time())
            remaining_time_until_start = start_time_with_date - now

            if remaining_time_until_start.total_seconds() > 0 or force_update:
                # Display countdown until the session starts
                minutes, seconds = divmod(int(remaining_time_until_start.total_seconds()), 60)
                self.current_timer_label.config(text=f"Starts in: {minutes:02}:{seconds:02}")

                # Clear next session label while waiting for current session to start
                self.next_session_label.config(text="")
                if not force_update:
                    self.master.after(1000, self.update_session)

            else:
                # Session ongoing, calculate remaining time
                end_time_with_date = datetime.combine(now.date(), current_session['end_time'].time())
                remaining_time = end_time_with_date - now

                if remaining_time.total_seconds() > 0:
                    # Update countdown timer with seconds
                    minutes, seconds = divmod(int(remaining_time.total_seconds()), 60)
                    self.current_timer_label.config(text=f"{minutes:02}:{seconds:02} remaining")

                    # Start blinking when panic_time is reached
                    if remaining_time.total_seconds() < 60 * pannic_time:
                        self.blinking = True
                        self.blink_text()
                        self.current_timer_label.config(font=("Courier", letra_time2), fg='yellow')
                    else:
                        self.blinking = False
                        self.current_timer_label.config(font=("Courier", letra_time), fg='red')

                    # Show next session
                    if next_session is not None:
                        next_start_time = next_session['start_time'].strftime('%H:%M')
                        next_end_time = next_session['end_time'].strftime('%H:%M')
                        next_session_text = f"Next: {next_session['session_name']} by {next_session['speaker_name']}\nStart: {next_start_time}, End: {next_end_time}"
                        self.next_session_label.config(text=next_session_text)
                    else:
                        self.next_session_label.config(text="End of Seminar")

                    if not force_update:
                        self.master.after(1000, self.update_session)
                else:
                    # Move to the next session
                    self.current_session_index += 1
                    self.update_session()
        else:
            # End of the seminar
            self.current_session_label.config(text="Seminar is over")
            self.current_timer_label.config(text="")
            self.next_session_label.config(text="")

    def blink_text(self):
        if self.blinking:
            # Toggle the timer label's text color
            current_color = self.current_timer_label.cget("fg")
            new_color = "yellow" if current_color == "red" else "red"
            self.current_timer_label.config(fg=new_color)
            self.master.after(500, self.blink_text)


# Load the agenda CSV and start the application
if __name__ == "__main__":
    root = tk.Tk()
    app = SeminarTracker(root, "agenda.xlsx")  # Replace with your actual file path
    root.mainloop()
