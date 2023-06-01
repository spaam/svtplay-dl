import re


class M3U8:
    # Created for hls version <=7
    # https://tools.ietf.org/html/rfc8216

    MEDIA_SEGMENT_TAGS = ("EXTINF", "EXT-X-BYTERANGE", "EXT-X-DISCONTINUITY", "EXT-X-KEY", "EXT-X-MAP", "EXT-X-PROGRAM-DATE-TIME", "EXT-X-DATERANGE")
    MEDIA_PLAYLIST_TAGS = (
        "EXT-X-TARGETDURATION",
        "EXT-X-MEDIA-SEQUENCE",
        "EXT-X-DISCONTINUITY-SEQUENCE",
        "EXT-X-ENDLIST",
        "EXT-X-PLAYLIST-TYPE",
        "EXT-X-I-FRAMES-ONLY",
    )
    MASTER_PLAYLIST_TAGS = ("EXT-X-MEDIA", "EXT-X-STREAM-INF", "EXT-X-I-FRAME-STREAM-INF", "EXT-X-SESSION-DATA", "EXT-X-SESSION-KEY")
    MEDIA_OR_MASTER_PLAYLIST_TAGS = ("EXT-X-INDEPENDENT-SEGMENTS", "EXT-X-START")

    TAG_TYPES = {"MEDIA_SEGMENT": 0, "MEDIA_PLAYLIST": 1, "MASTER_PLAYLIST": 2}

    def __init__(self, data):

        self.version = None

        self.media_segment = []
        self.media_playlist = {}
        self.master_playlist = []

        self.encrypted = False
        self.independent_segments = False

        self.parse_m3u(data)

    def __str__(self):
        return (
            f"Version: {self.version}\nMedia Segment: {self.media_segment}\n"
            f"Media Playlist: {self.media_playlist}\nMaster Playlist: {self.master_playlist}\n"
            f"Encrypted: {self.encrypted}\tIndependent_segments: {self.independent_segments}"
        )

    def parse_m3u(self, data):
        if not data.startswith("#EXTM3U"):
            raise ValueError("Does not appear to be an 'EXTM3U' file.")

        data = data.replace("\r\n", "\n")
        lines = data.split("\n")[1:]

        last_tag_type = None
        tag_type = None

        media_segment_info = {}

        for index, l in enumerate(lines):
            if not l:
                continue
            elif l.startswith("#EXT"):

                info = {}
                tag, attr = _get_tag_attribute(l)
                if tag == "EXT-X-VERSION":
                    self.version = int(attr)

                # 4.3.2.  Media Segment Tags
                elif tag in M3U8.MEDIA_SEGMENT_TAGS:

                    tag_type = M3U8.TAG_TYPES["MEDIA_SEGMENT"]
                    # 4.3.2.1.  EXTINF
                    if tag == "EXTINF":
                        if "," in attr:
                            dur, title = attr.split(",", 1)
                        else:
                            dur = attr
                            title = None
                        info["duration"] = float(dur)
                        info["title"] = title

                    # 4.3.2.2.  EXT-X-BYTERANGE
                    elif tag == "EXT-X-BYTERANGE":
                        if "@" in attr:
                            n, o = attr.split("@", 1)
                            info["n"], info["o"] = (int(n), int(o))
                        else:
                            info["n"] = int(attr)
                            info["o"] = 0

                    # 4.3.2.3.  EXT-X-DISCONTINUITY
                    elif tag == "EXT-X-DISCONTINUITY":
                        pass

                    # 4.3.2.4.  EXT-X-KEY
                    elif tag == "EXT-X-KEY":
                        self.encrypted = True
                        info = _get_tuple_attribute(attr)
                        if "URI" not in info:
                            self.encrypted = False

                    # 4.3.2.5.  EXT-X-MAP
                    elif tag == "EXT-X-MAP":
                        info = _get_tuple_attribute(attr)
                        if "BYTERANGE" in info:
                            if "@" in info["BYTERANGE"]:
                                n, o = info["BYTERANGE"].split("@", 1)
                                info["EXT-X-BYTERANGE"] = {}
                                info["EXT-X-BYTERANGE"]["n"], info["EXT-X-BYTERANGE"]["o"] = (int(n), int(o))
                            else:
                                info["EXT-X-BYTERANGE"] = {}
                                info["EXT-X-BYTERANGE"]["n"] = int(attr)
                                info["EXT-X-BYTERANGE"]["o"] = 0
                        if "BYTERANGE" not in info:
                            info["EXTINF"] = {}
                            info["EXTINF"]["duration"] = 0
                        self.media_segment.insert(0, info)

                    # 4.3.2.6.  EXT-X-PROGRAM-DATE-TIME"
                    elif tag == "EXT-X-PROGRAM-DATE-TIME":
                        info = attr

                    # 4.3.2.7.  EXT-X-DATERANGE
                    elif tag == "EXT-X-DATERANGE":
                        info = _get_tuple_attribute(attr)

                    media_segment_info[tag] = info

                # 4.3.3.  Media Playlist Tags
                elif tag in M3U8.MEDIA_PLAYLIST_TAGS:

                    tag_type = M3U8.TAG_TYPES["MEDIA_PLAYLIST"]
                    # 4.3.3.1.  EXT-X-TARGETDURATION
                    if tag == "EXT-X-TARGETDURATION":
                        info = int(attr)

                    # 4.3.3.2.  EXT-X-MEDIA-SEQUENCE
                    elif tag == "EXT-X-MEDIA-SEQUENCE":
                        info = int(attr)

                    # 4.3.3.3.  EXT-X-DISCONTINUITY-SEQUENCE
                    elif tag == "EXT-X-DISCONTINUITY-SEQUENCE":
                        info = int(attr)

                    # 4.3.3.4.  EXT-X-ENDLIST
                    elif tag == "EXT-X-ENDLIST":
                        break

                    # 4.3.3.5.  EXT-X-PLAYLIST-TYPE
                    elif tag == "EXT-X-PLAYLIST-TYPE":
                        info = attr

                    # 4.3.3.6.  EXT-X-I-FRAMES-ONLY
                    elif tag == "EXT-X-I-FRAMES-ONLY":
                        pass

                    self.media_playlist[tag] = info

                # 4.3.4. Master Playlist Tags
                elif tag in M3U8.MASTER_PLAYLIST_TAGS:

                    tag_type = M3U8.TAG_TYPES["MASTER_PLAYLIST"]
                    # 4.3.4.1.  EXT-X-MEDIA
                    if tag == "EXT-X-MEDIA":
                        info = _get_tuple_attribute(attr)

                    # 4.3.4.2.  EXT-X-STREAM-INF
                    elif tag == "EXT-X-STREAM-INF":
                        info = _get_tuple_attribute(attr)
                        if "BANDWIDTH" not in info:
                            raise ValueError("Can't find 'BANDWIDTH' in 'EXT-X-STREAM-INF'")
                        info["URI"] = lines[index + 1]

                    # 4.3.4.3.  EXT-X-I-FRAME-STREAM-INF
                    elif tag == "EXT-X-I-FRAME-STREAM-INF":
                        info = _get_tuple_attribute(attr)

                    # 4.3.4.4.  EXT-X-SESSION-DATA
                    elif tag == "EXT-X-SESSION-DATA":
                        info = _get_tuple_attribute(attr)

                    # 4.3.4.5.  EXT-X-SESSION-KEY
                    elif tag == "EXT-X-SESSION-KEY":
                        self.encrypted = True
                        info = _get_tuple_attribute(attr)
                    info["TAG"] = tag

                    self.master_playlist.append(info)

                # 4.3.5. Media or Master Playlist Tags
                elif tag in M3U8.MEDIA_OR_MASTER_PLAYLIST_TAGS:

                    tag_type = M3U8.TAG_TYPES["MEDIA_PLAYLIST"]
                    # 4.3.5.1. EXT-X-INDEPENDENT-SEGMENTS
                    if tag == "EXT-X-INDEPENDENT-SEGMENTS":
                        self.independent_segments = True

                    # 4.3.5.2. EXT-X-START
                    elif tag == "EXT-X-START":
                        info = _get_tuple_attribute(attr)

                    self.media_playlist[tag] = info

                # Unused tags
                else:
                    pass
            # This is a comment
            elif l.startswith("#"):
                pass
            # This must be a url/uri
            else:
                tag_type = None

                if last_tag_type is M3U8.TAG_TYPES["MEDIA_SEGMENT"]:
                    media_segment_info["URI"] = l
                    self.media_segment.append(media_segment_info)
                    media_segment_info = {}

            last_tag_type = tag_type

            if self.media_segment and self.master_playlist:
                raise ValueError("This 'M3U8' file contains data for both 'Media Segment' and 'Master Playlist'. This is not allowed.")


def _get_tag_attribute(line):
    line = line[1:]
    try:
        search_line = re.search(r"^([A-Z\-]*):(.*)", line)
        return search_line.group(1), search_line.group(2)
    except Exception:
        return line, None


def _get_tuple_attribute(attribute):
    attr_tuple = {}
    for art_l in re.split(""",(?=(?:[^'"]|'[^']*'|"[^"]*")*$)""", attribute):
        if art_l:
            name, value = art_l.split("=", 1)
            name = name.strip()
            # Checks for attribute name
            if not re.match(r"^[A-Z0-9\-]*$", name):
                raise ValueError("Not a valid attribute name.")

            # Remove extra quotes of string
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            attr_tuple[name] = value

    return attr_tuple
