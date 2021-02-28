import logging
import subprocess


def run_program(cmd, show=True):
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
    stdout, stderr = p.communicate()
    stderr = stderr.decode("utf-8", "replace")
    if p.returncode != 0 and show:
        msg = stderr.strip()
        logging.error(f"Something went wrong: {msg}")
    return p.returncode, stdout, stderr
