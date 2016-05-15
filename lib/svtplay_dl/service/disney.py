# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-

from __future__ import absolute_import
import json
import re
import copy
import os

from svtplay_dl.service import Service, OpenGraphThumbMixin
from svtplay_dl.utils import filenamify
from svtplay_dl.utils.urllib import urlparse
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.fetcher.http import HTTP
from svtplay_dl.error import ServiceError


class Disney(Service, OpenGraphThumbMixin):
    supported_domains = ['disney.se', 'video.disney.se', 'disneyjunior.disney.se']

    def get(self):
        parse = urlparse(self.url)
        if parse.hostname == "video.disney.se" or parse.hostname == "disneyjunior.disney.se":
            data = self.get_urldata()

            if self.exclude():
                yield ServiceError("Excluding video")
                return

            match = re.search(r"Grill.burger=({.*}):", data)
            if not match:
                yield ServiceError("Can't find video info")
                return
            jsondata = json.loads(match.group(1))
            for n in jsondata["stack"]:
                if len(n["data"]) > 0:
                    for x in n["data"]:
                        if "flavors" in x:
                            for i in x["flavors"]:
                                if i["format"] == "mp4":
                                    yield HTTP(copy.copy(self.options), i["url"], i["bitrate"])
        else:
            data = self.get_urldata()
            match = re.search(r"uniqueId : '([^']+)'", data)
            if not match:
                yield ServiceError("Can't find video info")
                return
            uniq = match.group(1)
            match = re.search("entryId : '([^']+)'", self.get_urldata())
            entryid = match.group(1)
            match = re.search("partnerId : '([^']+)'", self.get_urldata())
            partnerid = match.group(1)
            match = re.search("uiConfId : '([^']+)'", self.get_urldata())
            uiconfid = match.group(1)

            match = re.search("json : ({.*}}),", self.get_urldata())
            jsondata = json.loads(match.group(1))
            parse = urlparse(self.url)
            if len(parse.fragment) > 0:
                entry = parse.fragment[parse.fragment.rindex("/")+1:]
                if entry in jsondata["idlist"]:
                    entryid = jsondata["idlist"][entry]
                else:
                    yield ServiceError("Cant find video info")
                    return
            if self.options.output_auto:
                for i in jsondata["playlists"][0]["playlist"]:
                    if entryid in i["id"]:
                        title = i["longId"]
                        break

                directory = os.path.dirname(self.options.output)
                self.options.service = "disney"
                title = "%s-%s" % (title, self.options.service)
                title = filenamify(title)
                if len(directory):
                    self.options.output = os.path.join(directory, title)
                else:
                    self.options.output = title

            url = "http://cdnapi.kaltura.com/html5/html5lib/v1.9.7.6/mwEmbedFrame.php?&wid=%s&uiconf_id=%s&entry_id=%s&playerId=%s&forceMobileHTML5=true&urid=1.9.7.6&callback=mwi" % \
            (partnerid, uiconfid, entryid, uniq)
            data = self.http.request("get", url).text
            match = re.search(r"mwi\(({.*})\);", data)
            jsondata = json.loads(match.group(1))
            data = jsondata["content"]
            match = re.search(r"window.kalturaIframePackageData = ({.*});", data)
            jsondata = json.loads(match.group(1))
            ks = jsondata["enviornmentConfig"]["ks"]
            if self.options.output_auto:
                name = jsondata["entryResult"]["meta"]["name"]
                directory = os.path.dirname(self.options.output)
                self.options.service = "disney"
                title = "%s-%s" % (name, self.options.service)
                title = filenamify(title)
                if len(directory):
                    self.options.output = os.path.join(directory, title)
                else:
                    self.options.output = title

            if self.exclude():
                return

            url = "http://cdnapi.kaltura.com/p/%s/sp/%s00/playManifest/entryId/%s/format/applehttp/protocol/http/a.m3u8?ks=%s&referrer=aHR0cDovL3d3dy5kaXNuZXkuc2U=&" % (partnerid[1:], partnerid[1:], entryid, ks)
            redirect = self.http.check_redirect(url)
            streams = hlsparse(self.options, self.http.request("get", redirect), redirect)
            for n in list(streams.keys()):
                yield streams[n]