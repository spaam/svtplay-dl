class Kanal5():
    def handle(self, url):
        return "kanal5play.se" in url

    def get(self, options, url):
        match = re.search(".*video/([0-9]+)", url)
        if not match:
            log.error("Can't find video file")
            sys.exit(2)
        url = "http://www.kanal5play.se/api/getVideo?format=FLASH&videoId=%s" % match.group(1)
        data = json.loads(get_http_data(url))
        options.live = data["isLive"]
        steambaseurl = data["streamBaseUrl"]
        streams = {}

        for i in data["streams"]:
            stream = {}
            stream["source"] = i["source"]
            streams[int(i["bitrate"])] = stream

        test = select_quality(options, streams)

        filename = test["source"]
        match = re.search("^(.*):", filename)
        options.output  = "%s.%s" % (options.output, match.group(1))
        options.other = "-W %s -y %s " % ("http://www.kanal5play.se/flash/StandardPlayer.swf", filename)
        download_rtmp(options, steambaseurl)

