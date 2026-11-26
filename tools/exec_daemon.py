"""Optional persistent command executor for harnesses with slow per-call shell startup.

Start once as a background daemon:
  python -u tools/exec_daemon.py

Pipe normal CLI commands by appending lines to live/exec_in.txt (e.g. via write_file Append=true):
  python tools/say.py "Testing warm executor."
  python tools/send.py "CMD CmdAttackNW"

Each command runs in the repo root using the exact same tools/*.py scripts and flags (no behavior
changes). Output is written to live/exec_last.txt (with "--- DONE #<n> rc=<rc> (<t>s) ---") and
also printed to stdout.
"""
import shlex, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INBOX = ROOT / "live" / "exec_in.txt"
LAST = ROOT / "live" / "exec_last.txt"
SHELL_OPS = (";", "|", "&", ">", "<")


def run_one(line):
    use_direct = line.startswith("python ") and not any(op in line for op in SHELL_OPS)
    if use_direct:
        try:
            parts = shlex.split(line, posix=True)
            cmd = [sys.executable] + parts[1:]
            p = subprocess.run(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, encoding="utf-8", errors="replace")
            return p.returncode, p.stdout
        except ValueError:
            pass
    p = subprocess.run(line, shell=True, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       text=True, encoding="utf-8", errors="replace")
    return p.returncode, p.stdout


def read_lines():
    try:
        return [l.strip() for l in INBOX.read_text(encoding="utf-8-sig").splitlines() if l.strip()]
    except FileNotFoundError:
        return []


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    INBOX.parent.mkdir(exist_ok=True)
    done = len(read_lines())  # ignore any stale lines from previous runs
    print(f"EXEC_DAEMON READY (watching live/exec_in.txt from line {done})", flush=True)
    n = 0
    while True:
        lines = read_lines()
        if len(lines) < done:
            done = 0  # file was truncated/recreated
        if len(lines) > done:
            batch = lines[done:]
            done = len(lines)
            chunks = []
            for line in batch:
                n += 1
                t0 = time.time()
                try:
                    rc, out = run_one(line)
                except Exception as e:
                    rc, out = 1, f"exec_daemon error: {e}\n"
                dt = time.time() - t0
                if out and not out.endswith("\n"):
                    out += "\n"
                block = f"--- EXEC #{n}: {line} ---\n{out}--- DONE #{n} rc={rc} ({dt:.2f}s) ---\n"
                chunks.append(block)
                print(block, end="", flush=True)
            try:
                LAST.write_text("".join(chunks), encoding="utf-8")
            except OSError:
                pass
        time.sleep(0.02)


if __name__ == "__main__":
    main()
