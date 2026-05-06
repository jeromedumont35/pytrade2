import subprocess
import sys
import time

SCRIPT = "S_db_one_resolution.py"

RESOLUTIONS = ["1d", "4h", "1h"]

def run_resolution(res):
    print(f"\n🚀 Launching {SCRIPT} with resolution: {res}\n")

    process = subprocess.Popen(
        [sys.executable, SCRIPT, res],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    # Affiche les logs en direct
    for line in process.stdout:
        print(line, end="")

    process.wait()

    print(f"\n✅ Finished: {res}\n")


def main():
    for res in RESOLUTIONS:
        run_resolution(res)
        time.sleep(2)  # petite pause entre les runs


if __name__ == "__main__":
    main()