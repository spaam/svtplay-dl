import logging
import xml.etree.ElementTree as ET
from datetime import datetime

from svtplay_dl.utils.output import formatname
from svtplay_dl.utils.parser import Options

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

    filename = formatname(output.copy(), config, extension="nfo")
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
        ET.SubElement(root, "thumb").text = "{}.tvshow.tbn".format(output["title"])
    elif output["episodethumbnailurl"]:
        # Set the thumbnail path to download link if not thumbnail downloaded
        ET.SubElement(root, "thumb").text = output["showthumbnailurl"]

    cconfig = Options()
    cconfig.set("output", config.get("output"))
    cconfig.set("path", config.get("path"))
    cconfig.set("subfolder", config.get("subfolder"))
    cconfig.set("filename", "tvshow.{ext}")
    filename = formatname(output.copy(), cconfig, extension="nfo")
    logging.info("NFO show: %s", filename)

    tree = ET.ElementTree(root)
    tree.write(filename, encoding="UTF-8", xml_declaration=True)
