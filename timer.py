import tkinter as tk
import tkinter.font as tkfont
from datetime import datetime
import pandas as pd

# Font sizes for labels
# letra_current = 90
# letra_time = 120
# letra_time2 = 160
# letra_next = 52
# space_on_top = 300
# Change font_scale to fit the screen (e.g. 0.8 for a laptop, 3 for a big display).
# At runtime: Cmd/Ctrl + and Cmd/Ctrl - to resize, Cmd/Ctrl 0 to go back to font_scale.
font_scale = 1.0
letra_current = 30
letra_time = 70
letra_time2 = 100
letra_next = 24
letra_status = 14
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

        # Shared fonts, so resizing them updates every label at once
        self.scale = font_scale
        self.font_current = tkfont.Font(family="Courier")
        self.font_time = tkfont.Font(family="Courier")
        self.font_time2 = tkfont.Font(family="Courier")
        self.font_next = tkfont.Font(family="Courier")
        self.font_status = tkfont.Font(family="Courier")

        # Define labels for current and next session
        self.current_session_label = tk.Label(self.frame, text="", font=self.font_current, bg="#020332", fg="white")
        self.current_session_label.pack(pady=(20, 20))  # Padding around current session

        self.current_timer_label = tk.Label(self.frame, text="", font=self.font_time, fg='red', bg="#020332")
        self.current_timer_label.pack(pady=10)  # Padding around timer

        self.next_session_label = tk.Label(self.frame, text="", font=self.font_next, bg="#020332", fg="white")
        self.next_session_label.pack(pady=(space_on_top, 20))  # Padding around next session

        # Small status line to confirm agenda reloads
        self.status_label = tk.Label(self.frame, text="", font=self.font_status, bg="#020332", fg="gray")
        self.status_label.pack(pady=(10, 0))
        self.status_job = None

        # Bind Ctrl+U (plus Cmd+R and F5 on macOS) to update agenda
        for key in ("<Control-u>", "<Control-U>", "<Command-r>", "<Command-R>", "<F5>"):
            self.master.bind(key, self.update_agenda)

        # Bind Cmd/Ctrl + / - / 0 to grow, shrink and reset the font scale
        for mod in ("Command", "Control"):
            for key in ("plus", "equal", "KP_Add"):
                self.master.bind(f"<{mod}-{key}>", lambda e: self.set_scale(self.scale * 1.1))
            for key in ("minus", "KP_Subtract"):
                self.master.bind(f"<{mod}-{key}>", lambda e: self.set_scale(self.scale / 1.1))
            self.master.bind(f"<{mod}-0>", lambda e: self.set_scale(font_scale))

        self.apply_scale()

        # Take keyboard focus so the shortcuts work without clicking the window first
        self.master.lift()
        self.master.focus_force()

        self.current_session_index = 0
        self.blinking = False  # Control blinking state
        self.blink_job = None  # Pending blink callback, so it can be cancelled

        self.load_agenda()
        self.tick()

    def load_agenda(self):
        """Load agenda from Excel file. Keeps the previous agenda if loading fails."""
        agenda = pd.read_excel(self.agenda_file)
        agenda['start_time'] = pd.to_datetime(agenda['start_time'], format='%H:%M:%S')
        agenda['end_time'] = pd.to_datetime(agenda['end_time'], format='%H:%M:%S')
        self.agenda = agenda

    def update_agenda(self, event=None):
        """Reloads the agenda from the Excel file and resets the session tracker."""
        try:
            self.load_agenda()
        except Exception as e:
            print(f"Could not reload agenda, keeping the current one: {e}")
            self.show_status(f"Reload failed: {e}", "orange")
            return
        self.current_session_index = 0
        self.update_session()
        self.show_status(f"Agenda reloaded at {datetime.now().strftime('%H:%M:%S')}", "gray")

    def apply_scale(self):
        """Resize all fonts and spacing according to the current scale."""
        for font, size in ((self.font_current, letra_current), (self.font_time, letra_time),
                           (self.font_time2, letra_time2), (self.font_next, letra_next),
                           (self.font_status, letra_status)):
            font.configure(size=max(1, round(size * self.scale)))
        self.next_session_label.pack_configure(pady=(round(space_on_top * self.scale), 20))

    def set_scale(self, scale):
        self.scale = min(5.0, max(0.3, scale))
        self.apply_scale()
        self.show_status(f"Font scale: {self.scale:.2f}", "gray")

    def show_status(self, text, color):
        """Show a status message for a few seconds."""
        if self.status_job is not None:
            self.master.after_cancel(self.status_job)
        self.status_label.config(text=text, fg=color)
        self.status_job = self.master.after(4000, lambda: self.status_label.config(text=""))

    def tick(self):
        """Refresh the display once per second for as long as the app runs."""
        try:
            self.update_session()
        finally:
            self.master.after(1000, self.tick)

    def update_session(self):
        now = datetime.now()  # Keep the actual time with seconds and microseconds

        # Skip sessions that have already ended
        while self.current_session_index < len(self.agenda):
            end_time_with_date = datetime.combine(now.date(), self.agenda.iloc[self.current_session_index]['end_time'].time())
            if end_time_with_date > now:
                break
            self.current_session_index += 1

        if self.current_session_index >= len(self.agenda):
            # End of the seminar
            self.set_blinking(False)
            self.current_session_label.config(text="Seminar is over")
            self.current_timer_label.config(text="")
            self.next_session_label.config(text="")
            return

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

        if remaining_time_until_start.total_seconds() > 0:
            # Display countdown until the session starts
            self.set_blinking(False)
            minutes, seconds = divmod(int(remaining_time_until_start.total_seconds()), 60)
            self.current_timer_label.config(text=f"Starts in: {minutes:02}:{seconds:02}")

            # Clear next session label while waiting for current session to start
            self.next_session_label.config(text="")
        else:
            # Session ongoing, calculate remaining time
            remaining_time = end_time_with_date - now

            # Update countdown timer with seconds
            minutes, seconds = divmod(int(remaining_time.total_seconds()), 60)
            self.current_timer_label.config(text=f"{minutes:02}:{seconds:02} remaining")

            # Blink when panic_time is reached
            self.set_blinking(remaining_time.total_seconds() < 60 * pannic_time)

            # Show next session
            if next_session is not None:
                next_start_time = next_session['start_time'].strftime('%H:%M')
                next_end_time = next_session['end_time'].strftime('%H:%M')
                next_session_text = f"Next: {next_session['session_name']} by {next_session['speaker_name']}\nStart: {next_start_time}, End: {next_end_time}"
                self.next_session_label.config(text=next_session_text)
            else:
                self.next_session_label.config(text="End of Seminar")

    def set_blinking(self, on):
        """Turn panic blinking on or off, starting at most one blink loop."""
        if on and not self.blinking:
            self.blinking = True
            self.current_timer_label.config(font=self.font_time2, fg='yellow')
            self.blink_job = self.master.after(500, self.blink_text)
        elif not on:
            self.blinking = False
            if self.blink_job is not None:
                self.master.after_cancel(self.blink_job)
                self.blink_job = None
            self.current_timer_label.config(font=self.font_time, fg='red')

    def blink_text(self):
        if self.blinking:
            # Toggle the timer label's text color
            current_color = self.current_timer_label.cget("fg")
            new_color = "yellow" if current_color == "red" else "red"
            self.current_timer_label.config(fg=new_color)
            self.blink_job = self.master.after(500, self.blink_text)


# Load the agenda CSV and start the application
if __name__ == "__main__":
    root = tk.Tk()
    app = SeminarTracker(root, "agenda.xlsx")  # Replace with your actual file path
    root.mainloop()
