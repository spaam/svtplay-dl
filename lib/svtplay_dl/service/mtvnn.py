import json
import logging
import re
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.service import OpenGraphThumbMixin
from svtplay_dl.service import Service


# This is _very_ similar to mtvservices..
class Mtvnn(Service, OpenGraphThumbMixin):
    supported_domains = ["nickelodeon.se", "nickelodeon.nl", "nickelodeon.no", "www.comedycentral.se", "nickelodeon.dk"]

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
            url_service = (
                f"http://feeds.mtvnservices.com/od/feed/intl-mrss-player-feed?mgid=mgid:arc:episode:nick.intl:{wanted_id}"
                "&arcEp=nickelodeon.se&imageEp=nickelodeon.se&stage=staging&accountOverride=intl.mtvi.com&ep=a9cc543c"
            )
            service_asset = self.http.request("get", url_service)
            match_guid = re.search('<guid isPermaLink="false">(.*)</guid>', service_asset.text)

            if not match_guid:
                yield ServiceError("Can't find video info")
                return

            hls_url = (
                f"https://mediautilssvcs-a.akamaihd.net/services/MediaGenerator/{match_guid.group(1)}?arcStage=staging&accountOverride=intl.mtvi.com&"
                "billingSection=intl&ep=a9cc543c&acceptMethods=hls"
            )
            hls_asset = self.http.request("get", hls_url)
            xml = ET.XML(hls_asset.text)

            if (
                xml.find("./video") is not None
                and xml.find("./video").find("item") is not None
                and xml.find("./video").find("item").find("rendition") is not None
                and xml.find("./video").find("item").find("rendition").find("src") is not None
            ):

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
                hlsapi = f"http://api.mtvnn.com/v2/{countrycode}/{urlpart}.json?video_format=m3u8&callback=&"
                data = self.http.request("get", hlsapi).text

                dataj = json.loads(data)
                for i in dataj["local_playlist_videos"]:
                    yield from hlsparse(self.config, self.http.request("get", i["url"]), i["url"], output=self.output)

    def find_all_episodes(self, config):
        episodes = []
        match = re.search(r"data-franchise='([^']+)'", self.get_urldata())
        if match is None:
            logging.error("Couldn't program id")
            return episodes
        programid = match.group(1)
        match = re.findall(r"<li class='([a-z]+ )?playlist-item( [a-z]+)*?'( data-[-a-z]+='[^']+')* data-item-id='([^']+)'", self.get_urldata())
        if not match:
            logging.error("Couldn't retrieve episode list")
            return episodes
        episodNr = []
        for i in match:
            episodNr.append(i[3])

        n = 0
        for i in sorted(episodNr):
            if n == config.get("all_last"):
                break
            episodes.append(f"http://www.nickelodeon.se/serier/{programid}-something/videos/{i}-something")
            n += 1
        return episodes


class MtvMusic(Service, OpenGraphThumbMixin):
    supported_domains = ["mtv.se"]

    def get(self):
        data = self.get_urldata()

        match = re.search("window.pagePlaylist = (.*);", data)
        if not match:
            yield ServiceError("Can't find video info")
            return

        try:
            janson = json.loads(match.group(1))
        except Exception:
            yield ServiceError(f"Can't decode api request: {match.group(1)}")
            return

        parse = urlparse(self.url)
        wanted_id = parse.path.split("/")[-1].split("-")[0]

        for n in janson:
            if wanted_id == str(n["id"]):
                mrssxmlurl = f"http://media-utils.mtvnservices.com/services/MediaGenerator/mgid:arc:video:mtv.se:{n['video_token']}?acceptMethods=hls"
                hls_asset = self.http.request("get", mrssxmlurl)
                xml = ET.XML(hls_asset.text)

                if (
                    xml.find("./video") is not None
                    and xml.find("./video").find("item") is not None
                    and xml.find("./video").find("item").find("rendition") is not None
                    and xml.find("./video").find("item").find("rendition").find("src") is not None
                ):

                    hls_url = xml.find("./video").find("item").find("rendition").find("src").text
                    yield from hlsparse(self.config, self.http.request("get", hls_url), hls_url, output=self.output)
