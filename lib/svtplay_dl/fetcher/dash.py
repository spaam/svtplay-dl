# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
import copy
import math
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.parse import urljoin

from svtplay_dl.error import ServiceError
from svtplay_dl.error import UIException
from svtplay_dl.fetcher import VideoRetriever
from svtplay_dl.subtitle import subtitle
from svtplay_dl.utils.output import ETA
from svtplay_dl.utils.output import output
from svtplay_dl.utils.output import progress_stream
from svtplay_dl.utils.output import progressbar


class DASHException(UIException):
    def __init__(self, url, message):
        self.url = url
        super().__init__(message)


class LiveDASHException(DASHException):
    def __init__(self, url):
        super().__init__(url, "This is a live DASH stream, and they are not supported.")


class DASHattibutes:
    def __init__(self):
        self.default = {}

    def set(self, key, value):
        self.default[key] = value

    def get(self, key):
        if key in self.default:
            return self.default[key]
        return 0


def templateelemt(attributes, element, filename, idnumber):
    files = []

    init = element.attrib["initialization"]
    media = element.attrib["media"]
    if "startNumber" in element.attrib:
        start = int(element.attrib["startNumber"])
    else:
        start = 1

    if "timescale" in element.attrib:
        attributes.set("timescale", float(element.attrib["timescale"]))
    else:
        attributes.set("timescale", 1)

    if "duration" in element.attrib:
        attributes.set("duration", float(element.attrib["duration"]))

    segments = []
    timeline = element.findall("{urn:mpeg:dash:schema:mpd:2011}SegmentTimeline/{urn:mpeg:dash:schema:mpd:2011}S")
    if timeline:
        t = -1
        for s in timeline:
            duration = int(s.attrib["d"])
            repeat = int(s.attrib["r"]) if "r" in s.attrib else 0
            segmenttime = int(s.attrib["t"]) if "t" in s.attrib else 0

            if t < 0:
                t = segmenttime
            count = repeat + 1

            end = start + len(segments) + count
            number = start + len(segments)
            while number < end:
                segments.append({"number": number, "duration": math.ceil(duration / attributes.get("timescale")), "time": t})
                t += duration
                number += 1
    else:  # Saw this on dynamic live content
        start = 0
        now = time.time()
        periodStartWC = time.mktime(attributes.get("availabilityStartTime").timetuple()) + start
        periodEndWC = now + attributes.get("minimumUpdatePeriod")
        periodDuration = periodEndWC - periodStartWC
        segmentCount = math.ceil(periodDuration * attributes.get("timescale") / attributes.get("duration"))
        availableStart = math.floor(
            (now - periodStartWC - attributes.get("timeShiftBufferDepth")) * attributes.get("timescale") / attributes.get("duration"),
        )
        availableEnd = math.floor((now - periodStartWC) * attributes.get("timescale") / attributes.get("duration"))
        start = max(0, availableStart)
        end = min(segmentCount, availableEnd)
        for number in range(start, end):
            segments.append({"number": number, "duration": int(attributes.get("duration") / attributes.get("timescale"))})

    name = media.replace("$RepresentationID$", idnumber).replace("$Bandwidth$", attributes.get("bandwidth"))
    files.append(urljoin(filename, init.replace("$RepresentationID$", idnumber).replace("$Bandwidth$", attributes.get("bandwidth"))))
    for segment in segments:
        if "$Time$" in media:
            new = name.replace("$Time$", str(segment["time"]))
        if "$Number" in name:
            if re.search(r"\$Number(\%\d+)d\$", name):
                vname = name.replace("$Number", "").replace("$", "")
                new = vname % segment["number"]
            else:
                new = name.replace("$Number$", str(segment["number"]))

        files.append(urljoin(filename, new))

    return files


