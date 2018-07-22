import logging

import xml.etree.ElementTree as ET
from svtplay_dl.utils.output import formatname
from svtplay_dl.utils.parser import Options


def write_nfo_episode(output, config):
    root = ET.Element("episodedetails")
    ET.SubElement(root, "title").text = output["title_nice"]
    ET.SubElement(root, "showtitle").text = output["episodename"]
    ET.SubElement(root, "season").text = output["season"]
    ET.SubElement(root, "episode").text = output["episode"]
    ET.SubElement(root, "plot").text = output["showdescription"]
    if not config.get("thumbnail"):
        # Set the thumbnail path to download link if not thumbnail downloaded
        ET.SubElement(root, "thumb").text = output["showthumbnailurl"]

    filename = formatname(output.copy(), config, extension="nfo")
    logging.info("NFO episode: %s", filename)

    tree = ET.ElementTree(root)
    tree.write(filename, encoding="UTF-8", xml_declaration=True)


def write_nfo_tvshow(output, config):
    # Config for tvshow nfo file
    root = ET.Element("tvshow")
    ET.SubElement(root, "title").text = output["title_nice"]
    ET.SubElement(root, "plot").text = output["episodedescription"]
    if config.get("thumbnail"):
        # Set the thumbnail relative path to downloaded thumbnail
        ET.SubElement(root, "thumb").text = "{}.tvshow.tbn".format(output["title"])
    else:
        # Set the thumbnail path to download link if not thumbnail downloaded
        ET.SubElement(root, "thumb").text = output["episodethumbnailurl"]

    cconfig = Options()
    cconfig.set("output", config.get("output"))
    cconfig.set("path", config.get("path"))
    cconfig.set("subfolder", config.get("subfolder"))
    cconfig.set("filename", "tvshow.{ext}")
    filename = formatname(output.copy(), cconfig, extension="nfo")
    logging.info("NFO show: %s", filename)

    tree = ET.ElementTree(root)
    tree.write(filename, encoding="UTF-8", xml_declaration=True)