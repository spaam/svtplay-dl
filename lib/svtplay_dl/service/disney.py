# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-

from __future__ import absolute_import
import json
import re
import copy

from svtplay_dl.service import Service, OpenGraphThumbMixin
from svtplay_dl.utils import get_http_data, check_redirect
from svtplay_dl.utils.urllib import urlparse
from svtplay_dl.fetcher.hls import HLS, hlsparse
from svtplay_dl.fetcher.http import HTTP
from svtplay_dl.log import log

class Disney(Service, OpenGraphThumbMixin):
    supported_domains = ['disney.se', 'video.disney.se']

    def get(self, options):
        parse = urlparse(self.url)
        if parse.hostname == "video.disney.se":
            match = re.search(r"Grill.burger=({.*}):", self.get_urldata())
            if not match:
                log.error("Can't find video info")
                return
            jsondata = json.loads(match.group(1))
            for n in jsondata["stack"]:
                if len(n["data"]) > 0:
                    for x in n["data"]:
                        if "flavors" in x:
                            for i in x["flavors"]:
                                if i["format"] == "mp4":
                                    yield HTTP(copy.copy(options), i["url"], i["bitrate"])
        else:
            match = re.search(r"uniqueId : '([^']+)'", self.get_urldata())
            if not match:
                log.error("Can't find video info")
                return
            uniq = match.group(1)
            match = re.search("entryId : '([^']+)'", self.get_urldata())
            entryid = match.group(1)
            match = re.search("partnerId : '([^']+)'", self.get_urldata())
            partnerid = match.group(1)
            match = re.search("uiConfId : '([^']+)'", self.get_urldata())
            uiconfid = match.group(1)


            url = "http://cdnapi.kaltura.com/html5/html5lib/v1.9.7.6/mwEmbedFrame.php?&wid=%s&uiconf_id=%s&entry_id=%s&playerId=%s&forceMobileHTML5=true&urid=1.9.7.6&callback=mwi" % \
            (partnerid, uiconfid, entryid, uniq)
            data = get_http_data(url)
            match = re.search(r"mwi\(({.*})\);", data)
            jsondata = json.loads(match.group(1))
            data = jsondata["content"]
            match = re.search(r"window.kalturaIframePackageData = ({.*});", data)
            jsondata = json.loads(match.group(1))
            ks = jsondata["enviornmentConfig"]["ks"]

            url = "http://cdnapi.kaltura.com/p/%s/sp/%s00/playManifest/entryId/%s/format/applehttp/protocol/http/a.m3u8?ks=%s&referrer=aHR0cDovL3d3dy5kaXNuZXkuc2U=&" % (partnerid[1:], partnerid[1:], entryid, ks)
            redirect  = check_redirect(url)
            streams = hlsparse(redirect)
            for n in list(streams.keys()):
                yield HLS(copy.copy(options), streams[n], n)