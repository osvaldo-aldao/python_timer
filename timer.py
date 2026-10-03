import json
import sys
import tkinter as tk
import tkinter.font as tkfont
from datetime import datetime
from pathlib import Path
import pandas as pd

# Font sizes for labels
# letra_current = 90
# letra_time = 120
# letra_time2 = 160
# letra_next = 52
# space_on_top = 300
# Change font_scale to fit the screen (e.g. 0.8 for a laptop, 3 for a big display).
# At runtime: Cmd/Ctrl + and Cmd/Ctrl - to resize, Cmd/Ctrl 0 to go back to font_scale.
# The size you pick is saved to timer_settings.json and reused next time.
#
# Test mode, to find the best size before the event: `python timer.py --test`
#   Up / Down (or Left / Right)  step through the sessions
#   P                            show the bigger blinking panic timer
#   Enter                        leave test mode and start the real timer
font_scale = 1.0
settings_file = Path(__file__).with_name("timer_settings.json")
letra_current = 30
letra_time = 70
letra_time2 = 100
letra_next = 24
letra_status = 14
space_on_top = 100
pannic_time = 1  # time in minutes

# Guide printed in the terminal at start
instructions = """
Enea Tech Summit Session Tracker
Mode: {mode}   |   Font scale: {scale:.2f}   |   Agenda: {agenda} ({sessions} sessions)

Flow
  1. Before the event, start in test mode:  python timer.py --test
  2. Step through every session with Up / Down and resize until all text fits.
     Press P to check the bigger blinking panic timer too.
  3. Press Enter to leave test mode and start the real timer.
  4. The size is saved: next time just run  python timer.py

Shortcuts                     Mac                 PC
  Font bigger / smaller       Cmd + / Cmd -       Ctrl + / Ctrl -
  Font back to default        Cmd 0               Ctrl 0
  Reload agenda               Cmd R or F5         Ctrl U or F5
  Test mode only:
    Previous / next session   Up / Down (or Left / Right)
    Panic timer on / off      P
    Start the real timer      Enter
"""

