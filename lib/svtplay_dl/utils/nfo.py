import copy
import logging
import xml.etree.ElementTree as ET
from datetime import datetime

from svtplay_dl.utils.output import find_dupes
from svtplay_dl.utils.output import formatname

# https://kodi.wiki/view/NFO_files/TV_shows#nfo_Tags


def write_nfo_episode(output, config):
    if not output["title_nice"]:
        # If we don't even have the title, skip the NFO
        return

    root = ET.Element("episodedetails")
    ET.SubElement(root, "showtitle").text = output["title_nice"]
    if output["episodename"]:
        ET.SubElement(root, "title").text = output["episodename"]
    if output["season"]:
        ET.SubElement(root, "season").text = str(output["season"])
    if output["episode"]:
        ET.SubElement(root, "episode").text = str(output["episode"])
    ET.SubElement(root, "plot").text = output["episodedescription"]
    if output["publishing_datetime"] is not None:
        ET.SubElement(root, "aired").text = datetime.fromtimestamp(output["publishing_datetime"]).isoformat()
    if not config.get("thumbnail") and output["showthumbnailurl"]:
        # Set the thumbnail path to download link if not thumbnail downloaded
        ET.SubElement(root, "thumb").text = output["episodethumbnailurl"]
    loutout = output.copy()
    loutout["ext"] = "nfo"
    filename = formatname(loutout, config)
    dupe, fileame = find_dupes(loutout.copy(), config, False)
    if dupe and not config.get("force_nfo"):
        logging.warning("File (%s) already exists. Use --force-nfo to overwrite", fileame.name)
        return
    logging.info("NFO episode: %s", filename)

    tree = ET.ElementTree(root)
    tree.write(filename, encoding="UTF-8", xml_declaration=True)


def write_nfo_tvshow(output, config):
    # Config for tvshow nfo file
    if not output["title_nice"]:
        # If we don't even have the title, skip the NFO
        return
    root = ET.Element("tvshow")
    ET.SubElement(root, "title").text = output["title_nice"] if not None else output["title"]
    if output["showdescription"]:
        ET.SubElement(root, "plot").text = output["showdescription"]
    if config.get("thumbnail"):
        # Set the thumbnail relative path to downloaded thumbnail
        ET.SubElement(root, "thumb").text = f"{output['title']}.tvshow.tbn"
    elif output["episodethumbnailurl"]:
        # Set the thumbnail path to download link if not thumbnail downloaded
        ET.SubElement(root, "thumb").text = output["showthumbnailurl"]

    cconfig = copy.deepcopy(config)
    cconfig.set("output", config.get("output"))
    cconfig.set("path", config.get("path"))
    cconfig.set("subfolder", config.get("subfolder"))
    cconfig.set("filename", "tvshow.nfo")

    loutput = output.copy()
    filename = formatname(loutput, cconfig)
    dupe, fileame = find_dupes(loutput, cconfig, False)
    if dupe and not cconfig.get("force_nfo"):
        logging.warning("File (%s) already exists. Use --force-nfo to overwrite", fileame.name)
        return

    logging.info("NFO show: %s", filename)

    tree = ET.ElementTree(root)
    tree.write(filename, encoding="UTF-8", xml_declaration=True)
