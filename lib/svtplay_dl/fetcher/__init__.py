class VideoRetriever:
    def __init__(self, options, url, bitrate, **kwargs):
        self.options = options
        self.url = url
        self.bitrate = int(bitrate)
        self.kwargs = kwargs

    def name(self):
        pass