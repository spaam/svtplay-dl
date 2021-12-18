# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
import os

from svtplay_dl.fetcher import VideoRetriever
from svtplay_dl.utils.output import ETA
from svtplay_dl.utils.output import formatname
from svtplay_dl.utils.output import progressbar


class HTTP(VideoRetriever):
    @property
    def name(self):
        return "http"

    def download(self):
        """Get the stream from HTTP"""
        _, ext = os.path.splitext(self.url)
        if ext == ".mp3":
            self.output["ext"] = "mp3"
        else:
            self.output["ext"] = "mp4"  # this might be wrong..
        data = self.http.request("get", self.url, stream=True)
        try:
            total_size = data.headers["content-length"]
        except KeyError:
            total_size = 0
        total_size = int(total_size)
        bytes_so_far = 0

        filename = formatname(self.output, self.config)
        file_d = open(filename, "wb")

        eta = ETA(total_size)
        for i in data.iter_content(8192):
            bytes_so_far += len(i)
            file_d.write(i)
            if not self.config.get("silent"):
                eta.update(bytes_so_far)
                progressbar(total_size, bytes_so_far, "".join(["ETA: ", str(eta)]))

        file_d.close()
        self.finished = True
