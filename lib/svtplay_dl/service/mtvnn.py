from __future__ import absolute_import
import re
import json
import logging
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

from svtplay_dl.service import Service, OpenGraphThumbMixin
from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.hls import hlsparse


# This is _very_ similar to mtvservices..
class Mtvnn(Service, OpenGraphThumbMixin):
    supported_domains = ['nickelodeon.se', "nickelodeon.nl", "nickelodeon.no", "www.comedycentral.se", "nickelodeon.dk"]

    def get(self):
        data = self.get_urldata()
        parse = urlparse(self.url)

        if parse.netloc.endswith("se"):
            match = re.search(r'<div class="video-player" (.*)>', data)

            if not match:
                yield ServiceError("Can't find video info")
                return

            match_id = re.search(r'data-id="([0-9a-fA-F|\-]+)" ', match.group(1))

            if not match_id:
                yield ServiceError("Can't find video info")
                return

            wanted_id = match_id.group(1)
            url_service = "http://feeds.mtvnservices.com/od/feed/intl-mrss-player-feed?mgid=mgid:arc:episode:nick.intl:{0}" \
                          "&arcEp=nickelodeon.se&imageEp=nickelodeon.se&stage=staging&accountOverride=intl.mtvi.com&ep=a9cc543c".format(wanted_id)
            service_asset = self.http.request("get", url_service)
            match_guid = re.search('<guid isPermaLink="false">(.*)</guid>', service_asset.text)

            if not match_guid:
                yield ServiceError("Can't find video info")
                return

            hls_url = "https://mediautilssvcs-a.akamaihd.net/services/MediaGenerator/{0}?arcStage=staging&accountOverride=intl.mtvi.com&" \
                      "billingSection=intl&ep=a9cc543c&acceptMethods=hls".format(match_guid.group(1))
            hls_asset = self.http.request("get", hls_url)
            xml = ET.XML(hls_asset.text)

            if xml.find("./video") is not None and xml.find("./video").find("item") is not None \
                    and xml.find("./video").find("item").find("rendition") is not None \
                    and xml.find("./video").find("item").find("rendition").find("src") is not None:

                hls_url = xml.find("./video").find("item").find("rendition").find("src").text
                stream = hlsparse(self.config, self.http.request("get", hls_url), hls_url, output=self.output)
                for key in list(stream.keys()):
                    yield stream[key]
            return

        match = re.search(r'data-mrss=[\'"](http://gakusei-cluster.mtvnn.com/v2/mrss.xml[^\'"]+)[\'"]', data)
        if not match:
            yield ServiceError("Can't find id for the video")
            return

        mrssxmlurl = match.group(1)
        data = self.http.request("get", mrssxmlurl).content
        xml = ET.XML(data)
        title = xml.find("channel").find("item").find("title").text
        self.output["title"] = title

        match = re.search("gon.viacom_config=([^;]+);", self.get_urldata())
        if match:
            countrycode = json.loads(match.group(1))["country_code"].replace("_", "/")

            match = re.search("mtvnn.com:([^&]+)", mrssxmlurl)
            if match:
                urlpart = match.group(1).replace("-", "/").replace("playlist", "playlists")  # it use playlists dunno from where it gets it
                hlsapi = "http://api.mtvnn.com/v2/{0}/{1}.json?video_format=m3u8&callback=&".format(countrycode, urlpart)
                data = self.http.request("get", hlsapi).text

                dataj = json.loads(data)
                for i in dataj["local_playlist_videos"]:
                    streams = hlsparse(self.config, self.http.request("get", i["url"]), i["url"], output=self.output)
                    for n in list(streams.keys()):
                        yield streams[n]

    def find_all_episodes(self, config):
        match = re.search(r"data-franchise='([^']+)'", self.get_urldata())
        if match is None:
            logging.error("Couldn't program id")
            return
        programid = match.group(1)
        match = re.findall(r"<li class='([a-z]+ )?playlist-item( [a-z]+)*?'( data-[-a-z]+='[^']+')* data-item-id='([^']+)'",
                           self.get_urldata())
        if not match:
            logging.error("Couldn't retrieve episode list")
            return
        episodNr = []
        for i in match:
            episodNr.append(i[3])
        episodes = []
        n = 0
        for i in sorted(episodNr):
            if n == config.get("all_last"):
                break
            episodes.append("http://www.nickelodeon.se/serier/{0}-something/videos/{1}-something".format(programid, i))
            n += 1
        return episodes


class MtvMusic(Service, OpenGraphThumbMixin):
    supported_domains = ['mtv.se']

    def get(self):
        data = self.get_urldata()

        match = re.search('window.pagePlaylist = (.*);', data)
        if not match:
            yield ServiceError("Can't find video info")
            return

        try:
            janson = json.loads(match.group(1))
        except Exception:
            yield ServiceError("Can't decode api request: {0}".format(match.group(1)))
            return

        parse = urlparse(self.url)
        wanted_id = parse.path.split("/")[-1].split("-")[0]

        for n in janson:
            if wanted_id == str(n["id"]):

                mrssxmlurl = "http://media-utils.mtvnservices.com/services/MediaGenerator/" \
                             "mgid:arc:video:mtv.se:{0}?acceptMethods=hls".format(n["video_token"])
                hls_asset = self.http.request("get", mrssxmlurl)
                xml = ET.XML(hls_asset.text)

                if xml.find("./video") is not None and xml.find("./video").find("item") is not None and \
                   xml.find("./video").find("item").find("rendition") is not None and \
                   xml.find("./video").find("item").find("rendition").find("src") is not None:

                    hls_url = xml.find("./video").find("item").find("rendition").find("src").text
                    stream = hlsparse(self.config, self.http.request("get", hls_url), hls_url, output=self.output)
                    if stream:

                        for key in list(stream.keys()):
                                yield stream[key]
