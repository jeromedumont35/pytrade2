import subprocess
import os
import sys
import shlex


class CLauncher:
    """
    Lance S_Prod_Launcher.py :
    - Windows        → nouvelle console
    - Linux          → nouvelle fenêtre terminal (Terminator prioritaire)
    - macOS          → nouvelle session
    - Termux         → nouvelle fenêtre tmux (auto start-server)
    """

    TMUX_SESSION = "pytrade"

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

    # ------------------------------------------------------------------
    # UTILS
    # ------------------------------------------------------------------
    def _which(self, exe):
        """Retourne True si l'exécutable est présent"""
        return subprocess.call(
            ["which", exe],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        ) == 0

    # ------------------------------------------------------------------
    # TERMUX / TMUX
    # ------------------------------------------------------------------
    def _is_termux(self):
        return "TERMUX_VERSION" in os.environ

    def _tmux_start_server(self):
        subprocess.run(
            ["tmux", "start-server"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

    def _tmux_ensure_session(self):
        subprocess.run(
            ["tmux", "new-session", "-d", "-s", self.TMUX_SESSION],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

    def _tmux_new_window(self, window_name, cmd):
        subprocess.Popen(
            [
                "tmux", "new-window",
                "-t", self.TMUX_SESSION,
                "-n", window_name,
                shlex.join(cmd)
            ],
            cwd=self.launcher_dir,
            shell=False
        )

    # ------------------------------------------------------------------
    # LINUX TERMINALS
    # ------------------------------------------------------------------
    def _launch_in_linux_terminal(self, cmd):
        cmd_str = shlex.join(cmd)

        if self._which("terminator"):
            terminal_cmd = ["terminator", "-e", cmd_str]

        elif self._which("gnome-terminal"):
            terminal_cmd = ["gnome-terminal", "--", "bash", "-c", cmd_str]

        elif self._which("konsole"):
            terminal_cmd = ["konsole", "-e", cmd_str]

        elif self._which("xterm"):
            terminal_cmd = ["xterm", "-e", cmd_str]

        else:
            # fallback sans terminal graphique
            subprocess.Popen(
                cmd,
                cwd=self.launcher_dir,
                start_new_session=True
            )
            return

        subprocess.Popen(
            terminal_cmd,
            cwd=self.launcher_dir,
            shell=False
        )

    # ------------------------------------------------------------------
    # PUBLIC
    # ------------------------------------------------------------------
    def run_launcher(self, amount, symbol, nb_days):
        cmd = [
            sys.executable,
            self.script_path,
            str(amount),
            str(symbol),
            str(nb_days)
        ]

        print(f"[LAUNCH] {' '.join(cmd)}")

        # ---- Windows ----
        if sys.platform == "win32":
            subprocess.Popen(
                cmd,
                cwd=self.launcher_dir,
                shell=False,
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
            return

        # ---- Termux ----
        if self._is_termux():
            window_name = f"{symbol}_A{amount}_D{nb_days}"

            self._tmux_start_server()
            self._tmux_ensure_session()
            self._tmux_new_window(window_name, cmd)
            return

        # ---- Linux ----
        if sys.platform.startswith("linux"):
            self._launch_in_linux_terminal(cmd)
            return

        # ---- macOS / fallback ----
        subprocess.Popen(
            cmd,
            cwd=self.launcher_dir,
            start_new_session=True
        )
