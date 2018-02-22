import xml.etree.ElementTree as ET
import json
import re
from svtplay_dl.log import log
from svtplay_dl.utils import is_py2, is_py3, decode_html_entities, HTTP
from svtplay_dl.utils.io import StringIO
from svtplay_dl.output import output
from requests import __build__ as requests_version
import platform


class subtitle(object):
    def __init__(self, options, subtype, url, subfix=None):
        self.url = url
        self.subtitle = None
        self.options = options
        self.subtype = subtype
        self.http = HTTP(options)
        self.subfix = subfix
        self.bom = False

    def download(self):
        subdata = self.http.request("get", self.url, cookies=self.options.cookies)
        if subdata.status_code != 200:
            log.warning("Can't download subtitle file")
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
        if self.subtype == "raw":
            data = self.raw(subdata)

        if self.subfix:
            self.options.output = self.options.output + self.subfix

        if self.options.get_raw_subtitles:
            subdata = self.raw(subdata)
            self.save_file(subdata, self.subtype)

        self.save_file(data, "srt")

    def save_file(self, data, subtype):
        if platform.system() == "Windows" and is_py3:
            file_d = output(self.options, subtype, mode="wt", encoding="utf-8")
        else:
            file_d = output(self.options, subtype, mode="wt")
        if hasattr(file_d, "read") is False:
            return
        file_d.write(data)
        file_d.close()

    def raw(self, subdata):
        if is_py2:
            data = subdata.text.encode("utf-8")
        else:
            data = subdata.text
        return data

    def tt(self, subdata):
        i = 1
        data = ""
        if is_py2:
            subs = subdata.text.encode("utf8")
        else:
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
        if is_py2:
            data = data.encode("utf8")
        return data

    def json(self, subdata):
        data = json.loads(subdata.text)
        number = 1
        subs = ""
        for i in data:
            subs += "%s\n%s --> %s\n" % (number, timestr(int(i["startMillis"])), timestr(int(i["endMillis"])))
            if is_py2:
                subs += "%s\n\n" % i["text"].encode("utf-8")
            else:
                subs += "%s\n\n" % i["text"]
            number += 1

        return subs

    def sami(self, subdata):
        text = subdata.text
        if is_py2:
            text = text.encode("utf8")
        text = re.sub(r'&', '&amp;', text)
        tree = ET.fromstring(text)
        subt = tree.find("Font")
        subs = ""
        n = 0
        for i in subt.getiterator():
            if i.tag == "Subtitle":
                n = i.attrib["SpotNumber"]

                if i.attrib["SpotNumber"] == "1":
                    subs += "%s\n%s --> %s\n" % (i.attrib["SpotNumber"], timecolon(i.attrib["TimeIn"]), timecolon(i.attrib["TimeOut"]))
                else:
                    subs += "\n%s\n%s --> %s\n" % (i.attrib["SpotNumber"], timecolon(i.attrib["TimeIn"]), timecolon(i.attrib["TimeOut"]))
            else:
                if int(n) > 0 and i.text:
                    subs += "%s\n" % decode_html_entities(i.text)

        if is_py2:
            subs = subs.encode('utf8')
        subs = re.sub('&amp;', r'&', subs)
        return subs

    def smi(self, subdata):
        if requests_version < 0x20300:
            if is_py2:
                subdata = subdata.content
            else:
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
        if is_py2 and isinstance(text, unicode):
            return text.encode("utf-8")
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
                if self.options.convert_subtitle_colors:
                    colors = {'30': '#000000', '31': '#ff0000', '32': '#00ff00', '33': '#ffff00',
                              '34': '#0000ff', '35': '#ff00ff', '36': '#00ffff', '37': '#ffffff'}
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
        if is_py2:
            return srt.encode("utf-8")
        return srt


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
