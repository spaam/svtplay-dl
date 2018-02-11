from __future__ import absolute_import
import copy

from svtplay_dl.output import progress_stream, output, ETA, progressbar
from svtplay_dl.utils import HTTP


class VideoRetriever(object):
    def __init__(self, options, url, bitrate=0, **kwargs):
        self.options = options
        self.url = url
        self.bitrate = int(bitrate)
        self.kwargs = kwargs
        self.http = HTTP(options)
        self.finished = False
        self.audio = kwargs.pop("audio", None)
        self.files = kwargs.pop("files", None)
        self.keycookie = kwargs.pop("keycookie", None)
        self.authorization = kwargs.pop("authorization", None)

    def __repr__(self):
        return "<Video(fetcher=%s, bitrate=%s>" % (self.__class__.__name__, self.bitrate)

    def name(self):
        pass

    def _download_url(self, url, audio=False, total_size=None):
        cookies = self.kwargs["cookies"]
        data = self.http.request("get", url, cookies=cookies, headers={'Range': 'bytes=0-8192'})
        if not total_size:
            try:
                total_size = data.headers['Content-Range']
                total_size = total_size[total_size.find("/") + 1:]
                total_size = int(total_size)
            except KeyError:
                raise KeyError("Can't get the total size.")

        bytes_so_far = 8192
        if audio:
            file_d = output(copy.copy(self.options), "m4a")
        else:
            file_d = output(self.options, self.options.other)

        if file_d is None:
            return
        file_d.write(data.content)
        eta = ETA(total_size)
        while bytes_so_far < total_size:

            if not self.options.silent:
                eta.update(bytes_so_far)
                progressbar(total_size, bytes_so_far, ''.join(["ETA: ", str(eta)]))

            old = bytes_so_far + 1
            bytes_so_far = total_size

            bytes_range = "bytes={0}-{1}".format(old, bytes_so_far)

            data = self.http.request("get", url, cookies=cookies, headers={'Range': bytes_range})
            file_d.write(data.content)

        file_d.close()
        progressbar(bytes_so_far, total_size, "ETA: complete")
        progress_stream.write('\n')
        self.finished = True
