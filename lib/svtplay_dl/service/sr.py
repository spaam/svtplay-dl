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
        payload = ""
        for i in match:
            for jsonlist in json.loads(i):
                if isinstance(jsonlist, str):
                    payload += jsonlist

        for row in self._rsc_rows(payload):
            if not row.startswith("["):
                continue
            try:
                json_raw = json.loads(row)
            except json.JSONDecodeError:
                continue
            # news
            found = self.find_dict_with_keys(json_raw, ["article"])
            if found and isinstance(found["article"], dict) and "playAudio" in found["article"]:
                return found
            # episodes
            found = self.find_dict_with_keys(json_raw, ["episode", "episodeCollections", "trackList"])
            if found:
                return found

        return None

    def _rsc_rows(self, payload):
        # react server components payload: "id:value\n" rows, except text rows "id:T<hexlen>,<text>"
        # which are length prefixed (in utf-8 bytes), may contain newlines and have no row terminator
        data = payload.encode("utf-8")
        pos = 0
        while pos < len(data):
            colon = data.find(b":", pos)
            if colon < 0:
                return
            match = re.match(rb"T([0-9a-fA-F]+),", data[colon + 1 : colon + 20])
            if match:
                start = colon + 1 + match.end()
                pos = start + int(match.group(1), 16)
                yield data[start:pos].decode("utf-8", errors="replace")
                continue
            end = data.find(b"\n", colon)
            if end < 0:
                end = len(data)
            yield data[colon + 1 : end].decode("utf-8", errors="replace")
            pos = end + 1

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
