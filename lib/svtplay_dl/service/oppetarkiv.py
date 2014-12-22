# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import re

from svtplay_dl.utils import get_http_data
from svtplay_dl.service.svtplay import Svtplay
from svtplay_dl.log import log

class OppetArkiv(Svtplay):
    supported_domains = ['oppetarkiv.se']

    def find_all_episodes(self, options):
        page = 1
        error, data = self.get_urldata()
        if error:
            log.error("Cant get web page")
            return
        match = re.search(r'"http://www.oppetarkiv.se/etikett/titel/([^"/]+)', data)
        if match is None:
            match = re.search(r'"http://www.oppetarkiv.se/etikett/titel/([^"/]+)', self.url)
            if match is None:
                log.error("Couldn't find title")
                return
        program = match.group(1)
        more = True
        episodes = []

        n = 0
        if options.all_last > 0:
            sort = "tid_fallande"
        else:
            sort = "tid_stigande"

        while more:
            url = "http://www.oppetarkiv.se/etikett/titel/%s/?sida=%s&sort=%s&embed=true" % (program, page, sort)
            error, data = get_http_data(url)
            visa = re.search(r'svtXColorDarkLightGrey', data)
            if not visa:
                more = False
            regex = re.compile(r'(http://www.oppetarkiv.se/video/[^"]+)')
            for match in regex.finditer(data):
                if n == options.all_last:
                    break
                episodes.append(match.group(1))
                n += 1
            page += 1

        return episodes
