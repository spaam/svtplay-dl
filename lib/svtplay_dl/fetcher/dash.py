# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import copy
import xml.etree.ElementTree as ET


from svtplay_dl.output import progress_stream, output, ETA, progressbar
from svtplay_dl.utils.urllib import urljoin
from svtplay_dl.error import UIException, ServiceError
from svtplay_dl.fetcher import VideoRetriever


class DASHException(UIException):
    def __init__(self, url, message):
        self.url = url
        super(DASHException, self).__init__(message)


class LiveDASHException(DASHException):
    def __init__(self, url):
        super(LiveDASHException, self).__init__(
            url, "This is a live DASH stream, and they are not supported.")


def dashparse(options, res, url):
    streams = {}

    if res.status_code == 403 or res.status_code == 404:
        streams[0] = ServiceError("Can't read DASH playlist. {0}".format(res.status_code))
        return streams
    xml = ET.XML(res.text)
    baseurl = urljoin(url, xml.find("{urn:mpeg:dash:schema:mpd:2011}BaseURL").text)
    videofiles = xml.findall(".//{urn:mpeg:dash:schema:mpd:2011}AdaptationSet[@contentType='video']/{urn:mpeg:dash:schema:mpd:2011}Representation")

    audiofiles = xml.findall(".//{urn:mpeg:dash:schema:mpd:2011}AdaptationSet[@contentType='audio']/{urn:mpeg:dash:schema:mpd:2011}Representation")
    for i in audiofiles:
        audiourl = urljoin(baseurl, i.find("{urn:mpeg:dash:schema:mpd:2011}BaseURL").text)
        audiobitrate = float(i.attrib["bandwidth"]) / 1000
        for n in videofiles:
            bitrate = float(n.attrib["bandwidth"])/1000 + audiobitrate
            videourl = urljoin(baseurl, n.find("{urn:mpeg:dash:schema:mpd:2011}BaseURL").text)
            options.other = "mp4"
            streams[int(bitrate)] = DASH(copy.copy(options), videourl, bitrate, cookies=res.cookies, audio=audiourl)

    return streams


class DASH(VideoRetriever):
    def name(self):
        return "dash"

    def download(self):
        if self.options.live and not self.options.force:
            raise LiveDASHException(self.url)

        if self.audio:
            self._download(self.audio, audio=True)
        self._download(self.url)


    def _download(self, url, audio=False):
        cookies = self.kwargs["cookies"]
        data = self.http.request("get", url, cookies=cookies, headers={'Range': 'bytes=0-8192'})
        try:
            total_size = data.headers['Content-Range']
            total_size = total_size[total_size.find("/")+1:]
        except KeyError:
            total_size = 0
        total_size = int(total_size)
        bytes_so_far = 8192
        if audio:
            file_d = output(copy.copy(self.options), "m4a")
        else:
            file_d = output(self.options, self.options.other)
        if hasattr(file_d, "read") is False:
            return
        file_d.write(data.content)
        eta = ETA(total_size)
        while bytes_so_far < total_size:
            old = bytes_so_far + 1
            bytes_so_far = old + 1000000
            if bytes_so_far > total_size:
                bytes_so_far = total_size

            bytes_range = "bytes=%s-%s" % (old, bytes_so_far)

            data = self.http.request("get", url, cookies=cookies, headers={'Range': bytes_range})
            file_d.write(data.content)
            if self.options.output != "-" and not self.options.silent:
                eta.update(old)
                progressbar(total_size, old, ''.join(["ETA: ", str(eta)]))

        if self.options.output != "-":
            file_d.close()
            progressbar(bytes_so_far, total_size, "ETA: complete")
            progress_stream.write('\n')
            self.finished = True
