import sys
import os

from svtplay.log import log

progress_stream = sys.stderr

def progress(byte, total, extra = ""):
    """ Print some info about how much we have downloaded """
    ratio = float(byte) / total
    percent = round(ratio*100, 2)
    tlen = str(len(str(total)))
    fmt = "Downloaded %"+tlen+"dkB of %dkB bytes (% 3.2f%%)"
    progresstr = fmt % (byte >> 10, total >> 10, percent)

    columns = int(os.getenv("COLUMNS", "80"))
    if len(progresstr) < columns - 13:
        p = int((columns - len(progresstr) - 3) * ratio)
        q = int((columns - len(progresstr) - 3) * (1 - ratio))
        progresstr = "[" + ("#" * p) + (" " * q) + "] " + progresstr
    progress_stream.write(progresstr + ' ' + extra + '\r')

    if byte >= total:
        progress_stream.write('\n')

    progress_stream.flush()

def progressbar(total, pos, msg=""):
    """
    Given a total and a progress position, output a progress bar
    to stderr. It is important to not output anything else while
    using this, as it relies soley on the behavior of carriage
    return (\\r).

    Can also take an optioal message to add after the
    progressbar. It must not contain newliens.

    The progress bar will look something like this:

    [099/500][=========...............................] ETA: 13:36:59

    Of course, the ETA part should be supplied be the calling
    function.
    """
    width = 50 # TODO hardcoded progressbar width
    rel_pos = int(float(pos)/total*width)
    bar = str()

    # FIXME ugly generation of bar
    for i in range(0, rel_pos):
        bar += "="
    for i in range(rel_pos, width):
        bar += "."

    # Determine how many digits in total (base 10)
    digits_total = len(str(total))
    fmt_width = "%0" + str(digits_total) + "d"
    fmt = "\r[" + fmt_width + "/" + fmt_width + "][%s] %s"

    progress_stream.write(fmt % (pos, total, bar, msg))

