class Urplay():
    def handle(self, url):
        return "urplay.se" in url

    def get(self, options, url):
        data = get_http_data(url)
        match = re.search('file=(.*)\&plugins', data)
        if match:
            path = "mp%s:%s" % (match.group(1)[-1], match.group(1))
            options.other = "-a ondemand -y %s" % path
            download_rtmp(options, "rtmp://streaming.ur.se/")

