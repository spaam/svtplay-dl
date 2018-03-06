# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import copy
import xml.etree.ElementTree as ET
import os
import re
from datetime import datetime

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


def templateelemt(element, filename, idnumber, offset_sec, duration_sec):
    files = []
    timescale = 1
    duration = 1
    total = 1

    init = element.attrib["initialization"]
    media = element.attrib["media"]
    if "startNumber" in element.attrib:
        start = int(element.attrib["startNumber"])
    else:
        start = 1

    if "timescale" in element.attrib:
        timescale = float(element.attrib["timescale"])

    if "duration" in element.attrib:
        duration = float(element.attrib["duration"])

    if offset_sec is not None and duration_sec is None:
        start += int(offset_sec / ( duration / timescale ))

    if duration_sec is not None:
        total = int(duration_sec / ( duration / timescale ))

    selements = None
    rvalue = None
    timeline = element.find("{urn:mpeg:dash:schema:mpd:2011}SegmentTimeline")
    if timeline is not None:

        rvalue = timeline.findall(".//{urn:mpeg:dash:schema:mpd:2011}S[@r]")
        selements = timeline.findall(".//{urn:mpeg:dash:schema:mpd:2011}S")
        selements.pop()

        if rvalue:
            total = int(rvalue[0].attrib["r"]) + len(selements) + 1

    name = media.replace("$RepresentationID$", idnumber)
    files.append(urljoin(filename, init.replace("$RepresentationID$", idnumber)))

    if "$Time$" in media:
        time = [0]
        for n in selements:
            time.append(int(n.attrib["d"]))
        match = re.search("\$Time\$", name)
        if rvalue and match and len(selements) < 3:
            for n in range(start, start + total):
                new = name.replace("$Time$", str(n * int(rvalue[0].attrib["d"])))
                files.append(urljoin(filename, new))
        else:
            number = 0
            for n in time:
                number += n
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


def adaptionset(element, url, baseurl=None, offset_sec=None, duration_sec=None):
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
        bitrate = int(i.attrib["bandwidth"]) / 1000
        idnumber = i.attrib["id"]

        if i.find("{urn:mpeg:dash:schema:mpd:2011}BaseURL") is not None:
            filename = urljoin(filename, i.find("{urn:mpeg:dash:schema:mpd:2011}BaseURL").text)

        if i.find("{urn:mpeg:dash:schema:mpd:2011}SegmentBase") is not None:
            segments = True
            files.append(filename)
        if template is not None:
            segments = True
            files = templateelemt(template, filename, idnumber, offset_sec, duration_sec)
        elif i.find("{urn:mpeg:dash:schema:mpd:2011}SegmentTemplate") is not None:
            segments = True
            files = templateelemt(i.find("{urn:mpeg:dash:schema:mpd:2011}SegmentTemplate"), filename, idnumber, offset_sec, duration_sec)

        if files:
            streams[bitrate] = {"segments": segments, "files": files}

    return streams


def dashparse(options, res, url):
    streams = {}
    baseurl = None
    offset_sec = None
    duration_sec = None

    if not res:
        return None

    if res.status_code >= 400:
        streams[0] = ServiceError("Can't read DASH playlist. {0}".format(res.status_code))
        return streams
    if len(res.text) < 1:
        streams[0] = ServiceError("Can't read DASH playlist. {0}, size: {1}".format(res.status_code, len(res.text)))
        return
    xml = ET.XML(res.text)

    if xml.find("./{urn:mpeg:dash:schema:mpd:2011}BaseURL") is not None:
        baseurl = xml.find("./{urn:mpeg:dash:schema:mpd:2011}BaseURL").text

    if "availabilityStartTime" in xml.attrib:
        availabilityStartTime = xml.attrib["availabilityStartTime"]
        publishTime = xml.attrib["publishTime"]

        datetime_start = datetime.strptime(availabilityStartTime, "%Y-%m-%dT%H:%M:%S.%fZ")
        datetime_publish = datetime.strptime(publishTime, "%Y-%m-%dT%H:%M:%S.%fZ")
        diff_publish = datetime_publish - datetime_start
        offset_sec = diff_publish.total_seconds()

        if "mediaPresentationDuration" in xml.attrib:
            mediaPresentationDuration = xml.attrib["mediaPresentationDuration"]
            dt = datetime.strptime(mediaPresentationDuration, 'PT%HH%MM%S.%fS')
            duration_sec = (dt - datetime(1900, 1, 1)).total_seconds()

    temp = xml.findall('.//{urn:mpeg:dash:schema:mpd:2011}AdaptationSet[@mimeType="audio/mp4"]')
    audiofiles = adaptionset(temp, url, baseurl, offset_sec, duration_sec)
    temp = xml.findall('.//{urn:mpeg:dash:schema:mpd:2011}AdaptationSet[@mimeType="video/mp4"]')
    videofiles = adaptionset(temp, url, baseurl, offset_sec, duration_sec)

    if not audiofiles or not videofiles:
        streams[0] = ServiceError("Found no Audiofiles or Videofiles to download.")
        return

    options.other = "mp4"

    for i in videofiles.keys():
        bitrate = i + list(audiofiles.keys())[0]
        options.segments = videofiles[i]["segments"]
        streams[bitrate] = DASH(copy.copy(options), url, bitrate, cookies=res.cookies,
                                     audio=audiofiles[list(audiofiles.keys())[0]]["files"], files=videofiles[i]["files"])

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
                self._download_url(self.audio, audio=True)
            self._download_url(self.url)

    def _download2(self, files, audio=False):
        cookies = self.kwargs["cookies"]

        if audio:
            file_d = output(copy.copy(self.options), "m4a")
        else:
            file_d = output(self.options, self.options.other)
        if file_d is None:
            return
        eta = ETA(len(files))
        n = 1
        for i in files:
            if not self.options.silent:
                eta.increment()
                progressbar(len(files), n, ''.join(['ETA: ', str(eta)]))
                n += 1
            data = self.http.request("get", i, cookies=cookies)

            if data.status_code == 404:
                break
            data = data.content
            file_d.write(data)

        file_d.close()
        if not self.options.silent:
            progress_stream.write('\n')
        self.finished = True
