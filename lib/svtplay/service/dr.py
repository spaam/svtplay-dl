from __future__ import absolute_import
import re
import json

from svtplay.utils import get_http_data, select_quality
from svtplay.rtmp import download_rtmp

class Dr(object):
    def handle(self, url):
        return "dr.dk" in url

    def get(self, options, url):
        data = get_http_data(url)
        match = re.search(r'resource:[ ]*"([^"]*)",', data)
        resource_url = match.group(1)
        resource_data = get_http_data(resource_url)
        resource = json.loads(resource_data)
        streams = {}
        for stream in resource['links']:
            streams[stream['bitrateKbps']] = stream['uri']
        if len(streams) == 1:
            uri = streams[list(streams.keys())[0]]
        else:
            uri = select_quality(options, streams)
        # need -v ?
        options.other = "-v -y '" + uri.replace("rtmp://vod.dr.dk/cms/", "") + "'"
        download_rtmp(options, uri)

