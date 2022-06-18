from difflib import SequenceMatcher


def filter_files(m3u8):
    files = []
    good = m3u8.media_segment[1]["URI"]
    for segment in m3u8.media_segment:
        if SequenceMatcher(None, good, segment["URI"]).ratio() > 0.7:
            files.append(segment)
    m3u8.media_segment = files
    return m3u8
