import platform
import subprocess
import logging


def which(program):
    import os

    if platform.system() == "Windows":
        program = "{0}.exe".format(program)

    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            path = path.strip('"')
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file
        if os.path.isfile(program):
            exe_file = os.path.join(os.getcwd(), program)
            if is_exe(exe_file):
                return exe_file
    return None


def run_program(cmd, show=True):
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
    stdout, stderr = p.communicate()
    stderr = stderr.decode('utf-8', 'replace')
    if p.returncode != 0 and show:
        msg = stderr.strip()
        logging.error("Something went wrong: {0}".format(msg))
    return p.returncode, stdout, stderr
