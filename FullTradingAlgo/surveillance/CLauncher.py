import subprocess
import os
import sys


class CLauncher:
    def __init__(self):
        # Chemin absolu vers ../launchers/jdu
        self.launcher_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "launchers", "jdu")
        )

        self.script_path = os.path.join(
            self.launcher_dir,
            "S_Prod_Launcher.py"
        )

        if not os.path.exists(self.script_path):
            raise FileNotFoundError(self.script_path)

    def run_launcher(self, timeframe, symbol, mode):
        cmd = [
            sys.executable,
            self.script_path,
            str(timeframe),
            str(symbol),
            str(mode)
        ]

        print(f"[LAUNCH] {' '.join(cmd)}")

        kwargs = {
            "cwd": self.launcher_dir,
            "shell": False
        }

        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NEW_CONSOLE
        else:
            # équivalent logique sous Linux / macOS
            kwargs["start_new_session"] = True

        subprocess.Popen(cmd, **kwargs)
