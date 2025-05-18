# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
import json
import re

from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.service import Service
from svtplay_dl.utils.text import decode_html_entities


class Aftonbladettv(Service):
    supported_domains = ["svd.se", "tv.aftonbladet.se"]

    def get(self):
        data = self.get_urldata()
        match = re.search('data-player-config="([^"]+)"', data)
        if not match:
            match = re.search('data-svpPlayer-video="([^"]+)"', data)
            if not match:
                match = re.search("window.ASSET = ({.*})", data)
                if not match:
                    yield ServiceError("Can't find video info")
                    return
        data = json.loads(decode_html_entities(match.group(1)))
        query = self._login()
        base_url = data["streamUrls"]["hls"]
        url = base_url + query if query else base_url
        yield from hlsparse(config=self.config, res=self.http.request("get", url), url=url, output=self.output)

    def _login(self):
        token = self.config.get("token")
        if not token:
            return None

        match = re.search(r"^https://tv\.aftonbladet\.se/video/(\d+)", self.url)
        if not match:
            return None
        video_id = match.group(1)

        details_url = f"https://svp.vg.no/svp/api/v1/ab/assets/{video_id}?additional=access&appName=abtv-frontend-production"
        res = self.http.request("get", details_url)
        if res.status_code != 200:
            return None

        access_info = res.json().get("additional", {}).get("access", {})
        if not access_info:
            return None

        access_type = None
        if access_info.get("login"):
            access_type = "login"
        elif access_info.get("plus"):
            access_type = "plus"
        else:
            return None

        token_url = f"https://svp-token-api.aftonbladet.se/svp/token/{video_id}?access={access_type}"
        res = self.http.request("get", token_url, headers={"x-sp-id": token})
        if res.status_code != 200:
            return None
        auth_data = res.json()
        expiry = auth_data["expiry"]
        hmac_token = auth_data["value"]

        hdnea_url = f"https://svp.vg.no/svp/token/v1/?vendor=ab&assetId={video_id}&expires={expiry}&hmac={hmac_token}"
        res = self.http.request("get", hdnea_url)
        if res.status_code != 200:
            return None

        return f"?hdnea={res.text.replace('/', '%2F').replace('=', '%3D').replace(',', '%2C')}"


class Aftonbladet(Service):
    supported_domains = ["aftonbladet.se"]

    def get(self):
        data = self.get_urldata()

        match = re.search("window.FLUX_STATE = ({.*})</script>", data)
        if not match:
            yield ServiceError("Can't find video info")
            return

        try:
            janson = json.loads(match.group(1))
        except json.decoder.JSONDecodeError:
            yield ServiceError(f"Can't decode api request: {match.group(1)}")
            return

        videos = self._get_video(janson)
        yield from videos

    def _get_video(self, janson):
        collections = janson["collections"]
        for n in list(collections.keys()):
            contents = collections[n]["contents"]["items"]
            for i in list(contents.keys()):
                if "type" in contents[i] and contents[i]["type"] == "video":
                    streams = hlsparse(
                        self.config,
                        self.http.request("get", contents[i]["videoAsset"]["streamUrls"]["hls"]),
                        contents[i]["videoAsset"]["streamUrls"]["hls"],
                        output=self.output,
                    )
                    for key in list(streams.keys()):
                        yield streams[key]
