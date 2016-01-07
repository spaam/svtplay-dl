# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import re
from svtplay_dl.service.svtplay import Svtplay
from svtplay_dl.log import log


class OppetArkiv(Svtplay):
    supported_domains = ['oppetarkiv.se']

    def find_all_episodes(self, options):
        page = 1
        data = self.get_urldata()
        match = re.search(r'"/etikett/titel/([^"/]+)', data)
        if match is None:
            match = re.search(r'"http://www.oppetarkiv.se/etikett/titel/([^/]+)/', self.url)
            if match is None:
                log.error("Couldn't find title")
                return
        program = match.group(1)
        episodes = []

        n = 0
        if self.options.all_last > 0:
            sort = "tid_fallande"
        else:
            sort = "tid_stigande"

        while True:
            url = "http://www.oppetarkiv.se/etikett/titel/%s/?sida=%s&sort=%s&embed=true" % (program, page, sort)
            data = self.http.request("get", url)
            if data.status_code == 404:
                break

            data = data.text
            regex = re.compile(r'href="(/video/[^"]+)"')
            for match in regex.finditer(data):
                if n == self.options.all_last:
                    break
                episodes.append("http://www.oppetarkiv.se%s" % match.group(1))
                n += 1
            page += 1

        return episodes
