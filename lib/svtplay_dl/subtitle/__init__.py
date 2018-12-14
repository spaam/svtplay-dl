import xml.etree.ElementTree as ET
import json
import re
import logging
from io import StringIO

from svtplay_dl.utils.text import decode_html_entities
from svtplay_dl.utils.http import HTTP, get_full_url
from svtplay_dl.utils.output import output


from requests import __build__ as requests_version
import platform


class subtitle(object):
    def __init__(self, config, subtype, url, subfix=None, **kwargs):
        self.url = url
        self.subtitle = None
        self.config = config
        self.subtype = subtype
        self.http = HTTP(config)
        self.subfix = subfix
        self.bom = False
        self.output = kwargs.pop("output", None)
        self.kwargs = kwargs

    def __repr__(self):
        return "<Subtitle(type={}, url={}>".format(self.subtype, self.url)

    def download(self):
        subdata = self.http.request("get", self.url)
        if subdata.status_code != 200:
            logging.warning("Can't download subtitle file")
            return

        data = None
        if "mtgx" in self.url and subdata.content[:3] == b"\xef\xbb\xbf":
            subdata.encoding = "utf-8"
            self.bom = True

        if self.subtype == "tt":
            data = self.tt(subdata)
        if self.subtype == "json":
            data = self.json(subdata)
        if self.subtype == "sami":
            data = self.sami(subdata)
        if self.subtype == "smi":
            data = self.smi(subdata)
        if self.subtype == "wrst":
            if "tv4play" in self.url and subdata.content[:3] == b"\xef\xbb\xbf":
                subdata.encoding = "utf-8"
                self.bom = True
            if "dplay" in self.url:
                subdata.encoding = "utf-8"
            data = self.wrst(subdata)
        if self.subtype == "wrstsegment":
            data = self.wrstsegment(subdata)
        if self.subtype == "raw":
            data = self.raw(subdata)

        if self.subfix:
            if self.config.get("get_all_subtitles"):
                if self.output["episodename"]:
                    self.output["episodename"] = "{}-{}".format(self.output["episodename"], self.subfix)
                else:
                    self.output["episodename"] = self.subfix

        if self.config.get("get_raw_subtitles"):
            subdata = self.raw(subdata)
            self.save_file(subdata, self.subtype)

        self.save_file(data, "srt")

    def save_file(self, data, subtype):
        if platform.system() == "Windows":
            file_d = output(self.output, self.config, subtype, mode="wt", encoding="utf-8")
        else:
            file_d = output(self.output, self.config, subtype, mode="wt")
        if hasattr(file_d, "read") is False:
            return
        file_d.write(data)
        file_d.close()

    def raw(self, subdata):
        return subdata.text

    def tt(self, subdata):
        i = 1
        data = ""
        subs = subdata.text

        subdata = re.sub(' xmlns="[^"]+"', '', subs, count=1)
        tree = ET.XML(subdata)
        xml = tree.find("body").find("div")
        plist = list(xml.findall("p"))
        for node in plist:
            tag = norm(node.tag)
            if tag == "p" or tag == "span":
                begin = node.attrib["begin"]
                if not ("dur" in node.attrib):
                    duration = node.attrib["duration"]
                else:
                    duration = node.attrib["dur"]
                if not ("end" in node.attrib):
                    begin2 = begin.split(":")
                    duration2 = duration.split(":")
                    try:
                        sec = float(begin2[2]) + float(duration2[2])
                    except ValueError:
                        sec = 0.000
                    end = "%02d:%02d:%06.3f" % (int(begin2[0]), int(begin2[1]), sec)
                else:
                    end = node.attrib["end"]
                data += '%s\n%s --> %s\n' % (i, begin.replace(".", ","), end.replace(".", ","))
                data = tt_text(node, data)
                data += "\n"
                i += 1

        return data

    def json(self, subdata):
        data = json.loads(subdata.text)
        number = 1
        subs = ""
        for i in data:
            subs += "%s\n%s --> %s\n" % (number, timestr(int(i["startMillis"])), timestr(int(i["endMillis"])))
            subs += "%s\n\n" % i["text"]
            number += 1

        return subs

    def sami(self, subdata):
        text = subdata.text
        text = re.sub(r'&', '&amp;', text)
        tree = ET.fromstring(text)
        allsubs = tree.findall(".//Subtitle")
        subs = ""
        increase = 0
        for sub in allsubs:
            try:
                number = int(sub.attrib["SpotNumber"])
            except ValueError:
                number = int(re.search(r"(\d+)", sub.attrib["SpotNumber"]).group(1))
                increase += 1
            n = number + increase

            texts = sub.findall(".//Text")
            all = ""
            for text in texts:
                line = ""
                for txt in text.itertext():
                    line += "{}".format(txt)
                all += "{}\n".format(decode_html_entities(line.lstrip()))
            subs += "{}\n{} --> {}\n{}\n".format(n, timecolon(sub.attrib["TimeIn"]), timecolon(sub.attrib["TimeOut"]), all)
        subs = re.sub('&amp;', r'&', subs)
        return subs

    def smi(self, subdata):
        if requests_version < 0x20300:
            subdata = subdata.content.decode("latin")
        else:
            subdata.encoding = "ISO-8859-1"
            subdata = subdata.text
        ssubdata = StringIO(subdata)
        timea = 0
        number = 1
        data = None
        subs = ""
        TAG_RE = re.compile(r'<(?!\/?i).*?>')
        bad_char = re.compile(r'\x96')
        for i in ssubdata.readlines():
            i = i.rstrip()
            sync = re.search(r"<SYNC Start=(\d+)>", i)
            if sync:
                if int(sync.group(1)) != int(timea):
                    if data and data != "&nbsp;":
                        subs += "%s\n%s --> %s\n" % (number, timestr(timea), timestr(sync.group(1)))
                        text = "%s\n" % TAG_RE.sub('', data.replace("<br>", "\n"))
                        text = decode_html_entities(text)
                        if text[len(text) - 2] != "\n":
                            text += "\n"
                        subs += text
                        number += 1
                timea = sync.group(1)
            text = re.search("<P Class=SVCC>(.*)", i)
            if text:
                data = text.group(1)
        recomp = re.compile(r'\r')
        text = bad_char.sub('-', recomp.sub('', subs))
        return text

    def wrst(self, subdata):
        ssubdata = StringIO(subdata.text)
        srt = ""
        subtract = False
        number_b = 1
        number = 0
        block = 0
        subnr = False
        if self.bom:
            ssubdata.read(1)
        for i in ssubdata.readlines():
            match = re.search(r"^[\r\n]+", i)
            match2 = re.search(r"([\d:\.]+ --> [\d:\.]+)", i)
            match3 = re.search(r"^(\d+)\s", i)
            if i[:6] == "WEBVTT":
                continue
            elif "X-TIMESTAMP" in i:
                continue
            elif match and number_b == 1 and self.bom:
                continue
            elif match and number_b > 1:
                block = 0
                srt += "\n"
            elif match2:
                if not subnr:
                    srt += "%s\n" % number_b
                matchx = re.search(r'(?P<h1>\d+):(?P<m1>\d+):(?P<s1>[\d\.]+) --> (?P<h2>\d+):(?P<m2>\d+):(?P<s2>[\d\.]+)', i)
                if matchx:
                    hour1 = int(matchx.group("h1"))
                    hour2 = int(matchx.group("h2"))
                    if int(number) == 1:
                        if hour1 > 9:
                            subtract = True
                    if subtract:
                        hour1 -= 10
                        hour2 -= 10
                else:
                    matchx = re.search(r'(?P<m1>\d+):(?P<s1>[\d\.]+) --> (?P<m2>\d+):(?P<s2>[\d\.]+)', i)
                    hour1 = 0
                    hour2 = 0
                time = "{0:02d}:{1}:{2} --> {3:02d}:{4}:{5}\n".format(hour1, matchx.group("m1"), matchx.group("s1").replace(".", ","),
                                                                      hour2, matchx.group("m2"), matchx.group("s2").replace(".", ","))
                srt += time
                block = 1
                subnr = False
                number_b += 1

            elif match3 and block == 0:
                number = match3.group(1)
                srt += "%s\n" % number
                subnr = True
            else:
                if self.config.get("convert_subtitle_colors"):
                    colors = {
                        '30': '#000000', '31': '#ff0000', '32': '#00ff00', '33': '#ffff00', '34': '#0000ff',
                        '35': '#ff00ff', '36': '#00ffff', '37': '#ffffff', 'c.black': '#000000', 'c.red': '#ff0000',
                        'c.green': '#00ff00', 'c.yellow': '#ffff00', 'c.blue': '#0000ff', 'c.magneta': '#ff00ff',
                        'c.cyan': '#00ffff', 'c.gray': '#ffffff',
                    }
                    sub = i
                    for tag, color in colors.items():
                        regex1 = '<' + tag + '>'
                        replace = '<font color="' + color + '">'
                        sub = re.sub(regex1, replace, sub)

                    sub = re.sub('</.+>', '</font>', sub)
                else:
                    sub = re.sub('<[^>]*>', '', i)
                srt += sub.strip()
                srt += "\n"
        srt = decode_html_entities(srt)
        return srt

    def wrstsegment(self, subdata):
        time = 0
        subs = []
        for i in self.kwargs["m3u8"].media_segment:
            itemurl = get_full_url(i["URI"], self.url)
            cont = self.http.get(itemurl)
            if "cmore" in self.url:
                cont.encoding = "utf-8"
            text = cont.text.split("\n")
            for t in text:  # is in text[1] for tv4play, but this should be more future proof
                if 'X-TIMESTAMP-MAP=MPEGTS' in t:
                    time = float(re.search(r"X-TIMESTAMP-MAP=MPEGTS:(\d+)", t).group(1)) / 90000 - 10
            text = text[3:len(text) - 2]
            if len(text) > 1:
                itmes = []
                for n in text:
                    if n:
                        itmes.append(n)
                    else:
                        if len(subs) > 1 and len(itmes) < 2:  # Ignore empty lines in unexpected places
                            pass
                        elif len(subs) > 1 and itmes[1] == subs[-1][1]:  # This will happen when there are two sections in file
                            ha = strdate(subs[-1][0])
                            ha3 = strdate(itmes[0])
                            second = str2sec(ha3.group(2)) + time
                            subs[-1][0] = "{} --> {}".format(ha.group(1), sec2str(second))
                            itmes = []
                        else:
                            ha = strdate(itmes[0])
                            first = str2sec(ha.group(1)) + time
                            second = str2sec(ha.group(2)) + time
                            itmes[0] = "{} --> {}".format(sec2str(first), sec2str(second))
                            subs.append(itmes)
                            itmes = []
                if itmes:
                    if len(subs) > 0 and itmes[1] == subs[-1][1]:
                        ha = strdate(subs[-1][0])
                        ha3 = strdate(itmes[0])
                        second = str2sec(ha3.group(2)) + time
                        subs[-1][0] = "{} --> {}".format(ha.group(1), sec2str(second))
                    else:
                        ha = strdate(itmes[0])
                        first = str2sec(ha.group(1)) + time
                        second = str2sec(ha.group(2)) + time
                        itmes[0] = "{} --> {}".format(sec2str(first), sec2str(second))
                        subs.append(itmes)

        string = ""
        nr = 1
        for sub in subs:
            string += "{}\n{}\n\n".format(nr, '\n'.join(sub))
            nr += 1

        return string


