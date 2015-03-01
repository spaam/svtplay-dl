# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import re
import json
import copy

from svtplay_dl.service import Service, OpenGraphThumbMixin
from svtplay_dl.utils import get_http_data
from svtplay_dl.fetcher.rtmp import RTMP
from svtplay_dl.fetcher.hls import HLS, hlsparse
from svtplay_dl.fetcher.hds import hdsparse
from svtplay_dl.subtitle import subtitle
from svtplay_dl.log import log

class Dr(Service, OpenGraphThumbMixin):
    supported_domains = ['dr.dk']

    def get(self, options):
        error, data = self.get_urldata()
        if error:
            log.error("Can't download page.")
            return

        if self.exclude(options):
            return

        match = re.search(r'resource:[ ]*"([^"]*)",', data)
        if match:
            resource_url = match.group(1)
            error, resource_data = get_http_data(resource_url)
            if error:
                log.error("Can't get resource data")
                return
            resource = json.loads(resource_data)
            streams = find_stream(options, resource)
            for i in streams:
                yield i
        else:
            match = re.search(r'resource="([^"]*)"', data)
            if not match:
                log.error("Cant find resource info for this video")
                return
            resource_url = "%s" % match.group(1)
            error, resource_data = get_http_data(resource_url)
            if error:
                log.error("Can't get resource data")
                return
            resource = json.loads(resource_data)

            if "SubtitlesList" in resource:
                suburl = resource["SubtitlesList"][0]["Uri"]
                yield subtitle(copy.copy(options), "wrst", suburl)
            if "Data" in resource:
                streams = find_stream(options, resource)
                for i in streams:
                    yield i
            else:
                for stream in resource['Links']:
                    if stream["Target"] == "HDS":
                        streams = hdsparse(copy.copy(options), stream["Uri"])
                        if streams:
                            for n in list(streams.keys()):
                                yield streams[n]
                    if stream["Target"] == "HLS":
                        streams = hlsparse(stream["Uri"])
                        for n in list(streams.keys()):
                            yield HLS(copy.copy(options), streams[n], n)
                    if stream["Target"] == "Streaming":
                        options.other = "-v -y '%s'" % stream['Uri'].replace("rtmp://vod.dr.dk/cms/", "")
                        rtmp = "rtmp://vod.dr.dk/cms/"
                        yield RTMP(copy.copy(options), rtmp, stream['Bitrate'])

def find_stream(options, resource):
    tempresource = resource['Data'][0]['Assets']
    # To find the VideoResource, they have Images as well
    for resources in tempresource:
        if resources['Kind'] == 'VideoResource':
            links = resources['Links']
            break
    for i in links:
        if i["Target"] == "Ios" or i["Target"] == "HLS":
            streams = hlsparse(i["Uri"])
            for n in list(streams.keys()):
                yield HLS(copy.copy(options), streams[n], n)
        else:
            if i["Target"] == "Streaming":
                options.other = "-y '%s'" % i["Uri"].replace("rtmp://vod.dr.dk/cms/", "")
                rtmp = "rtmp://vod.dr.dk/cms/"
                yield RTMP(copy.copy(options), rtmp, i["Bitrate"])
