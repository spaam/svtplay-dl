# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
import os
import time
from datetime import timedelta
from io import BytesIO

import pycurl

# We should ignore SIGPIPE when using pycurl.NOSIGNAL - see
# the libcurl tutorial for more info.
try:
    import signal
    from signal import SIGPIPE, SIG_IGN
except ImportError:
    pass
else:
    signal.signal(SIGPIPE, SIG_IGN)

from svtplay_dl.utils.output import progressbar, ETA
from svtplay_dl.utils import http

DEBUG = False


def get(urls, cookies, config=None, total_duration=None, tot_urls=0):

    if config.get("jobs") == 0:
        num_conn = os.cpu_count()
    else:
        num_conn = config.get("jobs")
    num_urls = len(urls)
    num_conn = min(num_conn, num_urls)
    eta = ETA(num_urls)

    if DEBUG:
        print("PycURL {} (compiled against 0x{:x})".format(pycurl.version, pycurl.COMPILE_LIBCURL_VERSION_NUM))
        print("----- Getting", num_urls, "URLs using", num_conn, "connections -----")

    start_time = time.time()

    # Pre-allocate a list of curl objects
    m = pycurl.CurlMulti()
    m.handles = []
    for i in range(num_conn):
        c = pycurl.Curl()
        c.b = None
        c.setopt(pycurl.FOLLOWLOCATION, 1)
        c.setopt(pycurl.MAXREDIRS, 5)
        c.setopt(pycurl.CONNECTTIMEOUT, 30)
        c.setopt(pycurl.TIMEOUT, 300)
        c.setopt(pycurl.NOSIGNAL, 1)
        if config and config.get("http_headers"):
            c.setopt(pycurl.HTTPHEADER, [http.split_header(config.get("http_headers")), "User-Agent:" + http.FIREFOX_UA])
        else:
            c.setopt(pycurl.HTTPHEADER, ["User-Agent:" + http.FIREFOX_UA])
        m.handles.append(c)

    freelist = m.handles[:]
    num_processed = 0
    last_num_processed = 0
    while num_processed < num_urls:
        # If there is an url to process and a free curl object, add to multi stack
        while urls and freelist:
            url = urls.pop(0)
            c = freelist.pop()
            c.b = BytesIO()
            cookie_string = "; ".join([str(x) + "=" + str(y) for x, y in cookies.items()])
            c.setopt(pycurl.COOKIE, cookie_string)
            c.setopt(pycurl.URL, url)
            c.setopt(pycurl.WRITEDATA, c.b)
            m.add_handle(c)
            # store some info
            c.url = url
        # Run the internal curl state machine for the multi stack
        while 1:
            ret, num_handles = m.perform()
            if ret != pycurl.E_CALL_MULTI_PERFORM:
                break
        # Check for curl objects which have terminated, and add them to the freelist
        while 1:
            num_q, ok_list, err_list = m.info_read()
            for c in ok_list:
                m.remove_handle(c)
                freelist.append(c)
            for c, errno, errmsg in err_list:
                m.remove_handle(c)
                freelist.append(c)
            num_processed = num_processed + len(ok_list) + len(err_list)
            if num_q == 0:
                break
        # Currently no more I/O is pending, could do something in the meantime
        # (display a progress bar, etc.).
        # We just call select() to sleep until some more data is available.

        if not config.get("silent") and num_processed > last_num_processed:
            if config.get("live"):
                progressbar(tot_urls + num_urls, tot_urls + num_processed, "".join(["DU: ", str(timedelta(seconds=int(total_duration)))]))
            else:
                for i in range(num_processed - last_num_processed):
                    eta.increment()
                progressbar(num_urls, num_processed, "".join(["ETA: ", str(eta)]))

        last_num_processed = num_processed
        m.select(1.0)

    out = []
    # Cleanup
    for c in m.handles:
        out.insert(0, c.b.getvalue())
        c.close()
    m.close()

    end_time = time.time()
    if DEBUG:
        print("Time diff:{}".format(end_time - start_time))

    return out