def adaptionset(attributes, elements, url, baseurl=None):
    streams = {}

    dirname = os.path.dirname(url) + "/"
    if baseurl:
        dirname = urljoin(dirname, baseurl)
    for element in elements:
        template = element.find("{urn:mpeg:dash:schema:mpd:2011}SegmentTemplate")
        represtation = element.findall(".//{urn:mpeg:dash:schema:mpd:2011}Representation")

        codecs = None
        if "codecs" in element.attrib:
            codecs = element.attrib["codecs"]
        lang = None
        if "lang" in element.attrib:
            lang = element.attrib["lang"]

        resolution = None
        if "maxWidth" in element.attrib and "maxHeight" in element.attrib:
            resolution = f'{element.attrib["maxWidth"]}x{element.attrib["maxHeight"]}'

        for i in represtation:
            files = []
            segments = False
            filename = dirname
            mimetype = None
            attributes.set("bandwidth", i.attrib["bandwidth"])
            bitrate = int(i.attrib["bandwidth"]) / 1000
            if "contentType" in element.attrib and element.attrib["contentType"] == "text":
                if streams.keys():
                    bitrate = list(streams.keys())[-1]
                bitrate += 1
            if "mimeType" in element.attrib:
                mimetype = element.attrib["mimeType"]
            idnumber = i.attrib["id"]
            channels = None
            codec = None
            if codecs is None and "codecs" in i.attrib:
                codecs = i.attrib["codecs"]
            if codecs and codecs[:3] == "avc":
                codec = "h264"
            elif codecs and codecs[:3] == "hvc":
                codec = "hevc"
            else:
                codec = codecs
            if not resolution and "maxWidth" in i.attrib and "maxHeight" in i.attrib:
                resolution = f'{element.attrib["maxWidth"]}x{element.attrib["maxHeight"]}'
            if i.find("{urn:mpeg:dash:schema:mpd:2011}AudioChannelConfiguration") is not None:
                chan = i.find("{urn:mpeg:dash:schema:mpd:2011}AudioChannelConfiguration").attrib["value"]
                if chan == "6":
                    channels = "51"
                else:
                    channels = None
            if i.find("{urn:mpeg:dash:schema:mpd:2011}BaseURL") is not None:
                filename = urljoin(filename, i.find("{urn:mpeg:dash:schema:mpd:2011}BaseURL").text)

            if i.find("{urn:mpeg:dash:schema:mpd:2011}SegmentBase") is not None:
                segments = True
                files.append(filename)
            if template is not None:
                segments = True
                files = templateelemt(attributes, template, filename, idnumber)
            elif i.find("{urn:mpeg:dash:schema:mpd:2011}SegmentTemplate") is not None:
                segments = True
                files = templateelemt(attributes, i.find("{urn:mpeg:dash:schema:mpd:2011}SegmentTemplate"), filename, idnumber)
            if mimetype == "text/vtt":
                files.append(filename)

            if files:
                streams[bitrate] = {
                    "segments": segments,
                    "files": files,
                    "codecs": codec,
                    "channels": channels,
                    "lang": lang,
                    "mimetype": mimetype,
                    "resolution": resolution,
                }

    return streams


def dashparse(config, res, url, **kwargs):
    streams = {}
    if not res:
        return streams

    if res.status_code >= 400:
        streams[0] = ServiceError(f"Can't read DASH playlist. {res.status_code}")
        return streams
    if len(res.text) < 1:
        streams[0] = ServiceError("Can't read DASH playlist. {}, size: {}".format(res.status_code, len(res.text)))
        return streams

    return _dashparse(config, res.text, url, res.cookies, **kwargs)


