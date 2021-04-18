import logging
from operator import itemgetter

from svtplay_dl import error
from svtplay_dl.utils.http import HTTP


# TODO: should be set as the default option in the argument parsing?
DEFAULT_PROTOCOL_PRIO = ["dash", "hls", "hds", "http"]
LIVE_PROTOCOL_PRIO = ["hls", "dash", "hds", "http"]
DEFAULT_FORMAT_PRIO = ["h264", "h264-51"]


def sort_quality(data):
    data = sorted(data, key=lambda x: (x.bitrate, x.name), reverse=True)
    datas = []
    for i in data:
        datas.append([i.bitrate, i.name, i.format, i.resolution])
    return datas


def list_quality(videos):
    data = sort_quality(videos)
    logging.info("Quality\tMethod\tCodec\tResolution")
    for i in data:
        logging.info("%s\t%s\t%s\t%s", i[0], i[1].upper(), i[2].upper(), i[3])


def protocol_prio(streams, priolist):
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


def format_prio(streams, priolist):
    logging.debug("Format priority: %s", str(priolist))
    prioritized = [s for s in streams if s.format in priolist]
    return prioritized


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

    # Extract protocol prio, in the form of "hls,hds,http",
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
        data = sort_quality(streams)
        quality = ", ".join("{} ({})".format(str(x), str(y)) for x, y in data)
        raise error.UIException("Can't find that quality. Try one of: %s (or " "try --flexible-quality)" % quality)

    http = HTTP(config)
    # Test if the wanted stream is available. If not try with the second best and so on.
    for w in wanted:
        res = http.get(stream_hash[w].url, cookies=stream_hash[w].kwargs.get("cookies", None))
        if res is not None and res.status_code < 404:
            return stream_hash[w]

    raise error.UIException("Streams not available to download.")
