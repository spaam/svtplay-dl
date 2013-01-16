class Expressen():
    def handle(self, url):
        return "expressen.se" in url

    def get(self, options, url):
        parse = urlparse(url)
        match = re.search("/(.*[\/\+].*)/", unquote_plus(parse.path))
        if not match:
            log.error("Can't find video file")
            sys.exit(2)
        url = "http://tv.expressen.se/%s/?standAlone=true&output=xml" % quote_plus(match.group(1))
        other = ""
        data = get_http_data(url)
        xml = ET.XML(data)
        ss = xml.find("vurls")
        if sys.version_info < (2, 7):
            sa = list(ss.getiterator("vurl"))
        else:
            sa = list(ss.iter("vurl"))
        streams = {}

        for i in sa:
            streams[int(i.attrib["bitrate"])] = i.text

        test = select_quality(options, streams)

        filename = test
        match = re.search("rtmp://([0-9a-z\.]+/[0-9]+/)(.*).flv", filename)

        filename = "rtmp://%s" % match.group(1)
        options.other = "-y %s" % match.group(2)

        download_rtmp(options, filename)