def _dashparse(config, text, url, cookies, **kwargs):
    streams = {}
    baseurl = None
    output = kwargs.pop("output", None)
    attributes = DASHattibutes()

    xml = ET.XML(text)

    if xml.find("./{urn:mpeg:dash:schema:mpd:2011}BaseURL") is not None:
        baseurl = xml.find("./{urn:mpeg:dash:schema:mpd:2011}BaseURL").text

    if "availabilityStartTime" in xml.attrib:
        attributes.set("availabilityStartTime", parse_dates(xml.attrib["availabilityStartTime"]))
        attributes.set("publishTime", parse_dates(xml.attrib["publishTime"]))

    if "mediaPresentationDuration" in xml.attrib:
        attributes.set("mediaPresentationDuration", parse_duration(xml.attrib["mediaPresentationDuration"]))
    if "timeShiftBufferDepth" in xml.attrib:
        attributes.set("timeShiftBufferDepth", parse_duration(xml.attrib["timeShiftBufferDepth"]))
    if "minimumUpdatePeriod" in xml.attrib:
        attributes.set("minimumUpdatePeriod", parse_duration(xml.attrib["minimumUpdatePeriod"]))

    attributes.set("type", xml.attrib["type"])
    temp = xml.findall('.//{urn:mpeg:dash:schema:mpd:2011}AdaptationSet[@mimeType="audio/mp4"]')
    if len(temp) == 0:
        temp = xml.findall('.//{urn:mpeg:dash:schema:mpd:2011}AdaptationSet[@contentType="audio"]')
    audiofiles = adaptionset(attributes, temp, url, baseurl)
    temp = xml.findall('.//{urn:mpeg:dash:schema:mpd:2011}AdaptationSet[@mimeType="video/mp4"]')
    if len(temp) == 0:
        temp = xml.findall('.//{urn:mpeg:dash:schema:mpd:2011}AdaptationSet[@contentType="video"]')
    videofiles = adaptionset(attributes, temp, url, baseurl)
    temp = xml.findall('.//{urn:mpeg:dash:schema:mpd:2011}AdaptationSet[@contentType="text"]')
    subtitles = adaptionset(attributes, temp, url, baseurl)

    if not audiofiles or not videofiles:
        streams[0] = ServiceError("Found no Audiofiles or Videofiles to download.")
        return streams
    if "channels" in kwargs:
        kwargs.pop("channels")
    if "codec" in kwargs:
        kwargs.pop("codec")
    for i in videofiles.keys():
        bitrate = i + list(audiofiles.keys())[0]
        streams[bitrate] = DASH(
            copy.copy(config),
            url,
            bitrate,
            cookies=cookies,
            audio=audiofiles[list(audiofiles.keys())[0]]["files"],
            files=videofiles[i]["files"],
            output=output,
            segments=videofiles[i]["segments"],
            codec=videofiles[i]["codecs"],
            channels=audiofiles[list(audiofiles.keys())[0]]["channels"],
            resolution=videofiles[i]["resolution"],
            **kwargs,
        )
    for i in subtitles.keys():
        if subtitles[i]["codecs"] == "stpp":
            streams[i] = subtitle(
                copy.copy(config), "stpp", url, subtitles[i]["lang"], output=copy.copy(output), files=subtitles[i]["files"], **kwargs
            )
        if subtitles[i]["mimetype"] == "text/vtt":
            streams[i] = subtitle(
                copy.copy(config), "webvtt", url, subtitles[i]["lang"], output=copy.copy(output), files=subtitles[i]["files"], **kwargs
            )
    return streams


def parse_duration(duration):
    match = re.search(r"P(?:(\d*)Y)?(?:(\d*)M)?(?:(\d*)D)?(?:T(?:(\d*)H)?(?:(\d*)M)?(?:([\d.]*)S)?)?", duration)
    if not match:
        return 0
    year = int(match.group(1)) * 365 * 24 * 60 * 60 if match.group(1) else 0
    month = int(match.group(2)) * 30 * 24 * 60 * 60 if match.group(2) else 0
    day = int(match.group(3)) * 24 * 60 * 60 if match.group(3) else 0
    hour = int(match.group(4)) * 60 * 60 if match.group(4) else 0
    minute = int(match.group(5)) * 60 if match.group(5) else 0
    second = float(match.group(6)) if match.group(6) else 0
    return year + month + day + hour + minute + second


def parse_dates(date_str):
    date_patterns = ["%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"]
    dt = None
    for pattern in date_patterns:
        try:
            dt = datetime.strptime(date_str, pattern)
            break
        except Exception:
            pass
    if not dt:
        raise ValueError(f"Can't parse date format: {date_str}")

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
            if self.audio and not self.config.get("only_video"):
                self._download2(self.audio, audio=True)
            if not self.config.get("only_audio"):
                self._download2(self.files)
        else:
            if self.audio and not self.config.get("only_video"):
                self._download_url(self.audio, audio=True)
            if not self.config.get("only_audio"):
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
                progressbar(len(files), n, "".join(["ETA: ", str(eta)]))
                n += 1
            data = self.http.request("get", i, cookies=cookies)

            if data.status_code == 404:
                break
            data = data.content
            file_d.write(data)

        file_d.close()
        if not self.config.get("silent"):
            progress_stream.write("\n")
        self.finished = True
