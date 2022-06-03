from svtplay_dl.utils.http import HTTP


class VideoRetriever:
    def __init__(self, config, url, bitrate, output, **kwargs):
        self.config = config
        self.url = url
        self.bitrate = int(bitrate) if bitrate else 0
        self.kwargs = kwargs
        self.http = HTTP(config)
        self.finished = False
        self.audio = kwargs.pop("audio", None)
        self.files = kwargs.pop("files", None)
        self.keycookie = kwargs.pop("keycookie", None)
        self.authorization = kwargs.pop("authorization", None)
        self.output = output
        self.segments = kwargs.pop("segments", None)
        self.output_extention = None
        channels = kwargs.pop("channels", None)
        codec = kwargs.pop("codec", "h264")
        self.resolution = kwargs.pop("resolution", "")
        self.language = kwargs.pop("language", "")
        self.audio_role = kwargs.pop("role", "main")
        self.format = f"{codec}-{channels}" if channels else codec

    def __repr__(self):
        return f"<Video(fetcher={self.__class__.__name__}, bitrate={self.bitrate} format={self.format}, language={self.language}, audio_role={self.audio_role}, resolution={self.resolution}>"

    @property
    def name(self):
        pass