class SeminarTracker:
    def __init__(self, master, agenda_file, testing=False):
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
        self.scale = self.load_saved_scale()
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

        # Wrap long lines so the text never gets wider than the screen
        wrap_width = self.master.winfo_screenwidth() - 100
        for label in (self.current_session_label, self.current_timer_label,
                      self.next_session_label, self.status_label):
            label.config(wraplength=wrap_width, justify="center")

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

        # Test mode keys: step through sessions, preview panic, Enter starts the real timer
        for key in ("<Up>", "<Left>"):
            self.master.bind(key, lambda e: self.step_test_session(-1))
        for key in ("<Down>", "<Right>"):
            self.master.bind(key, lambda e: self.step_test_session(1))
        for key in ("<p>", "<P>"):
            self.master.bind(key, self.toggle_test_panic)
        for key in ("<Return>", "<KP_Enter>"):
            self.master.bind(key, self.end_test_mode)

        self.apply_scale()

        # Take keyboard focus so the shortcuts work without clicking the window first
        self.master.lift()
        self.master.focus_force()

        self.current_session_index = 0
        self.blinking = False  # Control blinking state
        self.blink_job = None  # Pending blink callback, so it can be cancelled
        self.testing = testing
        self.test_index = 0  # Session shown in test mode
        self.test_panic = False  # Show the panic timer in test mode

        self.load_agenda()
        self.print_instructions()
        self.tick()

    def load_agenda(self):
        """Load agenda from Excel file. Keeps the previous agenda if loading fails."""
        agenda = pd.read_excel(self.agenda_file)
        agenda['start_time'] = pd.to_datetime(agenda['start_time'], format='%H:%M:%S')
        agenda['end_time'] = pd.to_datetime(agenda['end_time'], format='%H:%M:%S')
        # Remove stray spaces around names, and show empty cells as blank instead of "nan"
        for column in ('session_name', 'speaker_name'):
            agenda[column] = agenda[column].fillna("").astype(str).str.strip()
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
        self.test_index = min(self.test_index, len(self.agenda) - 1)
        self.refresh()
        self.show_status(f"Agenda reloaded at {datetime.now().strftime('%H:%M:%S')}", "gray")

    def apply_scale(self):
        """Resize all fonts and spacing according to the current scale."""
        for font, size in ((self.font_current, letra_current), (self.font_time, letra_time),
                           (self.font_time2, letra_time2), (self.font_next, letra_next),
                           (self.font_status, letra_status)):
            font.configure(size=max(1, round(size * self.scale)))
        self.next_session_label.pack_configure(pady=(round(space_on_top * self.scale), 20))

    def load_saved_scale(self):
        """Return the font scale saved last time, or font_scale if there is none."""
        try:
            return float(json.loads(settings_file.read_text())["font_scale"])
        except (OSError, ValueError, KeyError, TypeError):
            return font_scale

    def save_scale(self):
        """Remember the font scale for the next start."""
        try:
            settings_file.write_text(json.dumps({"font_scale": round(self.scale, 3)}, indent=2))
        except OSError as e:
            print(f"Could not save settings: {e}")

    def set_scale(self, scale):
        self.scale = min(5.0, max(0.3, scale))
        self.apply_scale()
        self.save_scale()
        self.show_status(f"Font scale: {self.scale:.2f}", "gray")

    def show_status(self, text, color):
        """Show a status message for a few seconds."""
        if self.status_job is not None:
            self.master.after_cancel(self.status_job)
        self.status_label.config(text=text, fg=color)
        self.status_job = self.master.after(4000, self.clear_status)

    def clear_status(self):
        """Hide the status message, or go back to the test mode hint."""
        self.status_job = None
        if self.testing:
            self.status_label.config(
                text=f"TEST MODE - session {self.test_index + 1}/{len(self.agenda)} - "
                     "Up/Down: change session, P: panic timer, Enter: start the timer",
                fg="orange")
        else:
            self.status_label.config(text="")

    def tick(self):
        """Refresh the display once per second for as long as the app runs."""
        try:
            self.refresh()
        finally:
            self.master.after(1000, self.tick)

    def refresh(self):
        if self.testing:
            self.show_test_session()
        else:
            self.update_session()

    def session_text(self, prefix, session):
        start_time = session['start_time'].strftime('%H:%M')
        end_time = session['end_time'].strftime('%H:%M')
        return f"{prefix}: {session['session_name']} by {session['speaker_name']}\nStart: {start_time}, End: {end_time}"

    def show_test_session(self):
        """Show one session as if it were running, with its full length on the timer."""
        session = self.agenda.iloc[self.test_index]
        self.current_session_label.config(text=self.session_text("Current", session))
        minutes, seconds = divmod(int((session['end_time'] - session['start_time']).total_seconds()), 60)
        self.current_timer_label.config(text=f"{minutes:02}:{seconds:02} remaining")
        self.set_blinking(self.test_panic)
        if self.test_index + 1 < len(self.agenda):
            self.next_session_label.config(text=self.session_text("Next", self.agenda.iloc[self.test_index + 1]))
        else:
            self.next_session_label.config(text="End of Seminar")
        if self.status_job is None:
            self.clear_status()

    def step_test_session(self, step):
        if self.testing:
            self.test_index = (self.test_index + step) % len(self.agenda)
            self.show_test_session()

    def toggle_test_panic(self, event=None):
        if self.testing:
            self.test_panic = not self.test_panic
            self.show_test_session()

    def print_instructions(self):
        print(instructions.format(mode="TEST" if self.testing else "RUNNING", scale=self.scale,
                                  agenda=self.agenda_file, sessions=len(self.agenda)), flush=True)

    def end_test_mode(self, event=None):
        if self.testing:
            print(f"Test mode off, timer running with font scale {self.scale:.2f} (saved for next time)", flush=True)
            self.testing = False
            self.test_panic = False
            self.set_blinking(False)
            self.current_session_index = 0
            self.update_session()
            self.show_status(f"Test mode off, timer running (font scale {self.scale:.2f})", "gray")

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

        # Update the current session information
        self.current_session_label.config(text=self.session_text("Current", current_session))

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
                self.next_session_label.config(text=self.session_text("Next", next_session))
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
    app = SeminarTracker(root, "agenda.xlsx", testing="--test" in sys.argv[1:])
    root.mainloop()
