# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
import json
import re
import logging

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
        hdnea = self._login()
        url = data['streamUrls']['hls'] + hdnea
        yield from hlsparse(
            config=self.config, 
            res=self.http.request("get", url), 
            url=url, 
            output=self.output
        )
    
    def _get_service(self):
        try:
            url = self.url
            vid_ref = "video/"
            if not vid_ref in url:
                return None
            index = url.find(vid_ref)+len(vid_ref)
            service = url[index:].split("/")[0]
            return service
        
        except Exception as e:
            logging.error(f"Can't find service in video link")
            return None



    def _login(self):
        if (service := self._get_service()) is None:
            return None 
        if (token := self.config.get("token")) is None:
            return None
        
        # Get token
        if (r := self.http.request(
            "get",
            f"https://svp-token-api.aftonbladet.se/svp/token/{service}?access=plus",
            headers={"x-sp-id":token}
            )
        ).status_code != 200:
            logging.info(f"Can't get token")
            return None
        
        #hdnea-header with hmac encryption
        if (h:= self.http.request(
            "get",
            f"https://svp.vg.no/svp/token/v1/?vendor=ab&assetId={service}&expires={r.json()['expiry']}&hmac={r.json()['value']}",
            )
        ).status_code != 200:
            logging.info(f"Can't get hdnea header with hmac encryption")
            return None
        
        #URL encode hdnea
        hdnea =f"?hdnea={h.text.replace('/', '%2F').replace('=', '%3D').replace(',', '%2C')}" 
        
        return hdnea 


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
