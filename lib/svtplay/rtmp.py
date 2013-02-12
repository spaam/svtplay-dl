import subprocess
import re
import shlex

from lib.svtplay.log import log

def download_rtmp(options, url):
    """ Get the stream from RTMP """
    args = []
    if options.live:
        args.append("-v")

    if options.resume:
        args.append("-e")

    extension = re.search("(\.[a-z0-9]+)$", url)
    if options.output != "-":
        if not extension:
            extension = re.search("-y (.+):[-_a-z0-9\/]", options.other)
            if not extension:
                options.output = "%s.flv" % options.output
            else:
                options.output = "%s%s" % (options.output, extension.group(1))
        else:
            options.output = options.output + extension.group(1)
        log.info("Outfile: %s", options.output)
        args += ["-o", options.output]
    if options.silent or options.output == "-":
        args.append("-q")
    if options.other:
        args += shlex.split(options.other)
    command = ["rtmpdump", "-r", url] + args
    try:
        subprocess.call(command)
    except OSError as e:
        log.error("Could not execute rtmpdump: " + e.strerror)

