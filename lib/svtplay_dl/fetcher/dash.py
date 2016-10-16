# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import copy
import xml.etree.ElementTree as ET
import os
import re


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

    if not res:
        return None

    if res.status_code >= 400:
        streams[0] = ServiceError("Can't read DASH playlist. {0}".format(res.status_code))
        return streams
    xml = ET.XML(res.text)
    if "isoff-on-demand" in xml.attrib["profiles"]:
        try:
            baseurl = urljoin(url, xml.find("{urn:mpeg:dash:schema:mpd:2011}BaseURL").text)
        except AttributeError:
            streams[0] = ServiceError("Can't parse DASH playlist")
            return
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
    if "isoff-live" in xml.attrib["profiles"]:
        video = xml.findall(".//{urn:mpeg:dash:schema:mpd:2011}AdaptationSet[@contentType='video']")
        if len(video) == 0:
            video = xml.findall(".//{urn:mpeg:dash:schema:mpd:2011}AdaptationSet[@mimeType='video/mp4']")
        audio = xml.findall(".//{urn:mpeg:dash:schema:mpd:2011}AdaptationSet[@contentType='audio']")
        if len(audio) == 0:
            audio = xml.findall(".//{urn:mpeg:dash:schema:mpd:2011}AdaptationSet[@mimeType='audio/mp4']")
        videofiles = parsesegments(video, url)
        audiofiles = parsesegments(audio, url)
        for i in videofiles.keys():
            bitrate = (int(i) + int(list(audiofiles.keys())[0])) /1000
            options.other = "mp4"
            streams[int(bitrate)] = DASH(copy.copy(options), url, bitrate, cookies=res.cookies, audio=audiofiles[list(audiofiles.keys())[0]], files=videofiles[i])

    return streams

def parsesegments(content, url):
    scheme = content[0].find("{urn:mpeg:dash:schema:mpd:2011}SegmentTemplate").attrib["media"]

    nrofvideos = content[0].findall(".//{urn:mpeg:dash:schema:mpd:2011}S[@r]")
    selemtns = content[0].findall(".//{urn:mpeg:dash:schema:mpd:2011}S")
    if nrofvideos:
        total = int(nrofvideos[0].attrib["r"]) + len(selemtns) + 1
        time = False
    else:
        time = []
        time.append(0)
        for i in selemtns:
            time.append(int(i.attrib["d"]))
    elements = content[0].findall(".//{urn:mpeg:dash:schema:mpd:2011}Representation")
    files = {}
    for i in elements:
        id = i.attrib["id"]
        segments = []
        bitrate = int(i.attrib["bandwidth"])
        vinit = content[0].find("{urn:mpeg:dash:schema:mpd:2011}SegmentTemplate").attrib["initialization"].replace(
            "$RepresentationID$", id)
        dirname = os.path.dirname(url) + "/"
        segments.append(urljoin(dirname, vinit))
        name = scheme.replace("$RepresentationID$", id)
        if "$Number" in name:
            match = re.search("\$Number(\%\d+)d\$", name)
            if match:
                name = name.replace("$Number", "").replace("$", "")
                for n in range(1, total):
                    segments.append(urljoin(dirname, name % n))
        if "$Time$" in name:
            match = re.search("\$Time\$", name)
            if match:
                number = 0
                for n in time:
                    number += int(n)
                    new = name.replace("$Time$", str(number))
                    segments.append(urljoin(dirname, new))
        files[bitrate] = segments
    return files


class DASH(VideoRetriever):
    def name(self):
        return "dash"

    def download(self):
        if self.options.live and not self.options.force:
            raise LiveDASHException(self.url)

        if self.files:
            if self.audio:
                self._download2(self.audio, audio=True)
            self._download2(self.files)
        else:
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

    def _download2(self, files, audio=False):
        cookies = self.kwargs["cookies"]

        if audio:
            file_d = output(copy.copy(self.options), "m4a")
        else:
            file_d = output(self.options, self.options.other)
        if hasattr(file_d, "read") is False:
            return
        eta = ETA(len(files))
        n = 1
        for i in files:
            if self.options.output != "-" and not self.options.silent:
                eta.increment()
                progressbar(len(files), n, ''.join(['ETA: ', str(eta)]))
                n += 1
            data = self.http.request("get", i, cookies=cookies)

            if data.status_code == 404:
                break
            data = data.content
            file_d.write(data)

        if self.options.output != "-":
            file_d.close()
            if not self.options.silent:
                progress_stream.write('\n')
            self.finished = True
