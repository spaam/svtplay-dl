# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import sys
import logging
import re
import xml.etree.ElementTree as ET
import json

if sys.version_info > (3, 0):
    from urllib.request import Request, urlopen, build_opener, HTTPCookieProcessor
    from urllib.error import HTTPError, URLError
    from urllib.parse import urlparse, parse_qs, unquote_plus, quote_plus
    from io import BytesIO as StringIO
    from http.cookiejar import CookieJar, Cookie
else:
    from urllib2 import Request, urlopen, HTTPError, URLError, build_opener, HTTPCookieProcessor
    from urlparse import urlparse, parse_qs
    from urllib import unquote_plus, quote_plus
    from StringIO import StringIO
    from cookielib import CookieJar, Cookie

log = logging.getLogger('svtplay_dl')
progress_stream = sys.stderr

def get_http_data(url, method="GET", header="", data="", referer=None, cookiejar=None):
    """ Get the page to parse it for streams """
    if not cookiejar:
        cookiejar = CookieJar()
    request = build_opener(HTTPCookieProcessor(cookiejar))
    request.addheaders += [('User-Agent', 'Mozilla/5.0 (Windows; U; Windows NT 5.1; en-GB; rv:1.9.0.3) Gecko/2008092417 Firefox/3.0.3')]

    if len(header) > 0:
        request.addheaders += [('Content-Type', header)]
    if len(data) > 0:
        request.add_data(data)
    if referer:
        request.addheaders += [('Referer', referer)]
    try:
        response = request.open(url)
    except HTTPError as e:
        log.error("Something wrong with that url")
        log.error("Error code: %s" % e.code)
        sys.exit(5)
    except URLError as e:
        log.error("Something wrong with that url")
        log.error("Error code: %s" % e.reason)
        sys.exit(5)
    except ValueError as e:
        log.error("Try adding http:// before the url")
        sys.exit(5)
    if sys.version_info > (3, 0):
        data = response.read()
        try:
            data = data.decode("utf-8")
        except UnicodeDecodeError:
            pass
    else:
        try:
            data = response.read()
        except socket.error as e:
            log.error("Lost the connection to the server")
            sys.exit(5)
    response.close()
    return data

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
        uri, tag = name[1:].split("}")
        return tag
    else:
        return name

def subtitle_tt(options, data):
    i = 1
    data = ""
    skip = False
    tree = ET.parse(data)
    for node in tree.iter():
        tag = norm(node.tag)
        if tag == "p":
            if skip:
                data = data + "\n"
            data += '%s\n%s,%s --> %s,%s\n' % (i, node.attrib["begin"][:8], node.attrib["begin"][9:], node.attrib["end"][:8], node.attrib["end"][9:])
            data += '%s\n' % node.text.strip(' \t\n\r')
            skip = True
            i += 1
        if tag == "br":
            if node.tail:
                data += '%s\n\n' % node.tail.strip(' \t\n\r')
                skip = False
    filename = re.search("(.*)\.[a-z0-9]{2,3}$", options.output)
    if filename:
        options.output = "%s.srt" % filename.group(1)
    log.info("Subtitle: %s", options.output)
    fd = open(options.output, "w")
    fd.write(data)
    fd.close()

def subtitle_json(options, data):
    data = json.loads(data)
    number = 1
    subs = ""
    for i in data:
        subs += "%s\n%s --> %s\n" % (number, timestr(int(i["startMillis"])), timestr(int(i["endMillis"])))
        subs += "%s\n\n" % i["text"]
        number += 1

    filename = re.search("(.*)\.[a-z0-9]{2,3}$", options.output)
    if filename:
        options.output = "%s.srt" % filename.group(1)
    log.info("Subtitle: %s", options.output)
    fd = open(options.output, "w")
    fd.write(subs)
    fd.close()

def subtitle_sami(options, data):
    tree = ET.XML(data)
    subt = tree.find("Font")
    subs = ""
    for i in subt.getiterator():
        if i.tag == "Subtitle":
            if i.attrib["SpotNumber"] == 1:
                subs += "%s\n%s --> %s\n" % (i.attrib["SpotNumber"], i.attrib["TimeIn"], i.attrib["TimeOut"])
            else:
                subs += "\n%s\n%s --> %s\n" % (i.attrib["SpotNumber"], i.attrib["TimeIn"], i.attrib["TimeOut"])
        else:
            subs += "%s\n" % i.text

    filename = re.search("(.*)\.[a-z0-9]{2,3}$", options.output)
    if filename:
        options.output = "%s.srt" % filename.group(1)
    log.info("Subtitle: %s", options.output)
    fd = open(options.output, "w")
    fd.write(subs)
    fd.close()

def subtitle_smi(options, data):
    recomp = re.compile(r'<SYNC Start=(\d+)>\s+<P Class=\w+>(.*)<br>\s+<SYNC Start=(\d+)>\s+<P Class=\w+>', re.M|re.I|re.U)
    number = 1
    subs = ""
    for i in recomp.finditer(data):
        subs += "%s\n%s --> %s\n" % (number, timestr(i.group(1)), timestr(i.group(3)))
        text = "%s\n\n" % i.group(2)
        subs += text.replace("<br>", "\n")
        number += 1

    filename = re.search("(.*)\.[a-z0-9]{2,3}$", options.output)
    if filename:
        options.output = "%s.srt" % filename.group(1)
    log.info("Subtitle: %s", options.output)
    fd = open(options.output, "w")
    fd.write(subs)
    fd.close()

def subtitle_wsrt(options, data):
    recomp = re.compile("(\d+)\r\n([\d:\.]+ --> [\d:\.]+)?([^\r\n]+)?\r\n([^\r\n]+)\r\n(([^\r\n]*)\r\n)?")
    srt = ""
    for i in recomp.finditer(data):
        sub = "%s\n%s\n%s\n" % (i.group(1), i.group(2).replace(".", ","), i.group(4))
        if len(i.group(6)) > 0:
            sub += "%s\n" % i.group(6)
        sub += "\n"
        sub = re.sub('<[^>]*>', '', sub)
        srt += sub
    filename = re.search("(.*)\.[a-z0-9]{2,3}$", options.output)
    if filename:
        options.output = "%s.srt" % filename.group(1)
    log.info("Subtitle: %s", options.output)
    fd = open(options.output, "w")
    fd.write(srt)
    fd.close()

def select_quality(options, streams):
    available = sorted(streams.keys(), key=int)

    optq = int(options.quality)
    if optq:
        optf = int(options.flexibleq)
        if not optf:
            wanted = [optq]
        else:
            wanted = range(optq-optf, optq+optf+1)
    else:
        wanted = [available[-1]]

    selected = None
    for q in available:
        if q in wanted:
            selected = q
            break

    if not selected:
        log.error("Can't find that quality. Try one of: %s (or try --flexible-quality)",
                  ", ".join(map(str, available)))
        sys.exit(4)

    return streams[selected]

