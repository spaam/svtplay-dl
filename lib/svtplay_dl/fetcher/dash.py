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


def templateelemt(element, filename, idnumber):
    files = []

    init = element.attrib["initialization"]
    media = element.attrib["media"]
    if "startNumber" in element.attrib:
        start = int(element.attrib["startNumber"])
    else:
        start = 0
    timeline = element.find("{urn:mpeg:dash:schema:mpd:2011}SegmentTimeline")
    rvalue = timeline.findall(".//{urn:mpeg:dash:schema:mpd:2011}S[@r]")
    selements = timeline.findall(".//{urn:mpeg:dash:schema:mpd:2011}S")
    selements.pop()
    if rvalue:
        total = int(rvalue[0].attrib["r"]) + len(selements) + 1

    name = media.replace("$RepresentationID$", idnumber)
    files.append(urljoin(filename, init.replace("$RepresentationID$", idnumber)))

    if "$Time$" in media:
        time = []
        time.append(0)
        for n in selements:
            time.append(int(n.attrib["d"]))
        match = re.search("\$Time\$", name)
        if match:
            number = 0
            if len(selements) < 3:
                for n in range(start, start + total):
                    new = name.replace("$Time$", str(n * int(rvalue[0].attrib["d"])))
                    files.append(urljoin(filename, new))
            else:
                for n in time:
                    number += int(n)
                    new = name.replace("$Time$", str(number))
                    files.append(urljoin(filename, new))
    if "$Number" in name:
        if re.search("\$Number(\%\d+)d\$", name):
            vname = name.replace("$Number", "").replace("$", "")
            for n in range(start, start + total):
                files.append(urljoin(filename, vname % n))
        else:
            for n in range(start, start + total):
                newname = name.replace("$Number$", str(n))
                files.append(urljoin(filename, newname))
    return files


def adaptionset(element, url, baseurl=None):
    streams = {}

    dirname = os.path.dirname(url) + "/"
    if baseurl:
        dirname = urljoin(dirname, baseurl)

    template = element[0].find("{urn:mpeg:dash:schema:mpd:2011}SegmentTemplate")
    represtation = element[0].findall(".//{urn:mpeg:dash:schema:mpd:2011}Representation")

    for i in represtation:
        files = []
        segments = False
        filename = dirname
        bitrate = int(int(i.attrib["bandwidth"]) / 1000)
        idnumber = i.attrib["id"]

        if i.find("{urn:mpeg:dash:schema:mpd:2011}BaseURL") is not None:
            filename = urljoin(filename, i.find("{urn:mpeg:dash:schema:mpd:2011}BaseURL").text)

        if i.find("{urn:mpeg:dash:schema:mpd:2011}SegmentBase") is not None:
            files.append(filename)
        if template is not None:
            segments = True
            files = templateelemt(template, filename, idnumber)
        elif i.find("{urn:mpeg:dash:schema:mpd:2011}SegmentTemplate"):
            segments = True
            files = templateelemt(i.find("{urn:mpeg:dash:schema:mpd:2011}SegmentTemplate"), filename, idnumber)

        streams[bitrate] = {"segments": segments, "files": files}

    return streams


def dashparse(options, res, url):
    streams = {}

    if not res:
        return None

    if res.status_code >= 400:
        streams[0] = ServiceError("Can't read DASH playlist. {0}".format(res.status_code))
        return streams
    xml = ET.XML(res.text)

    temp = xml.findall('.//{urn:mpeg:dash:schema:mpd:2011}AdaptationSet[@mimeType="audio/mp4"]')
    audiofiles = adaptionset(temp, url)
    temp = xml.findall('.//{urn:mpeg:dash:schema:mpd:2011}AdaptationSet[@mimeType="video/mp4"]')
    videofiles = adaptionset(temp, url)

    for i in videofiles.keys():
        bitrate = (int(i) + int(list(audiofiles.keys())[0]))
        options.other = "mp4"
        options.segments = videofiles[i]["segments"]
        streams[int(bitrate)] = DASH(copy.copy(options), url, bitrate, cookies=res.cookies, audio=audiofiles[list(audiofiles.keys())[0]]["files"], files=videofiles[i]["files"])

    return streams


class DASH(VideoRetriever):
    def name(self):
        return "dash"

    def download(self):
        if self.options.live and not self.options.force:
            raise LiveDASHException(self.url)

        if self.options.segments:
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