def timestr(msec):
    """
    Convert a millisecond value to a string of the following
    format:

        HH:MM:SS,SS

    with 10 millisecond precision. Note the , seperator in
    the seconds.
    """
    sec = float(msec) / 1000

    hours = int(sec / 3600)
    sec -= hours * 3600

    minutes = int(sec / 60)
    sec -= minutes * 60

    output = "%02d:%02d:%06.3f" % (hours, minutes, sec)
    return output.replace(".", ",")


def timecolon(data):
    match = re.search(r"(\d+:\d+:\d+):(\d+)", data)
    return "%s,%s" % (match.group(1), match.group(2))


def norm(name):
    if name[0] == "{":
        _, tag = name[1:].split("}")
        return tag
    else:
        return name


def tt_text(node, data):
    if node.text:
        data += "%s\n" % node.text.strip(' \t\n\r')
    for i in node:
        if i.text:
            data += "%s\n" % i.text.strip(' \t\n\r')
        if i.tail:
            text = i.tail.strip(' \t\n\r')
            if text:
                data += "%s\n" % text
    return data


def strdate(datestring):
    match = re.search(r"^(\d+:\d+:[\.0-9]+) --> (\d+:\d+:[\.0-9]+)", datestring)
    return match


def sec2str(seconds):
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return "{:02d}:{:02d}:{:06.3f}".format(int(h), int(m), s)


def str2sec(string):
    return sum(x * float(t) for x, t in zip([3600, 60, 1], string.split(":")))
