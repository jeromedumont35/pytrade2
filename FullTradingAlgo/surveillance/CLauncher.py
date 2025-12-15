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

        subprocess.Popen(
            cmd,
            cwd=self.launcher_dir,
            creationflags=subprocess.CREATE_NEW_CONSOLE,  # 👈 clé
            shell=False
        )
