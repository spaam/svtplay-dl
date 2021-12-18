import json
import re
from urllib.parse import quote
from urllib.parse import urlparse

from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.service import Service


class Eurosport(Service):
    supported_domains_re = [r"^([^.]+\.)*eurosportplayer.com"]

    def get(self):
        parse = urlparse(self.url)
        match = re.search("window.server_path = ({.*});", self.get_urldata())
        if not match:
            yield ServiceError("Cant find api key")
            return

        janson = json.loads(match.group(1))
        clientapikey = janson["sdk"]["clientApiKey"]

        header = {"authorization": f"Bearer {clientapikey}"}
        res = self.http.post(
            "https://eu.edge.bamgrid.com/devices",
            headers=header,
            json={"deviceFamily": "browser", "applicationRuntime": "firefox", "deviceProfile": "macosx", "attributes": {}},
        )
        res = self.http.post(
            "https://eu.edge.bamgrid.com/token",
            headers=header,
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
                "latitude": 0,
                "longitude": 0,
                "platform": "browser",
                "subject_token": res.json()["assertion"],
                "subject_token_type": "urn:bamtech:params:oauth:token-type:device",
            },
        )

        header = {"authorization": f"Bearer {res.json()['access_token']}"}
        res = self.http.post(
            "https://eu.edge.bamgrid.com/idp/login",
            headers=header,
            json={"email": self.config.get("username"), "password": self.config.get("password")},
        )
        if res.status_code > 400:
            yield ServiceError("Wrong username or password")
            return

        grant = "https://eu.edge.bamgrid.com/accounts/grant"
        res = self.http.post(grant, headers=header, json={"id_token": res.json()["id_token"]})
        header = {"authorization": f"Bearer {clientapikey}"}
        res = self.http.post(
            "https://eu.edge.bamgrid.com/token",
            headers=header,
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
                "latitude": 0,
                "longitude": 0,
                "platform": "browser",
                "subject_token": res.json()["assertion"],
                "subject_token_type": "urn:bamtech:params:oauth:token-type:account",
            },
        )
        access_token = res.json()["access_token"]

        query = {"preferredLanguages": ["en"], "mediaRights": ["GeoMediaRight"], "uiLang": "en", "include_images": True}

        if parse.path[:11] == "/en/channel":
            pagetype = "channel"
            match = re.search("/([^/]+)$", parse.path)
            if not match:
                yield ServiceError("Cant find channel")
                return

            (vid,) = match.groups()
            query["pageType"] = pagetype
            query["channelCallsign"] = vid
            query["channelCallsigns"] = vid
            query["onAir"] = True

            self.config.set("live", True)  # lets override to true

            url = (
                "https://search-api.svcs.eurosportplayer.com/svc/search/v2/graphql/persisted/"
                f"query/eurosport/web/Airings/onAir?variables={quote(json.dumps(query))}"
            )
            res = self.http.get(url, headers={"authorization": access_token})
            vid2 = res.json()["data"]["Airings"][0]["channel"]["id"]
            url = f"https://global-api.svcs.eurosportplayer.com/channels/{vid2}/scenarios/browser"
            res = self.http.get(url, headers={"authorization": access_token, "Accept": "application/vnd.media-service+json; version=1"})
            hls_url = res.json()["stream"]["slide"]
        else:
            pagetype = "event"
            match = re.search("/([^/]+)/([^/]+)$", parse.path)
            if not match:
                yield ServiceError("Cant fint event id")
                return

            query["title"], query["contentId"] = match.groups()
            query["pageType"] = pagetype

            url = f"https://search-api.svcs.eurosportplayer.com/svc/search/v2/graphql/persisted/query/eurosport/Airings?variables={quote(json.dumps(query))}"
            res = self.http.get(url, headers={"authorization": access_token})
            programid = res.json()["data"]["Airings"][0]["programId"]
            mediaid = res.json()["data"]["Airings"][0]["mediaId"]

            url = f"https://global-api.svcs.eurosportplayer.com/programs/{programid}/media/{mediaid}/scenarios/browser"
            res = self.http.get(url, headers={"authorization": access_token, "Accept": "application/vnd.media-service+json; version=1"})
            hls_url = res.json()["stream"]["complete"]

        yield from hlsparse(self.config, self.http.request("get", hls_url), hls_url, authorization=access_token, output=self.output)
