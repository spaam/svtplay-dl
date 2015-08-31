# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import time

from svtplay_dl.output import progress, output # FIXME use progressbar() instead
from svtplay_dl.fetcher import VideoRetriever

class HTTP(VideoRetriever):
    def name(self):
        return "http"

    def download(self):
        """ Get the stream from HTTP """
        data = self.http.request("get", self.url, stream=True)
        try:
            total_size = data.headers['content-length']
        except KeyError:
            total_size = 0
        total_size = int(total_size)
        bytes_so_far = 0

        file_d = output(self.options, "mp4")
        if hasattr(file_d, "read") is False:
            return

        lastprogress = 0
        for i in data.iter_content(8192):
            bytes_so_far += len(i)
            file_d.write(i)
            if self.options.output != "-":
                now = time.time()
                if lastprogress + 1 < now:
                    lastprogress = now
                    progress(bytes_so_far, total_size)

        if self.options.output != "-":
            file_d.close()
