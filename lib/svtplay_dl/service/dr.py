# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import base64
import re
import json
import copy

from svtplay_dl.service import Service, OpenGraphThumbMixin
from svtplay_dl.fetcher.rtmp import RTMP
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.fetcher.hds import hdsparse
from svtplay_dl.subtitle import subtitle
from svtplay_dl.error import ServiceError
from svtplay_dl.utils.urllib import urlparse, urljoin


class Dr(Service, OpenGraphThumbMixin):
    supported_domains = ['dr.dk']

    def get(self):
        data = self.get_urldata()

        if self.exclude():
            yield ServiceError("Excluding video")
            return

        match = re.search(r'resource:[ ]*"([^"]*)",', data)
        if match:
            resource_url = match.group(1)
            resource_data = self.http.request("get", resource_url).content
            resource = json.loads(resource_data)
            streams = self.find_stream(self.options, resource)
            for i in streams:
                yield i
        else:
            match = re.search(r'resource="([^"]*)"', data)
            if not match:
                yield ServiceError("Cant find resource info for this video")
                return
            if match.group(1)[:4] != "http":
                resource_url = "http:%s" % match.group(1)
            else:
                resource_url = match.group(1)
            resource_data = self.http.request("get", resource_url).text
            resource = json.loads(resource_data)

            if "Links" not in resource:
                yield ServiceError("Cant access this video. its geoblocked.")
                return
            if "SubtitlesList" in resource and len(resource["SubtitlesList"]) > 0:
                suburl = resource["SubtitlesList"][0]["Uri"]
                yield subtitle(copy.copy(self.options), "wrst", suburl)
            if "Data" in resource:
                streams = self.find_stream(self.options, resource)
                for i in streams:
                    yield i
            else:
                for stream in resource['Links']:
                    if stream["Target"] == "HDS":
                        streams = hdsparse(copy.copy(self.options), self.http.request("get", stream["Uri"], params={"hdcore": "3.7.0"}), stream["Uri"])
                        if streams:
                            for n in list(streams.keys()):
                                yield streams[n]
                    if stream["Target"] == "HLS":
                        streams = hlsparse(self.options, self.http.request("get", stream["Uri"]), stream["Uri"])
                        for n in list(streams.keys()):
                            yield streams[n]
                    if stream["Target"] == "Streaming":
                        self.options.other = "-v -y '%s'" % stream['Uri'].replace("rtmp://vod.dr.dk/cms/", "")
                        rtmp = "rtmp://vod.dr.dk/cms/"
                        yield RTMP(copy.copy(self.options), rtmp, stream['Bitrate'])

    def find_all_episodes(self, options):
        episodes = []
        matches = re.findall(r'<button class="show-more" data-url="([^"]+)" data-partial="([^"]+)"',
                             self.get_urldata())
        for encpath, enccomp in matches:
            newstyle = '_' in encpath
            if newstyle:
                encbasepath = encpath.split('_')[0]
                path = base64.b64decode(encbasepath + '===')
            else:
                path = base64.b64decode(encpath + '===')

            if '/view/' in path:
                continue

            params = 'offset=0&limit=1000'
            if newstyle:
                encparams = base64.b64encode(params).rstrip('=')
                encpath = '%s_%s' % (encbasepath, encparams)
            else:
                path = '%s?%s' % (urlparse(path).path, params)
                encpath = base64.b64encode(path).rstrip('=')

            url = urljoin('https://www.dr.dk/tv/partial/',
                          '%s/%s' % (enccomp, encpath))
            data = self.http.request('get', url).content

            matches = re.findall(r'"program-link" href="([^"]+)">', data)
            episodes = [urljoin('https://www.dr.dk/', url) for url in matches]
            break

        if not episodes:
            prefix = '/'.join(urlparse(self.url).path.rstrip('/').split('/')[:-1])
            matches = re.findall(r'"program-link" href="([^"]+)">', self.get_urldata())
            episodes = [urljoin('https://www.dr.dk/', url)
                        for url in matches
                        if url.startswith(prefix)]

        if options.all_last != -1:
            episodes = episodes[:options.all_last]
        else:
            episodes.reverse()

        return episodes

    def find_stream(self, options, resource):
        tempresource = resource['Data'][0]['Assets']
        # To find the VideoResource, they have Images as well
        for resources in tempresource:
            if resources['Kind'] == 'VideoResource':
                links = resources['Links']
                break
        for i in links:
            if i["Target"] == "Ios" or i["Target"] == "HLS":
                streams = hlsparse(options, self.http.request("get", i["Uri"]), i["Uri"])
                for n in list(streams.keys()):
                    yield streams[n]
            else:
                if i["Target"] == "Streaming":
                    options.other = "-y '%s'" % i["Uri"].replace("rtmp://vod.dr.dk/cms/", "")
                    rtmp = "rtmp://vod.dr.dk/cms/"
                    yield RTMP(copy.copy(options), rtmp, i["Bitrate"])
