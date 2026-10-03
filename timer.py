import json
import sys
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox
from datetime import datetime
from pathlib import Path
import pandas as pd

# Keyboard shortcuts (same on Mac and PC):
#   + / -      timer bigger / smaller
#   Up / Down  agenda bigger / smaller
#   0          reset both sizes to font_scale and agenda_scale below
#   F5, Ctrl R reload the agenda file
#   Ctrl O     open a different agenda file
#
# Test mode, to find the best size before the event: `python timer.py --test`
#   Left / Right  step through the sessions
#   P             show the bigger blinking panic timer
#   Enter         leave test mode and start the real timer
#
# Default font scales to fit the screen (e.g. 0.8 for a laptop, 3 for a big display).
# The sizes you pick are saved to timer_settings.json and reused next time.
#
# Agenda file: `python timer.py my_agenda.xlsx`, or start without a file name to pick one
# (the last one used is preselected; cancel to use agenda.xlsx next to timer.py).
font_scale = 1.0
agenda_scale = 1.0
settings_file = Path(__file__).with_name("timer_settings.json")
default_agenda_file = Path(__file__).with_name("agenda.xlsx")

# Font sizes at scale 1.0
letra_current = 30
letra_time = 60
letra_time2 = 80
letra_status = 14
letra_agenda = 16
letra_watermark = 20

watermark_text = "Technology Summit"  # Shown in title_color in the lower left corner

# Shortcut list printed in the terminal at start
shortcuts = (
    ("Action", "Keys (Mac and PC)"),
    ("Timer bigger / smaller", "+ / −: main keyboard (= also works) or numeric keypad"),
    ("Agenda bigger / smaller", "↑ / ↓"),
    ("Reset both sizes", "0"),
    ("Reload agenda", "F5 or Ctrl R (also Cmd R on the Mac)"),
    ("Open another agenda", "Ctrl O (also Cmd O on the Mac)"),
    ("Test mode only:", ""),
    ("  Previous / next session", "← / →"),
    ("  Panic timer on / off", "P"),
    ("  Start the real timer", "Enter"),
)
pannic_time = 3  # time in minutes

# Colors
bg_color = "#020332"
agenda_header_color = "#8a8fd1"
agenda_past_color = "#5a5e8f"
agenda_current_bg = "#1f2a7a"
divider_color = "#2a2c6b"
title_color = "#2EC4B6"  # Teal for the Current / Start / End titles


