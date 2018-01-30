# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import

from svtplay_dl.output import output, ETA, progressbar
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
        if file_d is None:
            return

        eta = ETA(total_size)
        for i in data.iter_content(8192):
            bytes_so_far += len(i)
            file_d.write(i)
            if not self.options.silent:
                eta.update(bytes_so_far)
                progressbar(total_size, bytes_so_far, ''.join(["ETA: ", str(eta)]))

        file_d.close()
        self.finished = True
