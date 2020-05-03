# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
import copy
import json
import re
from urllib.parse import urlparse

from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.fetcher.http import HTTP
from svtplay_dl.service import OpenGraphThumbMixin
from svtplay_dl.service import Service


class Disney(Service, OpenGraphThumbMixin):
    supported_domains = ["disney.se", "video.disney.se", "disneyjunior.disney.se"]

    def get(self):
        parse = urlparse(self.url)
        if parse.hostname == "video.disney.se" or parse.hostname == "disneyjunior.disney.se":
            data = self.get_urldata()
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
                                    res = self.http.get(i["url"])
                                    match = re.search('button primary" href="([^"]+)"', res.text)
                                    if match:
                                        yield HTTP(copy.copy(self.config), match.group(1), i["bitrate"], output=self.output)
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
                entry = parse.fragment[parse.fragment.rindex("/") + 1 :]
                if entry in jsondata["idlist"]:
                    entryid = jsondata["idlist"][entry]
                else:
                    yield ServiceError("Cant find video info")
                    return
            for i in jsondata["playlists"][0]["playlist"]:
                if entryid in i["id"]:
                    title = i["longId"]
                    break
            self.output["title"] = title

            url = (
                "http://cdnapi.kaltura.com/html5/html5lib/v1.9.7.6/mwEmbedFrame.php?&wid={}&uiconf_id={}&entry_id={}"
                "&playerId={}&forceMobileHTML5=true&urid=1.9.7.6&callback=mwi".format(partnerid, uiconfid, entryid, uniq)
            )
            data = self.http.request("get", url).text
            match = re.search(r"mwi\(({.*})\);", data)
            jsondata = json.loads(match.group(1))
            data = jsondata["content"]
            match = re.search(r"window.kalturaIframePackageData = ({.*});", data)
            jsondata = json.loads(match.group(1))
            ks = jsondata["enviornmentConfig"]["ks"]
            name = jsondata["entryResult"]["meta"]["name"]
            self.output["title"] = name

            url = (
                "http://cdnapi.kaltura.com/p/{}/sp/{}00/playManifest/entryId/{}/format/applehttp/protocol/http/a.m3u8"
                "?ks={}&referrer=aHR0cDovL3d3dy5kaXNuZXkuc2U=&".format(partnerid[1:], partnerid[1:], entryid, ks)
            )
            redirect = self.http.check_redirect(url)
            streams = hlsparse(self.config, self.http.request("get", redirect), redirect, output=self.output)
            for n in list(streams.keys()):
                yield streams[n]
