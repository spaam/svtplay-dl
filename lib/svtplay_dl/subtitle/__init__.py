import xml.etree.ElementTree as ET
import json
import re
from svtplay_dl.log import log
from svtplay_dl.utils import is_py2, get_http_data

class subtitle():
    def __init__(self, url):
        self.url = url
        self.subtitle = None

class subtitle_tt(subtitle):
    def download(self, options):
        self.subtitle = get_http_data(self.url)
        i = 1
        data = ""
        skip = False
        tree = ET.ElementTree(ET.fromstring(subtitle))
        for node in tree.iter():
            tag = norm(node.tag)
            if tag == "p":
                if skip:
                    data = data + "\n"
                begin = node.attrib["begin"]
                if not ("dur" in node.attrib):
                    duration = node.attrib["duration"]
                else:
                    duration = node.attrib["dur"]
                if not ("end" in node.attrib):
                    begin2 = begin.split(":")
                    duration2 = duration.split(":")
                    sec = float(begin2[2]) + float(duration2[2])
                    end = "%02d:%02d:%06.3f" % (int(begin[0]), int(begin[1]), sec)
                else:
                    end = node.attrib["end"]
                data += '%s\n%s --> %s\n' % (i, begin.replace(".",","), end.replace(".",","))
                data += '%s\n' % node.text.strip(' \t\n\r')
                skip = True
                i += 1
            if tag == "br":
                if node.tail:
                    data += '%s\n\n' % node.tail.strip(' \t\n\r')
                    skip = False

        if is_py2:
            data = data.encode('utf8')
        save(options, data)

class subtitle_json(subtitle):
    def download(self, options):
        self.subtitle = get_http_data(self.url)
        data = json.loads(self.subtitle)
        number = 1
        subs = ""
        for i in data:
            subs += "%s\n%s --> %s\n" % (number, timestr(int(i["startMillis"])), timestr(int(i["endMillis"])))
            subs += "%s\n\n" % i["text"].encode("utf-8")
            number += 1

        save(options, subs)

class subtitle_sami(subtitle):
    def download(self, options):
        self.subtitle = get_http_data(self.url)
        tree = ET.XML(self.subtitle)
        subt = tree.find("Font")
        subs = ""
        n = 0
        for i in subt.getiterator():
            if i.tag == "Subtitle":
                n = i.attrib["SpotNumber"]
                if i.attrib["SpotNumber"] == "1":
                    subs += "%s\n%s --> %s\n" % (i.attrib["SpotNumber"], i.attrib["TimeIn"], i.attrib["TimeOut"])
                else:
                    subs += "\n%s\n%s --> %s\n" % (i.attrib["SpotNumber"], i.attrib["TimeIn"], i.attrib["TimeOut"])
            else:
                if int(n) > 0:
                    subs += "%s\n" % i.text

        if is_py2:
            subs = subs.encode('utf8')
        save(options, subs)

class subtitle_smi(subtitle):
    def download(self, options):
        self.subtitle = get_http_data(self.url)
        recomp = re.compile(r'<SYNC Start=(\d+)>\s+<P Class=\w+>(.*)<br>\s+<SYNC Start=(\d+)>\s+<P Class=\w+>', re.M|re.I|re.U)
        number = 1
        subs = ""
        for i in recomp.finditer(str(self.subtitle)):
            subs += "%s\n%s --> %s\n" % (number, timestr(i.group(1)), timestr(i.group(3)))
            text = "%s\n\n" % i.group(2)
            subs += text.replace("<br>", "\n")
            number += 1

        save(options, subs)

class subtitle_wsrt(subtitle):
    def download(self, options):
        self.subtitle = get_http_data(self.url)
        recomp = re.compile(r"(\d+)\r\n([\d:\.]+ --> [\d:\.]+)?([^\r\n]+)?\r\n([^\r\n]+)\r\n(([^\r\n]*)\r\n)?")
        srt = ""
        for i in recomp.finditer(self.subtitle):
            sub = "%s\n%s\n%s\n" % (i.group(1), i.group(2).replace(".", ","), i.group(4))
            if len(i.group(6)) > 0:
                sub += "%s\n" % i.group(6)
            sub += "\n"
            sub = re.sub('<[^>]*>', '', sub)
            srt += sub

        save(options, srt)

def save(options, data):
    filename = re.search(r"(.*)\.[a-z0-9]{2,3}$", options.output)
    if filename:
        options.output = "%s.srt" % filename.group(1)
    else:
        options.output = "%s.srt" % options.output

    log.info("Subtitle: %s", options.output)
    fd = open(options.output, "w")
    fd.write(data)
    fd.close()

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

    output = "%02d:%02d:%05.2f" % (hours, minutes, sec)
    return output.replace(".", ",")

def norm(name):
    if name[0] == "{":
        _, tag = name[1:].split("}")
        return tag
    else:
        return name
