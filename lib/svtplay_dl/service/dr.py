# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import re
import json

from svtplay_dl.service import Service
from svtplay_dl.utils import get_http_data, select_quality
from svtplay_dl.fetcher.rtmp import download_rtmp

class Dr(Service):
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

