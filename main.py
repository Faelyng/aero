import tkinter as tk
import sv_ttk
from ui.desktop_ui import MissionFormApp

class App:
    def __init__(self):
        self.root = tk.Tk()
        sv_ttk.set_theme("light")
        self.app = MissionFormApp(self.root)

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = App()
    app.run()