class SessionInfo(tk.Frame):
    """Session name, speaker and times, with the titles shown in title_color."""

    def __init__(self, master, font):
        super().__init__(master, bg=bg_color)
        self.font = font
        self.wrap_width = 1

        self.name_row = tk.Frame(self, bg=bg_color)
        self.name_row.pack()
        self.prefix_label = self.make_label(self.name_row, title_color)
        self.name_label = self.make_label(self.name_row, "white")
        self.name_label.config(justify="center")

        self.times_row = tk.Frame(self, bg=bg_color)
        self.start_title = self.make_label(self.times_row, title_color, "Start: ")
        self.start_label = self.make_label(self.times_row, "white")
        self.end_title = self.make_label(self.times_row, title_color, "End: ")
        self.end_label = self.make_label(self.times_row, "white")
        for label in (self.start_title, self.start_label, self.end_title, self.end_label):
            label.pack(side="left")

    def make_label(self, parent, color, text=""):
        return tk.Label(parent, text=text, font=self.font, bg=bg_color, fg=color, padx=0, bd=0)

    def set_wrap(self, width):
        """Wrap the name so the text never gets wider than width."""
        self.wrap_width = max(1, width)
        prefix_width = self.font.measure(self.prefix_label.cget("text")) if self.prefix_label.winfo_manager() else 0
        self.name_label.config(wraplength=max(1, self.wrap_width - prefix_width))

    def show(self, prefix, session):
        """Show a session, e.g. "Current: <name> by <speaker>" and its start and end times."""
        self.prefix_label.config(text=f"{prefix}: ")
        self.name_label.config(text=f"{session['session_name']} by {session['speaker_name']}")
        self.name_label.pack(side="left", anchor="n")
        # before= keeps the title in front of the name after show_text() has hidden it
        self.prefix_label.pack(side="left", anchor="n", before=self.name_label)
        self.set_wrap(self.wrap_width)
        self.start_label.config(text=session['start_time'].strftime('%H:%M') + ", ")
        self.end_label.config(text=session['end_time'].strftime('%H:%M'))
        # Small gap above the times, half the font size so it grows with the font scale
        self.times_row.pack(pady=(self.font.cget("size") // 2, 0))

    def show_text(self, text):
        """Show a plain message (or nothing) instead of a session."""
        self.prefix_label.pack_forget()
        self.times_row.pack_forget()
        self.name_label.config(text=text)
        self.name_label.pack(side="left", anchor="n")
        self.set_wrap(self.wrap_width)


class SeminarTracker:
    def __init__(self, master, agenda_file=None, testing=False):
        self.master = master
        self.settings = self.load_settings()
        self.master.title("Enea Tech Summit Session Tracker")

        # Set background color for the main window
        self.master.config(bg=bg_color)

        # Start with the window filling the screen
        self.master.geometry(f"{master.winfo_screenwidth()}x{master.winfo_screenheight()}+0+0")
        #self.master.attributes('-fullscreen', True)  # Fullscreen mode
        #self.master.overrideredirect(True)  # Removes the title bar for a cleaner look

        # Show the window before asking for the agenda, so the picker appears in front of it
        if not agenda_file:
            self.master.update()
            self.master.lift()
            self.master.focus_force()
            agenda_file = self.ask_agenda_file() or default_agenda_file
        self.agenda_file = agenda_file

        # Shared fonts, so resizing them updates every label at once
        self.scale = self.setting_number("font_scale", font_scale)
        self.agenda_scale = self.setting_number("agenda_scale", agenda_scale)
        self.font_current = tkfont.Font(family="Courier")
        self.font_time = tkfont.Font(family="Courier")
        self.font_time2 = tkfont.Font(family="Courier")
        self.font_status = tkfont.Font(family="Courier")
        self.font_watermark = tkfont.Font(family="Courier", weight="bold")
        self.font_agenda = tkfont.Font(family="Courier")
        self.font_agenda_bold = tkfont.Font(family="Courier", weight="bold")

        # Split the window: timer on the left 2/3, agenda on the right 1/3
        self.master.grid_rowconfigure(0, weight=1)
        self.master.grid_columnconfigure(0, weight=2, uniform="split")
        self.master.grid_columnconfigure(2, weight=1, uniform="split")

        timer_side = tk.Frame(master, bg=bg_color)
        timer_side.grid(row=0, column=0, sticky="nsew")
        tk.Frame(master, bg=divider_color, width=2).grid(row=0, column=1, sticky="ns")
        agenda_side = tk.Frame(master, bg=bg_color)
        agenda_side.grid(row=0, column=2, sticky="nsew")

        # Timer side: a frame centered vertically holding the current session and timer
        self.frame = tk.Frame(timer_side, bg=bg_color)
        self.frame.place(relx=0.5, rely=0.5, anchor="center")
        timer_side.bind("<Configure>", lambda e: self.fit_timer_width(e.width - 40))

        # Watermark in the lower left corner
        tk.Label(timer_side, text=watermark_text, font=self.font_watermark, bg=bg_color,
                 fg=title_color).place(x=20, rely=1.0, y=-20, anchor="sw")

        self.current_session_label = SessionInfo(self.frame, self.font_current)
        self.current_session_label.pack(pady=(20, 20))  # Padding around current session

        self.current_timer_label = tk.Label(self.frame, text="", font=self.font_time, fg='red', bg=bg_color)
        self.current_timer_label.pack(pady=10)  # Padding around timer

        # Small status line to confirm agenda reloads and scale changes
        self.status_label = tk.Label(self.frame, text="", font=self.font_status, bg=bg_color, fg="gray")
        self.status_label.pack(pady=(10, 0))
        self.status_job = None

        # Agenda side: a scrollable table that keeps the current session in view
        self.agenda_canvas = tk.Canvas(agenda_side, bg=bg_color, highlightthickness=0)
        self.agenda_canvas.pack(fill="both", expand=True, padx=20, pady=20)
        self.agenda_table = tk.Frame(self.agenda_canvas, bg=bg_color)
        self.agenda_window = self.agenda_canvas.create_window(0, 0, window=self.agenda_table, anchor="nw")
        self.agenda_table.bind("<Configure>", lambda e: self.agenda_canvas.config(scrollregion=self.agenda_canvas.bbox("all")))
        self.agenda_canvas.bind("<Configure>", self.fit_agenda_width)
        self.agenda_rows = []
        self.highlighted_index = None

        # Shortcuts that work the same on Mac and PC (Ctrl U and Cmd R / Cmd O kept as extras)
        modifiers = ("Control", "Command") if sys.platform == "darwin" else ("Control",)
        for mod in modifiers:
            for letter in ("r", "R"):
                self.master.bind(f"<{mod}-{letter}>", self.update_agenda)
            for letter in ("o", "O"):
                self.master.bind(f"<{mod}-{letter}>", self.open_agenda)
        for key in ("<F5>", "<Control-u>", "<Control-U>"):
            self.master.bind(key, self.update_agenda)

        # + / - scale the timer, Up / Down scale the agenda, 0 resets both
        for key in ("plus", "equal", "KP_Add"):
            self.master.bind(f"<{key}>", lambda e: self.set_scale(self.scale * 1.1))
        for key in ("minus", "KP_Subtract"):
            self.master.bind(f"<{key}>", lambda e: self.set_scale(self.scale / 1.1))
        self.master.bind("<Up>", lambda e: self.set_agenda_scale(self.agenda_scale * 1.1))
        self.master.bind("<Down>", lambda e: self.set_agenda_scale(self.agenda_scale / 1.1))
        for key in ("0", "KP_0"):
            self.master.bind(f"<Key-{key}>", lambda e: self.reset_scales())

        # Test mode keys: step through sessions, preview panic, Enter starts the real timer
        self.master.bind("<Left>", lambda e: self.step_test_session(-1))
        self.master.bind("<Right>", lambda e: self.step_test_session(1))
        for key in ("<p>", "<P>"):
            self.master.bind(key, self.toggle_test_panic)
        for key in ("<Return>", "<KP_Enter>"):
            self.master.bind(key, self.end_test_mode)

        self.testing = testing
        self.test_index = 0  # Session shown in test mode
        self.test_panic = False  # Show the panic timer in test mode

        self.apply_scale()
        self.print_shortcuts()

        # Take keyboard focus so the shortcuts work without clicking the window first
        self.master.lift()
        self.master.focus_force()

        self.current_session_index = 0
        self.blinking = False  # Control blinking state
        self.blink_job = None  # Pending blink callback, so it can be cancelled

        try:
            self.load_agenda()
        except Exception as e:
            messagebox.showerror("Agenda", f"Could not load {self.agenda_file}:\n{e}")
            raise SystemExit(1)
        self.save_settings()
        self.tick()

    def load_agenda(self):
        """Load agenda from Excel file. Keeps the previous agenda if loading fails."""
        agenda = pd.read_excel(self.agenda_file)
        agenda['start_time'] = pd.to_datetime(agenda['start_time'], format='%H:%M:%S')
        agenda['end_time'] = pd.to_datetime(agenda['end_time'], format='%H:%M:%S')
        for column in ('session_name', 'speaker_name'):
            agenda[column] = agenda[column].fillna("").astype(str).str.strip()
        self.agenda = agenda
        self.build_agenda_table()

    def build_agenda_table(self):
        """Create one row per session with start time, topic and speaker."""
        for widget in self.agenda_table.winfo_children():
            widget.destroy()
        self.agenda_rows = []
        self.highlighted_index = None

        for column, title in enumerate(("Start", "Topic", "Speaker")):
            tk.Label(self.agenda_table, text=title, font=self.font_agenda_bold, bg=bg_color,
                     fg=agenda_header_color, anchor="w").grid(row=0, column=column, sticky="ew", padx=6, pady=(0, 8))

        for i, session in enumerate(self.agenda.itertuples()):
            cells = [tk.Label(self.agenda_table, text=text, font=self.font_agenda, bg=bg_color, fg="white",
                              anchor="w", justify="left")
                     for text in (session.start_time.strftime('%H:%M'), session.session_name, session.speaker_name)]
            for column, cell in enumerate(cells):
                cell.grid(row=i + 1, column=column, sticky="nsew", padx=6, pady=2, ipady=2)
            self.agenda_rows.append(cells)

        self.agenda_table.grid_columnconfigure(1, weight=1)
        self.agenda_table.grid_columnconfigure(2, weight=1)
        self.fit_agenda_width()

    def fit_agenda_width(self, event=None):
        """Make the table as wide as the agenda panel, wrapping long topics and speakers."""
        width = self.agenda_canvas.winfo_width()
        if width <= 1:
            return
        self.agenda_canvas.itemconfigure(self.agenda_window, width=width)
        time_width = self.font_agenda.measure("00:00") + 24
        text_width = max(50, (width - time_width) // 2 - 16)
        for cells in self.agenda_rows:
            cells[1].config(wraplength=text_width)
            cells[2].config(wraplength=text_width)

    def highlight_agenda(self):
        """Grey out finished sessions, highlight the current one and keep it in view."""
        if self.highlighted_index == self.current_session_index:
            return
        self.highlighted_index = self.current_session_index

        for i, cells in enumerate(self.agenda_rows):
            if i < self.current_session_index:
                style = dict(fg=agenda_past_color, bg=bg_color, font=self.font_agenda)
            elif i == self.current_session_index:
                style = dict(fg="white", bg=agenda_current_bg, font=self.font_agenda_bold)
            else:
                style = dict(fg="white", bg=bg_color, font=self.font_agenda)
            for cell in cells:
                cell.config(**style)

        self.scroll_agenda_to_current()

    def scroll_agenda_to_current(self):
        """Scroll so the current session is near the top, with the previous one still visible."""
        self.master.update_idletasks()
        table_height = self.agenda_table.winfo_height()
        if table_height <= self.agenda_canvas.winfo_height() or not self.agenda_rows:
            self.agenda_canvas.yview_moveto(0)
            return
        row = min(max(self.current_session_index - 1, 0), len(self.agenda_rows) - 1)
        self.agenda_canvas.yview_moveto(self.agenda_rows[row][0].winfo_y() / table_height)

    def ask_agenda_file(self):
        """Let the user pick an agenda file, starting from the last one used.

        No parent window on purpose: on macOS that would attach the picker to the window
        as a sheet that can't be moved and can end up partly off-screen.
        """
        last = Path(self.settings.get("agenda_file") or default_agenda_file).expanduser().resolve()
        return filedialog.askopenfilename(
            title="Choose the agenda file",
            initialdir=last.parent if last.parent.is_dir() else Path.cwd(), initialfile=last.name,
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*")])

    def open_agenda(self, event=None):
        """Switch to a different agenda file, keeping the current one if it can't be loaded."""
        path = self.ask_agenda_file()
        if not path:
            return
        previous = self.agenda_file
        self.agenda_file = path
        if self.update_agenda():
            self.save_settings()
        else:
            self.agenda_file = previous

    def update_agenda(self, event=None):
        """Reloads the agenda from the Excel file and resets the session tracker."""
        try:
            self.load_agenda()
        except Exception as e:
            print(f"Could not load agenda, keeping the current one: {e}")
            self.show_status(f"Loading {Path(self.agenda_file).name} failed: {e}", "orange")
            return False
        self.current_session_index = 0
        self.test_index = min(self.test_index, len(self.agenda) - 1)
        self.refresh()
        self.show_status(f"{Path(self.agenda_file).name} loaded at {datetime.now().strftime('%H:%M:%S')}", "gray")
        return True

    def apply_scale(self):
        """Resize all fonts according to the current timer and agenda scales."""
        for font, size in ((self.font_current, letra_current), (self.font_time, letra_time),
                           (self.font_time2, letra_time2), (self.font_status, letra_status),
                           (self.font_watermark, letra_watermark)):
            font.configure(size=max(1, round(size * self.scale)))
        for font in (self.font_agenda, self.font_agenda_bold):
            font.configure(size=max(1, round(letra_agenda * self.agenda_scale)))

    def print_shortcuts(self):
        """Print the mode and the keyboard shortcuts in the terminal."""
        if self.testing:
            print("Mode: TEST - check every session fits, then press Enter to start the real timer\n")
        else:
            print("Mode: RUNNING (start with --test to check the sizes first)\n")
        width = max(len(action) for action, _ in shortcuts) + 3
        print("\n".join(f"{action:<{width}}{keys}" for action, keys in shortcuts), flush=True)

    def load_settings(self):
        """Read the saved settings, or nothing if there is no valid settings file."""
        try:
            settings = json.loads(settings_file.read_text())
        except (OSError, ValueError):
            return {}
        return settings if isinstance(settings, dict) else {}

    def setting_number(self, key, default):
        try:
            return float(self.settings[key])
        except (KeyError, ValueError, TypeError):
            return default

    def save_settings(self):
        """Remember the font scales and agenda file for the next start."""
        self.settings = {"font_scale": round(self.scale, 3),
                         "agenda_scale": round(self.agenda_scale, 3),
                         "agenda_file": str(Path(self.agenda_file).resolve())}
        try:
            settings_file.write_text(json.dumps(self.settings, indent=2))
        except OSError as e:
            print(f"Could not save settings: {e}")

    def set_scale(self, scale):
        self.scale = min(5.0, max(0.3, scale))
        self.apply_scale()
        self.save_settings()
        self.show_status(f"Timer scale: {self.scale:.2f}", "gray")

    def reset_scales(self):
        self.set_scale(font_scale)
        self.set_agenda_scale(agenda_scale)
        self.show_status("Sizes reset", "gray")

    def set_agenda_scale(self, scale):
        self.agenda_scale = min(5.0, max(0.3, scale))
        self.apply_scale()
        self.save_settings()
        self.fit_agenda_width()
        self.scroll_agenda_to_current()
        self.show_status(f"Agenda scale: {self.agenda_scale:.2f}", "gray")

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
                     "Left/Right: change session, P: panic timer, Enter: start the timer",
                fg="orange")
        else:
            self.status_label.config(text="")

    def fit_timer_width(self, width):
        """Wrap the timer side's text so it never gets wider than its half of the screen."""
        self.current_session_label.set_wrap(width)
        for label in (self.current_timer_label, self.status_label):
            label.config(wraplength=max(1, width), justify="center")

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

    def show_test_session(self):
        """Show one session as if it were running, with its full length on the timer."""
        session = self.agenda.iloc[self.test_index]
        self.current_session_index = self.test_index
        self.highlight_agenda()
        self.current_session_label.show("Current", session)
        minutes, seconds = divmod(int((session['end_time'] - session['start_time']).total_seconds()), 60)
        self.current_timer_label.config(text=f"{minutes:02}:{seconds:02} remaining")
        self.set_blinking(self.test_panic)
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

    def end_test_mode(self, event=None):
        if self.testing:
            print(f"Test mode off, timer running with timer scale {self.scale:.2f} (saved for next time)", flush=True)
            self.testing = False
            self.test_panic = False
            self.set_blinking(False)
            self.current_session_index = 0
            self.update_session()
            self.show_status(f"Test mode off, timer running (timer scale {self.scale:.2f})", "gray")

    def update_session(self):
        now = datetime.now()  # Keep the actual time with seconds and microseconds

        # Skip sessions that have already ended
        while self.current_session_index < len(self.agenda):
            end_time_with_date = datetime.combine(now.date(), self.agenda.iloc[self.current_session_index]['end_time'].time())
            if end_time_with_date > now:
                break
            self.current_session_index += 1

        self.highlight_agenda()

        if self.current_session_index >= len(self.agenda):
            # End of the seminar
            self.set_blinking(False)
            self.current_session_label.show_text("All sessions have finished :)")
            self.current_timer_label.config(text="")
            return

        current_session = self.agenda.iloc[self.current_session_index]

        # Update the current session information
        self.current_session_label.show("Current", current_session)

        # Calculate remaining time until the session starts
        start_time_with_date = datetime.combine(now.date(), current_session['start_time'].time())
        remaining_time_until_start = start_time_with_date - now

        if remaining_time_until_start.total_seconds() > 0:
            # Display countdown until the session starts
            self.set_blinking(False)
            minutes, seconds = divmod(int(remaining_time_until_start.total_seconds()), 60)
            self.current_timer_label.config(text=f"Starts in: {minutes:02}:{seconds:02}")
        else:
            # Session ongoing, calculate remaining time
            remaining_time = end_time_with_date - now

            # Update countdown timer with seconds
            minutes, seconds = divmod(int(remaining_time.total_seconds()), 60)
            self.current_timer_label.config(text=f"{minutes:02}:{seconds:02} remaining")

            # Blink when panic_time is reached
            self.set_blinking(remaining_time.total_seconds() < 60 * pannic_time)

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


# Load the agenda file and start the application
if __name__ == "__main__":
    root = tk.Tk()
    args = [arg for arg in sys.argv[1:] if arg != "--test"]
    app = SeminarTracker(root, args[0] if args else None, testing="--test" in sys.argv[1:])
    root.mainloop()
