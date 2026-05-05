# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
import copy
import json
import re

from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.http import HTTP
from svtplay_dl.service import OpenGraphThumbMixin
from svtplay_dl.service import Service


class Sr(Service, OpenGraphThumbMixin):
    supported_domains = ["sverigesradio.se"]

    def get(self):
        data = self.get_urldata()
        janson = self._get_janson(data)

        if janson and "episode" in janson:
            audio_types = [
                ("podcast", ""),
                ("broadcast", "musik"),
            ]
            for audio_type, lang in audio_types:
                quality = janson["episode"]["audio"].get(audio_type)
                if quality:
                    url = (quality["qualities"].get("high") or quality["qualities"].get("standard") or {}).get("url")
                    if url:
                        yield HTTP(copy.copy(self.config), url, 128, output=self.output, language=lang)
            return
        elif janson and "article" in janson:
            quality = janson["article"]["playAudio"]
            url = (quality["qualities"].get("high") or quality["qualities"].get("standard") or {}).get("url")
            if url:
                yield HTTP(copy.copy(self.config), url, 128, output=self.output)
            return

        match = re.search(r'content="sesrplay://play/(\w+)/(\d+)"', data)
        if match:
            yield from self.webapi(match.group(2), match.group(1))
            return

        yield ServiceError("Can't find audio info")
        return

    def webapi(self, aid, what):
        res = self.http.get(f"https://web-api.sr.se/v1/player/ondemand?id={aid}&type={what}")
        if not res.ok:
            yield ServiceError("Can't find audio info")
            return

        audiourl = min(res.json()["item"]["audio"]["src"], key=self.priority, default=None)
        yield HTTP(copy.copy(self.config), audiourl, 128, output=self.output)

    def priority(self, line):
        if line.endswith("-hi"):
            return 0
        if line.endswith("-lo"):
            return 2
        return 1

    def _get_janson(self, urldata):
        match = re.findall(r"__next_f\.push\((.+?)\)</script>", urldata, re.DOTALL)
        for i in match:
            janson = json.loads(i)
            for jsonlist in janson:
                if isinstance(jsonlist, str):
                    index = jsonlist.find(":")
                    if index > 0:
                        if jsonlist[index + 1 :].startswith("["):
                            rawdata = jsonlist[index + 1 :]
                            try:
                                json_raw = json.loads(rawdata)
                            except json.JSONDecodeError:
                                continue
                            # news
                            found = self.find_dict_with_keys(json_raw, ["showSurvey", "article"])
                            if found:
                                return found
                            # episodes
                            found = self.find_dict_with_keys(json_raw, ["episode", "episodeCollections", "trackList"])
                            if found:
                                return found

        return None

    def find_dict_with_keys(self, obj, required_keys):
        if isinstance(obj, dict):
            if all(k in obj for k in required_keys):
                return obj
            for value in obj.values():
                result = self.find_dict_with_keys(value, required_keys)
                if result is not None:
                    return result
        elif isinstance(obj, list):
            for item in obj:
                result = self.find_dict_with_keys(item, required_keys)
                if result is not None:
                    return result
        return None
