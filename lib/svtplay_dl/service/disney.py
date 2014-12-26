# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-

from __future__ import absolute_import
import json
import re
import copy
import os

from svtplay_dl.service import Service, OpenGraphThumbMixin
from svtplay_dl.utils import get_http_data, check_redirect, filenamify
from svtplay_dl.utils.urllib import urlparse
from svtplay_dl.fetcher.hls import HLS, hlsparse
from svtplay_dl.fetcher.http import HTTP
from svtplay_dl.log import log

class Disney(Service, OpenGraphThumbMixin):
    supported_domains = ['disney.se', 'video.disney.se']

    def get(self, options):
        parse = urlparse(self.url)
        if parse.hostname == "video.disney.se":
            error, data = self.get_urldata()
            if error:
                log.error("Can't get the page")
                return

            if self.exclude(options):
                return

            match = re.search(r"Grill.burger=({.*}):", data)
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
            error, data = self.get_urldata()
            if error:
                log.error("Cant get the page")
                return
            match = re.search(r"uniqueId : '([^']+)'", data)
            if not match:
                log.error("Can't find video info")
                return
            uniq = match.group(1)
            match = re.search("entryId : '([^']+)'", self.get_urldata()[1])
            entryid = match.group(1)
            match = re.search("partnerId : '([^']+)'", self.get_urldata()[1])
            partnerid = match.group(1)
            match = re.search("uiConfId : '([^']+)'", self.get_urldata()[1])
            uiconfid = match.group(1)

            match = re.search("json : ({.*}}),", self.get_urldata()[1])
            jsondata = json.loads(match.group(1))
            parse = urlparse(self.url)
            if len(parse.fragment) > 0:
                entry = parse.fragment[parse.fragment.rindex("/")+1:]
                if entry in jsondata["idlist"]:
                    entryid = jsondata["idlist"][entry]
                else:
                    log.error("Cant find video info")
                    return
            if options.output_auto:
                for i in jsondata["playlists"][0]["playlist"]:
                    if entryid in i["id"]:
                        title = i["longId"]
                        break

                directory = os.path.dirname(options.output)
                options.service = "disney"
                title = "%s-%s" % (title, options.service)
                title = filenamify(title)
                if len(directory):
                    options.output = "%s/%s" % (directory, title)
                else:
                    options.output = title

            if self.exclude(options):
                return

            url = "http://cdnapi.kaltura.com/html5/html5lib/v1.9.7.6/mwEmbedFrame.php?&wid=%s&uiconf_id=%s&entry_id=%s&playerId=%s&forceMobileHTML5=true&urid=1.9.7.6&callback=mwi" % \
            (partnerid, uiconfid, entryid, uniq)
            error, data = get_http_data(url)
            if error:
                log.error("Cant get video info")
                return
            match = re.search(r"mwi\(({.*})\);", data)
            jsondata = json.loads(match.group(1))
            data = jsondata["content"]
            match = re.search(r"window.kalturaIframePackageData = ({.*});", data)
            jsondata = json.loads(match.group(1))
            ks = jsondata["enviornmentConfig"]["ks"]
            if options.output_auto:
                name = jsondata["entryResult"]["meta"]["name"]
                directory = os.path.dirname(options.output)
                options.service = "disney"
                title = "%s-%s" % (name, options.service)
                title = filenamify(title)
                if len(directory):
                    options.output = "%s/%s" % (directory, title)
                else:
                    options.output = title

            url = "http://cdnapi.kaltura.com/p/%s/sp/%s00/playManifest/entryId/%s/format/applehttp/protocol/http/a.m3u8?ks=%s&referrer=aHR0cDovL3d3dy5kaXNuZXkuc2U=&" % (partnerid[1:], partnerid[1:], entryid, ks)
            redirect = check_redirect(url)
            streams = hlsparse(redirect)
            for n in list(streams.keys()):
                yield HLS(copy.copy(options), streams[n], n)