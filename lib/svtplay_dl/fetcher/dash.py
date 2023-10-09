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
from svtplay_dl.subtitle import subtitle_probe
from svtplay_dl.utils.output import ETA
from svtplay_dl.utils.output import formatname
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
    else:
        if attributes.get("type") == "static":
            end = math.ceil(attributes.get("mediaPresentationDuration") / (attributes.get("duration") / attributes.get("timescale")))
        else:
            # Saw this on dynamic live content
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
    streams = []

    dirname = os.path.dirname(url) + "/"
    if baseurl:
        dirname = urljoin(dirname, baseurl)
    for element in elements:
        role = "main"
        template = element.find("{urn:mpeg:dash:schema:mpd:2011}SegmentTemplate")
        represtation = element.findall(".//{urn:mpeg:dash:schema:mpd:2011}Representation")
        role_elemets = element.findall(".//{urn:mpeg:dash:schema:mpd:2011}Role")

        codecs = None
        if "codecs" in element.attrib:
            codecs = element.attrib["codecs"]
        lang = ""
        if "lang" in element.attrib:
            lang = element.attrib["lang"]
        if role_elemets:
            role = role_elemets[0].attrib["value"]

        resolution = ""
        if "maxWidth" in element.attrib and "maxHeight" in element.attrib:
            resolution = f'{element.attrib["maxWidth"]}x{element.attrib["maxHeight"]}'

        for i in represtation:
            files = []
            segments = False
            filename = dirname
            mimetype = None
            attributes.set("bandwidth", i.attrib["bandwidth"])
            bitrate = int(i.attrib["bandwidth"]) / 1000
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
                resolution = f'{i.attrib["maxWidth"]}x{i.attrib["maxHeight"]}'
            elif not resolution and "width" in i.attrib and "height" in i.attrib:
                resolution = f'{i.attrib["width"]}x{i.attrib["height"]}'
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
                streams.append(
                    {
                        "bitrate": bitrate,
                        "segments": segments,
                        "files": files,
                        "codecs": codec,
                        "channels": channels,
                        "lang": lang,
                        "mimetype": mimetype,
                        "resolution": resolution,
                        "role": role,
                    },
                )
            resolution = ""
    return streams


def dashparse(config, res, url, output, **kwargs):
    if not res:
        return

    if res.status_code >= 400:
        yield ServiceError(f"Can't read DASH playlist. {res.status_code}")
    if len(res.text) < 1:
        yield ServiceError(f"Can't read DASH playlist. {res.status_code}, size: {len(res.text)}")

    yield from _dashparse(config, res.text, url, output, cookies=res.cookies, **kwargs)


def _dashparse(config, text, url, output, cookies, **kwargs):
    baseurl = None
    loutput = copy.copy(output)
    loutput["ext"] = "mp4"
    attributes = DASHattibutes()

    text = re.sub("&(?!amp;)", "&amp;", text)
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
    if len(temp) == 0:
        temp = xml.findall('.//{urn:mpeg:dash:schema:mpd:2011}AdaptationSet[@mimeType="application/mp4"]')
    subtitles = adaptionset(attributes, temp, url, baseurl)

    if not audiofiles or not videofiles:
        yield ServiceError("Found no Audiofiles or Videofiles to download.")
        return
    if "channels" in kwargs:
        kwargs.pop("channels")
    if "codec" in kwargs:
        kwargs.pop("codec")

    for video in videofiles:
        for audio in audiofiles:
            bitrate = video["bitrate"] + audio["bitrate"]
            yield DASH(
                copy.copy(config),
                url,
                bitrate,
                cookies=cookies,
                audio=audio["files"],
                files=video["files"],
                output=loutput,
                segments=video["segments"],
                codec=video["codecs"],
                channels=audio["channels"],
                resolution=video["resolution"],
                language=audio["lang"],
                role=audio["role"],
                **kwargs,
            )
    for sub in subtitles:
        if len(subtitles) > 1:
            if sub["role"] and sub["role"] != "main" and sub["role"] != "subtitle":
                sub["lang"] = f'{sub["lang"]}-{sub["role"]}'
        yield from subtitle_probe(copy.copy(config), url, subfix=sub["lang"], output=copy.copy(loutput), files=sub["files"], **kwargs)


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
    match = re.search(r"(.*:.*)\.(\d{5,9})Z", date_str)
    if match:
        date_str = f"{match.group(1)}.{int(int(match.group(2))/1000)}Z"  # Need to translate nanoseconds to milliseconds
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
            self.output["ext"] = "m4a"
        else:
            self.output["ext"] = "mp4"

        filename = formatname(self.output, self.config)
        file_d = open(filename, "wb")

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

    def _download_url(self, url, audio=False, total_size=None):
        cookies = self.kwargs["cookies"]
        data = self.http.request("get", url, cookies=cookies, headers={"Range": "bytes=0-8192"})
        if not total_size:
            try:
                total_size = data.headers["Content-Range"]
                total_size = total_size[total_size.find("/") + 1 :]
                total_size = int(total_size)
            except KeyError:
                raise KeyError("Can't get the total size.")

        bytes_so_far = 8192
        if audio:
            self.output["ext"] = "m4a"
        else:
            self.output["ext"] = "mp4"
        filename = formatname(self.output, self.config)
        file_d = open(filename, "wb")

        file_d.write(data.content)
        eta = ETA(total_size)
        while bytes_so_far < total_size:

            if not self.config.get("silent"):
                eta.update(bytes_so_far)
                progressbar(total_size, bytes_so_far, "".join(["ETA: ", str(eta)]))

            old = bytes_so_far + 1
            bytes_so_far = total_size

            bytes_range = f"bytes={old}-{bytes_so_far}"

            data = self.http.request("get", url, cookies=cookies, headers={"Range": bytes_range})
            file_d.write(data.content)

        file_d.close()
        progressbar(bytes_so_far, total_size, "ETA: complete")
        # progress_stream.write('\n')
        self.finished = True
