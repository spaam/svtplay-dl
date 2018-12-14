# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import copy
import xml.etree.ElementTree as ET
import os
import re
from datetime import datetime
from urllib.parse import urljoin

from svtplay_dl.utils.output import output, progress_stream, ETA, progressbar
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
        start += int(offset_sec / (duration / timescale))

    if duration_sec is not None:
        total = int(duration_sec / (duration / timescale))

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
        match = re.search(r"\$Time\$", name)
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
        if re.search(r"\$Number(\%\d+)d\$", name):
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


def dashparse(config, res, url, output=None):
    streams = {}
    if not res:
        return streams

    if res.status_code >= 400:
        streams[0] = ServiceError("Can't read DASH playlist. {0}".format(res.status_code))
        return streams
    if len(res.text) < 1:
        streams[0] = ServiceError("Can't read DASH playlist. {0}, size: {1}".format(res.status_code, len(res.text)))
        return streams

    return _dashparse(config, res.text, url, output, res.cookies)


def _dashparse(config, text, url, output, cookies):
    streams = {}
    baseurl = None
    offset_sec = None
    duration_sec = None

    xml = ET.XML(text)

    if xml.find("./{urn:mpeg:dash:schema:mpd:2011}BaseURL") is not None:
        baseurl = xml.find("./{urn:mpeg:dash:schema:mpd:2011}BaseURL").text

    if "availabilityStartTime" in xml.attrib:
        availabilityStartTime = xml.attrib["availabilityStartTime"]
        publishTime = xml.attrib["publishTime"]

        datetime_start = parse_dates(availabilityStartTime)
        datetime_publish = parse_dates(publishTime)
        diff_publish = datetime_publish - datetime_start
        offset_sec = diff_publish.total_seconds()

        if "mediaPresentationDuration" in xml.attrib:
            mediaPresentationDuration = xml.attrib["mediaPresentationDuration"]
            duration_sec = (parse_dates(mediaPresentationDuration) - datetime(1900, 1, 1)).total_seconds()

    temp = xml.findall('.//{urn:mpeg:dash:schema:mpd:2011}AdaptationSet[@mimeType="audio/mp4"]')
    audiofiles = adaptionset(temp, url, baseurl, offset_sec, duration_sec)
    temp = xml.findall('.//{urn:mpeg:dash:schema:mpd:2011}AdaptationSet[@mimeType="video/mp4"]')
    videofiles = adaptionset(temp, url, baseurl, offset_sec, duration_sec)

    if not audiofiles or not videofiles:
        streams[0] = ServiceError("Found no Audiofiles or Videofiles to download.")
        return streams

    for i in videofiles.keys():
        bitrate = i + list(audiofiles.keys())[0]
        streams[bitrate] = DASH(copy.copy(config), url, bitrate, cookies=cookies,
                                audio=audiofiles[list(audiofiles.keys())[0]]["files"], files=videofiles[i]["files"],
                                output=output, segments=videofiles[i]["segments"])

    return streams


def parse_dates(date_str):
    date_patterns = ["%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%S", "PT%HH%MM%S.%fS",
                     "PT%HH%MM%SS", "PT%MM%S.%fS", "PT%MM%SS", "PT%HH%SS", "PT%HH%S.%fS"]
    dt = None
    for pattern in date_patterns:
        try:
            dt = datetime.strptime(date_str, pattern)
            break
        except Exception:
            pass
    if not dt:
        raise ValueError("Can't parse date format: {0}".format(date_str))

    return dt


class DASH(VideoRetriever):
    @property
    def name(self):
        return "dash"

    def download(self):
        self.output_extention = "mp4"
        if self.config.get("live") and not self.config.get("force"):
            raise LiveDASHException(self.url)

        if self.segments:
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
            file_d = output(copy.copy(self.output), self.config, extension="m4a")
        else:
            file_d = output(self.output, self.config, extension="mp4")
        if file_d is None:
            return
        eta = ETA(len(files))
        n = 1
        for i in files:
            if not self.config.get("silent"):
                eta.increment()
                progressbar(len(files), n, ''.join(['ETA: ', str(eta)]))
                n += 1
            data = self.http.request("get", i, cookies=cookies)

            if data.status_code == 404:
                break
            data = data.content
            file_d.write(data)

        file_d.close()
        if not self.config.get("silent"):
            progress_stream.write('\n')
        self.finished = True
