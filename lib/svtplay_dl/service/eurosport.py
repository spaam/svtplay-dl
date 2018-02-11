from __future__ import absolute_import
import re
import json
import uuid

from svtplay_dl.service import Service
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.utils.urllib import urlparse, quote
from svtplay_dl.error import ServiceError


class Eurosport(Service):
    supported_domains = ['se.eurosportplayer.com']

    def get(self):
        parse = urlparse(self.url)
        match = re.search('window.server_path = ({.*});', self.get_urldata())
        if not match:
            yield ServiceError("Cant find api key")
            return

        janson = json.loads(match.group(1))
        clientid = janson["sdk"]["clientId"]
        clientapikey = janson["sdk"]["clientApiKey"]

        token = "https://global-api.svcs.eurosportplayer.com/token"
        header = {"authorization": "Bearer {}".format(clientapikey)}
        data = {"grant_type": "client_credentials", "latitude": 0, "longitude": 0, "platform": "browser", "token": str(uuid.uuid4())}
        res = self.http.post(token, headers=header, data=data)
        access_token = res.json()["access_token"]

        logindict = {"type": "email-password", "email": {"address": self.options.username}, "password": {"value": self.options.password}}

        res = self.http.post("https://eu-west-1-api.svcs.eurosportplayer.com/v2/user/identity", json=logindict,
                             headers={"authorization": access_token, "Accept": "application/vnd.identity-service+json; version=1.0"})
        if res.status_code > 400:
            yield ServiceError("Wrong username or password")
            return

        data = {"grant_type": "urn:mlbam:params:oauth:grant_type:token", "latitude": "0", "longitude": "0", "platform": "browser", "token": res.json()["code"]}
        header = {"authorization": "Bearer {}".format(clientapikey)}
        res = self.http.post("https://global-api.svcs.eurosportplayer.com/token", headers=header, data=data)
        refresh = res.json()["refresh_token"]

        data = {"grant_type": "refresh_token", "latitude": 0, "longitude": 0, "platform": "browser", "token": refresh}
        header = {"authorization": "Bearer {}".format(clientapikey)}
        res = self.http.post("https://global-api.svcs.eurosportplayer.com/token", headers=header, data=data)
        access_token = res.json()["access_token"]

        url = "https://bam-sdk-configs.mlbam.net/v0.1/{}/browser/v2.1/macosx/chrome/prod.json".format(clientid)
        res = self.http.get(url)
        janson = res.json()
        scenario = janson["media"]["playbackScenarios"]["unlimited"]

        query = {"preferredLanguages": ["sv", "en"], "mediaRights": ["GeoMediaRight"], "uiLang": "sv", "include_images": True}

        if parse.path[:5] == "/chan":
            pagetype = "channel"
            match = re.search('/([^/]+)$', parse.path)
            if not match:
                yield ServiceError("Cant find channel")
                return

            vid, = match.groups()
            query["pageType"] = pagetype
            query["channelCallsign"] = vid
            query["channelCallsigns"] = vid
            query["onAir"] = True

            self.options.live = True  # lets override to true

            url = "https://search-api.svcs.eurosportplayer.com/svc/search/v2/graphql/persisted/query/eurosport/web/Airings/onAir?variables={}".format(quote(json.dumps(query)))
            res = self.http.get(url, headers={"authorization": access_token})
            vid2 = res.json()["data"]["Airings"][0]["channel"]["id"]
            url = "https://global-api.svcs.eurosportplayer.com/channels/{}/scenarios/{}".format(vid2, scenario)
            res = self.http.get(url, headers={"authorization": access_token, "Accept": "application/vnd.media-service+json; version=1"})
            hls_url = res.json()["stream"]["slide"]
        else:
            pagetype = "event"
            match = re.search('/([^/]+)/([^/]+)$', parse.path)
            if not match:
                yield ServiceError("Cant fint event id")
                return

            query["title"], query["contentId"] = match.groups()
            query["pageType"] = pagetype

            url = "https://search-api.svcs.eurosportplayer.com/svc/search/v2/graphql/persisted/query/eurosport/Airings?variables={}".format(quote(json.dumps(query)))
            res = self.http.get(url, headers={"authorization": access_token})
            programid = res.json()["data"]["Airings"][0]["programId"]
            mediaid = res.json()["data"]["Airings"][0]["mediaId"]

            url = "https://global-api.svcs.eurosportplayer.com/programs/{}/media/{}/scenarios/{}".format(programid, mediaid, scenario)
            res = self.http.get(url, headers={"authorization": access_token, "Accept": "application/vnd.media-service+json; version=1"})
            hls_url = res.json()["stream"]["complete"]

        streams = hlsparse(self.options, self.http.request("get", hls_url), hls_url, authorization=access_token)
        if streams:
            for n in list(streams.keys()):
                yield streams[n]
