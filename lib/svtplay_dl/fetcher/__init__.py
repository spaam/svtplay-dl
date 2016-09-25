from __future__ import absolute_import
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

    def __repr__(self):
        return "<Video(fetcher=%s, bitrate=%s>" % (self.__class__.__name__, self.bitrate)

    def name(self):
        pass
