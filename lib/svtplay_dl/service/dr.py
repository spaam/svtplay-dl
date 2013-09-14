# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import re
import json

from svtplay_dl.service import Service
from svtplay_dl.utils import get_http_data, select_quality
from svtplay_dl.fetcher.rtmp import download_rtmp
from svtplay_dl.fetcher.hls import download_hls

class Dr(Service):
    def handle(self, url):
        return "dr.dk" in url

    def get(self, options, url):
        data = get_http_data(url)
        match = re.search(r'resource:[ ]*"([^"]*)",', data)
        if match:
            resource_url = match.group(1)
            resource_data = get_http_data(resource_url)
            resource = json.loads(resource_data)
            tempresource = resource['Data'][0]['Assets']
            # To find the VideoResource, they have Images as well
            for resources in tempresource:
                if resources['Kind'] == 'VideoResource':
                    links = resources['Links']
                    break

            streams = {}
            for i in links:
                if options.hls:
                    if i["Target"] == "Ios":
                        stream = {}
                        stream["uri"] = i["Uri"]
                        streams[int(i["Bitrate"])] = stream
                else:
                    if i["Target"] == "Streaming":
                        stream = {}
                        stream["uri"] = i["Uri"]
                        streams[int(i["Bitrate"])] = stream

            if len(streams) == 1:
                test = streams[list(streams.keys())[0]]
            else:
                test = select_quality(options, streams)

            if options.hls:
                baseurl = test["uri"][0:test["uri"].rfind("/")]
                download_hls(options, test["uri"], baseurl=baseurl)
            else:
                options.other = "-y '%s'" % test["uri"].replace("rtmp://vod.dr.dk/cms/", "")
                rtmp = "rtmp://vod.dr.dk/cms/"
                download_rtmp(options, rtmp)
        else:
            match = re.search(r'resource="([^"]*)"', data)
            if not match:
                log.error("Cant find resource info for this video")
                sys.exit(2)
            resource_url = "http://www.dr.dk%s" % match.group(1)
            resource_data = get_http_data(resource_url)
            resource = json.loads(resource_data)
            streams = {}
            for stream in resource['links']:
                streams[stream['bitrateKbps']] = stream['uri']
            if len(streams) == 1:
                uri = streams[list(streams.keys())[0]]
            else:
                uri = select_quality(options, streams)

            options.other = "-v -y '" + uri.replace("rtmp://vod.dr.dk/cms/", "") + "'"
            rtmp = "rtmp://vod.dr.dk/cms/"
            download_rtmp(options, rtmp)
