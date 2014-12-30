# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import time

from svtplay_dl.output import progress, output # FIXME use progressbar() instead
from svtplay_dl.log import log
from svtplay_dl.utils.urllib import urlopen, Request, HTTPError
from svtplay_dl.fetcher import VideoRetriever

class HTTP(VideoRetriever):
    def name(self):
        return "http"

    def download(self):
        """ Get the stream from HTTP """
        request = Request(self.url)
        request.add_header('User-Agent', 'Mozilla/5.0 (Windows; U; Windows NT 5.1; en-GB; rv:1.9.0.3) Gecko/2008092417 Firefox/3.0.3')
        try:
            response = urlopen(request)
        except HTTPError as e:
            log.error("Something wrong with that url")
            return
        try:
            total_size = response.info()['Content-Length']
        except KeyError:
            total_size = 0
        total_size = int(total_size)
        bytes_so_far = 0

        file_d = output(self.options, "mp4")
        if hasattr(file_d, "read") is False:
            return

        lastprogress = 0
        while 1:
            chunk = response.read(8192)
            bytes_so_far += len(chunk)

            if not chunk:
                break

            file_d.write(chunk)
            if self.options.output != "-":
                now = time.time()
                if lastprogress + 1 < now:
                    lastprogress = now
                    progress(bytes_so_far, total_size)

        if self.options.output != "-":
            file_d.close()

