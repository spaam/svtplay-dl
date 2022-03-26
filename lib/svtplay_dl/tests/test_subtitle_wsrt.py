import os

import svtplay_dl.subtitle
from svtplay_dl.utils.parser import setup_defaults


def parse(subfile):
    with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "subtitle", subfile), encoding="utf8") as fd:
        data = fd.read()
    return data


def test_wsrt_old():
    data = parse("wsrt-old.srt")
    subtitle = svtplay_dl.subtitle.subtitle(setup_defaults(), "", "")
    assert subtitle._wrst(data) == "1\n01:23:45,678 --> 01:23:46,789\nHello world!\n\n2\n01:23:48,910 --> 01:23:49,101\nHello\nworld!\n"


def test_wsrt_pretext():
    data = parse("wsrt-pretext.srt")
    subtitle = svtplay_dl.subtitle.subtitle(setup_defaults(), "", "")
    assert (
        subtitle._wrst(data)
        == "1\n00:00:10,040 --> 00:00:12,520\nNån försökte slå ihjäl mig.\n\n2\n00:00:12,600 --> 00:00:16,200\n-Var fan har du varit?\n-Vad?\n"
    )


def test_wsrt_style_hash():
    data = parse("wsrt-style-hash.srt")
    subtitle = svtplay_dl.subtitle.subtitle(setup_defaults(), "", "")
    assert (
        subtitle._wrst(data)
        == "1\n00:00:06,360 --> 00:00:10,080\n1845 gav sig\nen brittisk expedition ut-\n\n2\n00:00:10,240 --> 00:00:15,040\n-för att söka ett av forsknings-\nresornas mest eftertraktade mål:\n"
    )
