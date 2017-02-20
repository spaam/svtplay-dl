import os, sys
from subprocess import check_output
from pkg_resources import parse_version
from re import findall, sub, split
from requests import get
from svtplay_dl.utils import which
from svtplay_dl import log

def is_old():
    if not which('ffmpeg'):
        return None
    version_check = check_output([which('ffmpeg'),'-version']).split('\n')[0].split(' ')[:3]
    version_check = [v for v in version_check if findall('\d+', v)][0]
    if 'N' in version_check[0]:
        k = 1 if version_check.endswith('static') else 0
        version_check = version_check.split('-')[::-1][k][1:]

        r = get('https://api.github.com/repos/FFmpeg/FFmpeg/commits/' + version_check)
        print ' '.join(split('T|Z', r.json()['commit']['committer']['date'])[:2])
        if ' '.join(split('T|Z', r.json()['commit']['committer']['date'])[:2]) < "2012-09-28 01:02:28":
            return True
    else:
        if not version_check.endswith('.git'):
            version_check = version_check.split('-')[0]
        else:
            version_check = version_check.replace('.git','')
        if parse_version(version_check) <= parse_version('1.0'):
            return True

def get_ffmpeg():
    from platform import system
    ffmpeg = '' if which('ffmpeg') is None else os.path.dirname(which('ffmpeg'))
    system = system().lower()
    text = '(recommended) '
    n = 0

    log.info("Please choose any of the following options:")

    if 'darwin' in system:
        n += 1
        log.info('\t{0}. {1}Run this in your terminal: sudo brew update && sudo brew upgrade ffmpeg'.format(n, text))
        text = ''
    n += 1
    log.info('\t{0}. {1}Follow the instructions under "Quick run!" at: https://github.com/iwconfig/dlffmpeg#quick-run'.format(n, text))
    n += 1
    log.info("\t{0}. Run this in your terminal: sudo pip install -U dlffmpeg; sudo dlffmpeg {1}".format(n, ffmpeg))

    r = get('http://ffmpeg.org/releases/')
    latest = []
    html = sub('<[^<]+?>', '', str(r.text)).split('\n')
    latest[:] = [x for x in html if 'ffmpeg' in x]
    for v in html:
        if 'ffmpeg' in v:
            latest.append(v.split(' ')[1])
    curr_version = '.'.join(findall('\d', max(latest, key=parse_version)))
    if 'windows' in system:
        text = 'and read up on how to compile ffmpeg for windows at: https://trac.ffmpeg.org/wiki/CompilationGuide#Windows'
    else:
        text = "Usage:{0}Download{0}unpack{0}go into the folder with a terminal{0}run: ./configure; make; sudo make install; mv ffmpeg {1}".format('\n\t\t   - ', ffmpeg)

    n += 1
    log.info("\t{0}. Download and install the latest ({1}) tar ball here: http://ffmpeg.org/releases/ffmpeg-{1}.tar.gz\n\t   {2}\n".format(n, curr_version, text))
    log.info("Or check this site for more: https://ffmpeg.org/download.html")