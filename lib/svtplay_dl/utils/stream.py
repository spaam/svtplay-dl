import logging
from operator import itemgetter
from typing import List

from svtplay_dl import error
from svtplay_dl.utils.http import HTTP


# TODO: should be set as the default option in the argument parsing?
DEFAULT_PROTOCOL_PRIO = ["dash", "hls", "http"]
LIVE_PROTOCOL_PRIO = ["hls", "dash", "http"]
DEFAULT_FORMAT_PRIO = ["h264", "h264-51"]


def sort_quality(data) -> List:
    data = sorted(data, key=lambda x: (x.bitrate, x.name), reverse=True)
    datas = []
    for i in data:
        datas.append([i.bitrate, i.name, i.format, i.resolution, i.language, i.audio_role])
    return datas


def list_quality(videos):
    data = [["Quality:", "Method:", "Codec:", "Resolution:", "Language:", "Role:"]]
    data.extend(sort_quality(videos))
    for i in range(len(data)):
        logging.info(
            f"{str(data[i][0]):<10s} {data[i][1].upper():<8s} {data[i][2]:<8s} {data[i][3]:<12s} {data[i][4]:<20s} {data[i][5]:<20s}",
        )


def protocol_prio(streams, priolist) -> List:
    """
    Given a list of VideoRetriever objects and a prioritized list of
    accepted protocols (as strings) (highest priority first), return
    a list of VideoRetriever objects that are accepted, and sorted
    by bitrate, and then protocol priority.
    """
    # Map score's to the reverse of the list's index values
    proto_score = dict(zip(priolist, range(len(priolist), 0, -1)))
    logging.debug("Protocol priority scores (higher is better): %s", str(proto_score))

    # Build a tuple (bitrate, proto_score, stream), and use it
    # for sorting.
    prioritized = [(s.bitrate, proto_score[s.name], s) for s in streams if s.name in proto_score]
    return [x[2] for x in sorted(prioritized, key=itemgetter(0, 1), reverse=True)]


def format_prio(streams, priolist) -> List:
    logging.debug("Format priority: %s", str(priolist))
    prioritized = [s for s in streams if s.format in priolist]
    return prioritized


def language_prio(config, streams) -> List:
    if config.get("audio_language"):
        language = config.get("audio_language")
    else:
        return streams
    prioritized = [s for s in streams if s.language == language]
    return prioritized


def audio_role(config, streams) -> List:
    if config.get("audio_role"):
        role = config.get("audio_role")
    elif config.get("audio_role") is None and config.get("audio_language"):
        return streams
    else:
        role = "main"

    prioritized = [s for s in streams if s.audio_role == role]
    return prioritized


def subtitle_filter(subtitles) -> List:
    languages = []
    subs = []
    if not subtitles:
        return subs
    preferred = subtitles[0].config.get("subtitle_preferred")
    all_subs = subtitles[0].config.get("get_all_subtitles")

    for sub in subtitles:
        if sub.subfix not in languages:
            if all_subs:
                subs.append(sub)
                languages.append(sub.subfix)
            else:
                if preferred is None:
                    subs.append(sub)
                    languages.append(sub.subfix)
                if preferred and sub.subfix == preferred:
                    subs.append(sub)
                    languages.append(sub.subfix)
    return subs


def subtitle_decider(stream, subtitles):
    if subtitles and (stream.config.get("merge_subtitle") or stream.config.get("subtitle") or stream.config.get("get_all_subtitles")):
        subtitles = subtitle_filter(subtitles)
        if stream.config.get("get_all_subtitles"):
            for sub in subtitles:
                if stream.config.get("get_url"):
                    print(sub.url)
                else:
                    sub.download()
                if stream.config.get("merge_subtitle"):
                    if not sub.subfix:
                        stream.config.set("get_all_subtitles", False)
        else:
            if stream.config.get("get_url"):
                print(subtitles[0].url)
            else:
                subtitles[0].download()
    elif stream.config.get("merge_subtitle"):
        stream.config.set("merge_subtitle", False)


def resolution(streams, resolutions: List) -> List:
    videos = []
    for stream in streams:
        for resolution in resolutions:
            if stream.resolution.find("x") > 0 and stream.resolution.split("x")[1] == resolution:
                videos.append(stream)
    return videos


def select_quality(config, streams):
    high = 0
    if isinstance(config.get("quality"), str):
        try:
            quality = int(config.get("quality").split("-")[0])
            if len(config.get("quality").split("-")) > 1:
                high = int(config.get("quality").split("-")[1])
        except ValueError:
            raise error.UIException("Requested quality is invalid. use a number or range lowerNumber-higherNumber")
    else:
        quality = config.get("quality")
    try:
        optq = int(quality)
    except ValueError:
        raise error.UIException("Requested quality needs to be a number")

    try:
        optf = int(config.get("flexibleq"))
    except ValueError:
        raise error.UIException("Flexible-quality needs to be a number")

    if optf == 0 and high:
        optf = (high - quality) / 2
        optq = quality + (high - quality) / 2

    if config.get("format_preferred"):
        form_prio = config.get("format_preferred").split(",")
    else:
        form_prio = DEFAULT_FORMAT_PRIO
    streams = format_prio(streams, form_prio)

    streams = audio_role(config, streams)
    if not streams:
        raise error.UIException(f"Can't find any streams with that audio role {config.get('audio_role')}")

    streams = language_prio(config, streams)
    if not streams:
        raise error.UIException(f"Can't find any streams with that audio language {config.get('audio_language')}")

    if config.get("resolution"):
        resolutions = config.get("resolution").split(",")
        streams = resolution(streams, resolutions)
        if not streams:
            raise error.UIException(f"Can't find any streams with that video resolution {config.get('resolution')}")

    # Extract protocol prio, in the form of "hls,http",
    # we want it as a list

    if config.get("stream_prio"):
        proto_prio = config.get("stream_prio").split(",")
    elif config.get("live") or streams[0].config.get("live"):
        proto_prio = LIVE_PROTOCOL_PRIO
    else:
        proto_prio = DEFAULT_PROTOCOL_PRIO

    # Filter away any unwanted protocols, and prioritize
    # based on --stream-priority.
    streams = protocol_prio(streams, proto_prio)

    if len(streams) == 0:
        raise error.NoRequestedProtocols(requested=proto_prio, found=list({s.name for s in streams}))

    # Build a dict indexed by bitrate, where each value
    # is the stream with the highest priority protocol.
    stream_hash = {}
    for s in streams:
        if s.bitrate not in stream_hash:
            stream_hash[s.bitrate] = s

    avail = sorted(stream_hash.keys(), reverse=True)

    # wanted_lim is a two element tuple defines lower/upper bounds
    # (inclusive). By default, we want only the best for you
    # (literally!).
    wanted_lim = (avail[0],) * 2
    if optq:
        wanted_lim = (optq - optf, optq + optf)

    # wanted is the filtered list of available streams, having
    # a bandwidth within the wanted_lim range.
    wanted = [a for a in avail if a >= wanted_lim[0] and a <= wanted_lim[1]]

    # If none remains, the bitrate filtering was too tight.
    if len(wanted) == 0:
        raise error.UIException("Can't find that quality. Try a different one listed in --list-quality or try --flexible-quality")

    http = HTTP(config)
    # Test if the wanted stream is available. If not try with the second best and so on.
    for w in wanted:
        res = http.get(stream_hash[w].url, cookies=stream_hash[w].kwargs.get("cookies", None))
        if res is not None and res.status_code < 404:
            return stream_hash[w]

    raise error.UIException("Streams not available to download.")
