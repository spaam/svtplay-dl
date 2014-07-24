class VideoRetriever(object):
    def __init__(self, options, url, bitrate=0, **kwargs):
        self.options = options
        self.url = url
        self.bitrate = int(bitrate)
        self.kwargs = kwargs

    def name(self):
        pass
