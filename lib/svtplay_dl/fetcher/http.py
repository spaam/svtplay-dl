# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import sys
import time
import re

from svtplay_dl.output import progress # FIXME use progressbar() instead
from svtplay_dl.log import log
from svtplay_dl.utils.urllib import urlopen, Request, HTTPError

def download_http(options, url):
    """ Get the stream from HTTP """
    request = Request(url)
    request.add_header('User-Agent', 'Mozilla/5.0 (Windows; U; Windows NT 5.1; en-GB; rv:1.9.0.3) Gecko/2008092417 Firefox/3.0.3')
    try:
        response = urlopen(request)
    except HTTPError as e:
        log.error("Something wrong with that url")
        log.error("Error code: %s" % e.code)
        sys.exit(5)
    try:
        total_size = response.info()['Content-Length']
    except KeyError:
        total_size = 0
    total_size = int(total_size)
    bytes_so_far = 0
    if options.output != "-":
        extension = re.search(r"(\.[a-z0-9]+)$", url)
        if extension:
            options.output = options.output + extension.group(1)
        else:
            options.output = "%s.mp4" % options.output
        log.info("Outfile: %s", options.output)
        file_d = open(options.output, "wb")
    else:
        file_d = sys.stdout

    lastprogress = 0
    while 1:
        chunk = response.read(8192)
        bytes_so_far += len(chunk)

        if not chunk:
            break

        file_d.write(chunk)
        if options.output != "-":
            now = time.time()
            if lastprogress + 1 < now:
                lastprogress = now
                progress(bytes_so_far, total_size)

    if options.output != "-":
        file_d.close()

