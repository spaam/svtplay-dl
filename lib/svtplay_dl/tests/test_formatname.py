import platform
import unittest

from svtplay_dl.service import Service
from svtplay_dl.utils.output import _formatname
from svtplay_dl.utils.output import formatname
from svtplay_dl.utils.parser import setup_defaults


class formatnameTest(unittest.TestCase):
    all_combo = [
        [
            "test-{title}-{service}-{ext}-{episode}-{id}-{season}-{episodename}",
            {"title": "title", "season": 99, "episode": 21, "episodename": "episodename", "id": "0xdeadface", "ext": "ext"},
            "test-title-service-mp4-21-0xdeadface-99-episodename",
        ],
        [
            "test-{title}-{service}-{ext}-{episode}-{id}-{season}-{episodename}",
            {"title": "title", "season": 99, "episodename": "episodename", "id": "0xdeadface", "ext": "ext"},
            "test-title-service-mp4-0xdeadface-99-episodename",
        ],
        [
            "test-{title}-{service}-{ext}-{episode}-{id}-{season}-{episodename}",
            {"title": "title", "season": 99, "id": "0xdeadface", "ext": "ext"},
            "test-title-service-mp4-0xdeadface-99",
        ],
        [
            "test-{title}-{service}-{ext}-{episode}-{id}-{season}-{episodename}",
            {"title": "title", "episode": 21, "episodename": "episodename", "id": "0xdeadface", "ext": "ext"},
            "test-title-service-mp4-21-0xdeadface-episodename",
        ],
        [
            "test-{title}-{service}-{ext}-{episode}-{id}-{season}-{episodename}",
            {"title": "title", "episodename": "episodename", "id": "0xdeadface", "ext": "ext"},
            "test-title-service-mp4-0xdeadface-episodename",
        ],
        [
            "test-{title}-{service}-{ext}-{episode}-{id}-{season}-{episodename}",
            {"title": "title", "episodename": "episodename", "id": "0xdeadface"},
            "test-title-service-mp4-0xdeadface-episodename",
        ],
        [
            "test-{title}-{episode}-{season}-{service}-{episodename}-{id}-{ext}",
            {"title": "title", "season": 99, "episode": 21, "episodename": "episodename", "id": "0xdeadface", "ext": "ext"},
            "test-title-21-99-service-episodename-0xdeadface-mp4",
        ],
        [
            "test-{title}-{episode}-{season}-{service}-{episodename}-{id}-{ext}",
            {"title": "title", "season": 99, "episodename": "episodename", "id": "0xdeadface", "ext": "ext"},
            "test-title-99-service-episodename-0xdeadface-mp4",
        ],
        [
            "test-{title}-{episode}-{season}-{service}-{episodename}-{id}-{ext}",
            {"title": "title", "season": 99, "id": "0xdeadface", "ext": "ext"},
            "test-title-99-service-0xdeadface-mp4",
        ],
        [
            "test-{title}-{episode}-{season}-{service}-{episodename}-{id}-{ext}",
            {"title": "title", "episode": 21, "episodename": "episodename", "id": "0xdeadface", "ext": "ext"},
            "test-title-21-service-episodename-0xdeadface-mp4",
        ],
        [
            "test-{title}-{episode}-{season}-{service}-{episodename}-{id}-{ext}",
            {"title": "title", "episodename": "episodename", "id": "0xdeadface", "ext": "ext"},
            "test-title-service-episodename-0xdeadface-mp4",
        ],
        [
            "test-{title}-{episode}-{season}-{service}-{episodename}-{id}-{ext}",
            {"title": "title", "episodename": "episodename", "id": "0xdeadface"},
            "test-title-service-episodename-0xdeadface-mp4",
        ],
        [
            "{id}-{season}-{ext}-{episode}-{episodename}-{title}-{service}",
            {"title": "title", "season": 99, "episode": 21, "episodename": "episodename", "id": "0xdeadface", "ext": "ext"},
            "0xdeadface-99-mp4-21-episodename-title-service",
        ],
        [
            "{id}-{season}-{ext}-{episode}-{episodename}-{title}-{service}",
            {"title": "title", "season": 99, "episodename": "episodename", "id": "0xdeadface", "ext": "ext"},
            "0xdeadface-99-mp4-episodename-title-service",
        ],
        [
            "{id}-{season}-{ext}-{episode}-{episodename}-{title}-{service}",
            {"title": "title", "season": 99, "id": "0xdeadface", "ext": "ext"},
            "0xdeadface-99-mp4-title-service",
        ],
        [
            "{id}-{season}-{ext}-{episode}-{episodename}-{title}-{service}",
            {"title": "title", "episode": 21, "episodename": "episodename", "id": "0xdeadface", "ext": "ext"},
            "0xdeadface-mp4-21-episodename-title-service",
        ],
        [
            "{id}-{season}-{ext}-{episode}-{episodename}-{title}-{service}",
            {"title": "title", "episodename": "episodename", "id": "0xdeadface", "ext": "ext"},
            "0xdeadface-mp4-episodename-title-service",
        ],
        [
            "{id}-{season}-{ext}-{episode}-{episodename}-{title}-{service}",
            {"title": "title", "episodename": "episodename", "id": "0xdeadface"},
            "0xdeadface-mp4-episodename-title-service",
        ],
        [
            "{service}-{ext}-{season}-{id}-{title}-{episodename}-{episode}",
            {"title": "title", "season": 99, "episode": 21, "episodename": "episodename", "id": "0xdeadface", "ext": "ext"},
            "service-mp4-99-0xdeadface-title-episodename-21",
        ],
        [
            "{service}-{ext}-{season}-{id}-{title}-{episodename}-{episode}",
            {"title": "title", "season": 99, "episodename": "episodename", "id": "0xdeadface", "ext": "ext"},
            "service-mp4-99-0xdeadface-title-episodename",
        ],
        [
            "{service}-{ext}-{season}-{id}-{title}-{episodename}-{episode}",
            {"title": "title", "season": 99, "id": "0xdeadface", "ext": "ext"},
            "service-mp4-99-0xdeadface-title",
        ],
        [
            "{service}-{ext}-{season}-{id}-{title}-{episodename}-{episode}",
            {"title": "title", "episode": 21, "episodename": "episodename", "id": "0xdeadface", "ext": "ext"},
            "service-mp4-0xdeadface-title-episodename-21",
        ],
        [
            "{service}-{ext}-{season}-{id}-{title}-{episodename}-{episode}",
            {"title": "title", "episodename": "episodename", "id": "0xdeadface", "ext": "ext"},
            "service-mp4-0xdeadface-title-episodename",
        ],
        [
            "{service}-{ext}-{season}-{id}-{title}-{episodename}-{episode}",
            {"title": "title", "episodename": "episodename", "id": "0xdeadface"},
            "service-mp4-0xdeadface-title-episodename",
        ],
        [
            "test-{title}-{service}-{ext}-{episode}-{id}-{season}",
            {"title": "title", "season": 99, "episode": 21, "episodename": "episodename", "id": "0xdeadface", "ext": "ext"},
            "test-title-service-mp4-21-0xdeadface-99",
        ],
        [
            "test-{title}-{service}-{ext}-{episode}-{id}-{season}",
            {"title": "title", "season": 99, "episodename": "episodename", "id": "0xdeadface", "ext": "ext"},
            "test-title-service-mp4-0xdeadface-99",
        ],
        [
            "test-{title}-{service}-{ext}-{episode}-{id}-{season}",
            {"title": "title", "season": 99, "id": "0xdeadface", "ext": "ext"},
            "test-title-service-mp4-0xdeadface-99",
        ],
        [
            "test-{title}-{service}-{ext}-{episode}-{id}-{season}",
            {"title": "title", "episode": 21, "episodename": "episodename", "id": "0xdeadface", "ext": "ext"},
            "test-title-service-mp4-21-0xdeadface",
        ],
        [
            "test-{title}-{service}-{ext}-{episode}-{id}-{season}",
            {"title": "title", "episodename": "episodename", "id": "0xdeadface", "ext": "ext"},
            "test-title-service-mp4-0xdeadface",
        ],
        [
            "test-{title}-{service}-{ext}-{episode}-{id}-{season}",
            {"title": "title", "episodename": "episodename", "id": "0xdeadface"},
            "test-title-service-mp4-0xdeadface",
        ],
        [
            "{title}-{ext}-{episode}-{id}-{season}",
            {"title": "title", "season": 99, "episode": 21, "episodename": "episodename", "id": "0xdeadface", "ext": "ext"},
            "title-mp4-21-0xdeadface-99",
        ],
        [
            "{title}-{ext}-{episode}-{id}-{season}",
            {"title": "title", "season": 99, "episodename": "episodename", "id": "0xdeadface", "ext": "ext"},
            "title-mp4-0xdeadface-99",
        ],
        ["{title}-{ext}-{episode}-{id}-{season}", {"title": "title", "season": 99, "id": "0xdeadface", "ext": "ext"}, "title-mp4-0xdeadface-99"],
        [
            "{title}-{ext}-{episode}-{id}-{season}",
            {"title": "title", "episode": 21, "episodename": "episodename", "id": "0xdeadface", "ext": "ext"},
            "title-mp4-21-0xdeadface",
        ],
        [
            "{title}-{ext}-{episode}-{id}-{season}",
            {"title": "title", "episodename": "episodename", "id": "0xdeadface", "ext": "ext"},
            "title-mp4-0xdeadface",
        ],
        ["{title}-{ext}-{episode}-{id}-{season}", {"title": "title", "episodename": "episodename", "id": "0xdeadface"}, "title-mp4-0xdeadface"],
        [
            "{title}-{ext}.{episode}-{id}.{season}",
            {"title": "title", "season": 99, "episode": 21, "episodename": "episodename", "id": "0xdeadface", "ext": "ext"},
            "title-mp4.21-0xdeadface.99",
        ],
        [
            "{title}-{ext}.{episode}-{id}.{season}",
            {"title": "title", "season": 99, "episodename": "episodename", "id": "0xdeadface", "ext": "ext"},
            "title-mp4-0xdeadface.99",
        ],
        ["{title}-{ext}.{episode}-{id}.{season}", {"title": "title", "season": 99, "id": "0xdeadface", "ext": "ext"}, "title-mp4-0xdeadface.99"],
        [
            "{title}-{ext}.{episode}-{id}.{season}",
            {"title": "title", "episode": 21, "episodename": "episodename", "id": "0xdeadface", "ext": "ext"},
            "title-mp4.21-0xdeadface",
        ],
        [
            "{title}-{ext}.{episode}-{id}.{season}",
            {"title": "title", "episodename": "episodename", "id": "0xdeadface", "ext": "ext"},
            "title-mp4-0xdeadface",
        ],
        ["{title}-{ext}.{episode}-{id}.{season}", {"title": "title", "episodename": "episodename", "id": "0xdeadface"}, "title-mp4-0xdeadface"],
        [
            "{id}-{season}{ext}-{episode}{episodename}-{title}-{service}",
            {"title": "title", "season": 99, "episode": 21, "episodename": "episodename", "id": "0xdeadface", "ext": "ext"},
            "0xdeadface-99mp4-21episodename-title-service",
        ],
        [
            "{id}-{season}{ext}-{episode}{episodename}-{title}-{service}",
            {"title": "title", "season": 99, "episodename": "episodename", "id": "0xdeadface", "ext": "ext"},
            "0xdeadface-99mp4episodename-title-service",
        ],
        [
            "{id}-{season}{ext}-{episode}{episodename}-{title}-{service}",
            {"title": "title", "season": 99, "id": "0xdeadface", "ext": "ext"},
            "0xdeadface-99mp4-title-service",
        ],
        [
            "{id}-{season}{ext}-{episode}{episodename}-{title}-{service}",
            {"title": "title", "episode": 21, "episodename": "episodename", "id": "0xdeadface", "ext": "ext"},
            "0xdeadfacemp4-21episodename-title-service",
        ],
        [
            "{id}-{season}{ext}-{episode}{episodename}-{title}-{service}",
            {"title": "title", "episodename": "episodename", "id": "0xdeadface", "ext": "ext"},
            "0xdeadfacemp4episodename-title-service",
        ],
        [
            "{id}-{season}{ext}-{episode}{episodename}-{title}-{service}",
            {"title": "title", "episodename": "episodename", "id": "0xdeadface"},
            "0xdeadfacemp4episodename-title-service",
        ],
        [
            "{episodename}a{title}-{service}",
            {"title": "title", "season": 99, "episode": 21, "episodename": "episodename", "id": "0xdeadface", "ext": "ext"},
            "episodenameatitle-service.mp4",
        ],
        [
            "{episodename}a{title}-{service}",
            {"title": "title", "season": 99, "episodename": "episodename", "id": "0xdeadface", "ext": "ext"},
            "episodenameatitle-service.mp4",
        ],
        ["{episodename}a{title}-{service}", {"title": "title", "season": 99, "id": "0xdeadface", "ext": "ext"}, "atitle-service.mp4"],
        [
            "{episodename}a{title}-{service}",
            {"title": "title", "episode": 21, "episodename": "episodename", "id": "0xdeadface", "ext": "ext"},
            "episodenameatitle-service.mp4",
        ],
        [
            "{episodename}a{title}-{service}",
            {"title": "title", "episodename": "episodename", "id": "0xdeadface", "ext": "ext"},
            "episodenameatitle-service.mp4",
        ],
        ["{episodename}a{title}-{service}", {"title": "title", "episodename": "episodename", "id": "0xdeadface"}, "episodenameatitle-service.mp4"],
        [
            "{title}.{episode}.{episodename}-{id}-{service}.{ext}",
            {"title": "title", "season": 99, "episode": 21, "episodename": "episodename", "id": "0xdeadface", "ext": "ext"},
            "title.21.episodename-0xdeadface-service.mp4",
        ],
        [
            "{title}.{episode}.{episodename}-{id}-{service}.{ext}",
            {"title": "title", "season": 99, "episodename": "episodename", "id": "0xdeadface", "ext": "ext"},
            "title.episodename-0xdeadface-service.mp4",
        ],
        [
            "{title}.{episode}.{episodename}-{id}-{service}.{ext}",
            {"title": "title", "season": 99, "id": "0xdeadface", "ext": "ext"},
            "title-0xdeadface-service.mp4",
        ],
        [
            "{title}.{episode}.{episodename}-{id}-{service}.{ext}",
            {"title": "title", "episode": 21, "episodename": "episodename", "id": "0xdeadface", "ext": "ext"},
            "title.21.episodename-0xdeadface-service.mp4",
        ],
        [
            "{title}.{episode}.{episodename}-{id}-{service}.{ext}",
            {"title": "title", "episodename": "episodename", "id": "0xdeadface", "ext": "ext"},
            "title.episodename-0xdeadface-service.mp4",
        ],
        [
            "{title}.{episode}.{episodename}-{id}-{service}.{ext}",
            {"title": "title", "episodename": "episodename", "id": "0xdeadface"},
            "title.episodename-0xdeadface-service.mp4",
        ],
        [
            "{title}.s{season}e{episode}.{episodename}-{id}-{service}.{ext}",
            {"title": "title", "season": 99, "episode": 21, "episodename": "episodename", "id": "0xdeadface", "ext": "ext"},
            "title.s99e21.episodename-0xdeadface-service.mp4",
        ],
        [
            "{title}.s{season}e{episode}.{episodename}-{id}-{service}.{ext}",
            {"title": "title", "season": 99, "episodename": "episodename", "id": "0xdeadface", "ext": "ext"},
            "title.s99.episodename-0xdeadface-service.mp4",
        ],
    ]

    def test_formatname(self):
        for item in self.all_combo:
            config = setup_defaults()
            config.set("filename", item[0])
            service = Service(config, "localhost")
            service.output.update(item[1])
            service.output["ext"] = "mp4"
            assert str(_formatname(service.output, config)) == item[2]


class formatnameTest2(unittest.TestCase):
    def test_formatnameEmpty(self):
        config = setup_defaults()
        service = Service(config, "http://localhost")
        service.output["ext"] = "mp4"
        assert str(formatname(service.output, config).name) == "-service.mp4"

    def test_formatnameOutput(self):
        config = setup_defaults()
        if platform.system() == "Windows":
            config.set("output", "c:\\Users")
            service = Service(config, "http://localhost")
            service.output["ext"] = "mp4"
            assert str(formatname(service.output, config)) == "c:\\Users\\-service.mp4"
        else:
            config.set("output", "/tmp")
            service = Service(config, "http://localhost")
            service.output["ext"] = "mp4"
            assert str(formatname(service.output, config)) == "/tmp/-service.mp4"

    def test_formatnameBasedir(self):
        config = setup_defaults()
        service = Service(config, "http://localhost")
        service.output["basedir"] = True
        service.output["ext"] = "mp4"
        assert str(formatname(service.output, config).name) == "-service.mp4"

    def test_formatnameTvshow(self):
        config = setup_defaults()
        service = Service(config, "http://localhost")
        service.output["tvshow"] = True
        service.output["title"] = "kalle"
        service.output["season"] = 2
        service.output["episode"] = 2
        service.output["ext"] = "mp4"
        assert str(formatname(service.output, config).name) == "kalle.s02e02-service.mp4"

    def test_formatnameTvshowSubfolder(self):
        config = setup_defaults()
        config.set("subfolder", True)
        service = Service(config, "http://localhost")
        service.output["tvshow"] = True
        service.output["title"] = "kalle"
        service.output["season"] = 2
        service.output["episode"] = 2
        service.output["ext"] = "mp4"
        if platform.system() == "Windows":
            assert str(formatname(service.output, config)) == "kalle\\kalle.s02e02-service.mp4"
        else:
            assert str(formatname(service.output, config)) == "kalle/kalle.s02e02-service.mp4"

    def test_formatnameTvshowSubfolderMovie(self):
        config = setup_defaults()
        config.set("subfolder", True)
        service = Service(config, "http://localhost")
        service.output["tvshow"] = False
        service.output["title"] = "kalle"
        service.output["season"] = 2
        service.output["episode"] = 2
        service.output["ext"] = "mp4"
        if platform.system() == "Windows":
            assert str(formatname(service.output, config)) == "movies\\kalle.s02e02-service.mp4"
        else:
            assert str(formatname(service.output, config)) == "movies/kalle.s02e02-service.mp4"

    def test_formatnameTvshowPath(self):
        config = setup_defaults()
        if platform.system() == "Windows":
            config.set("path", "c:\\")
        else:
            config.set("path", "/tmp")
        service = Service(config, "http://localhost")
        service.output["title"] = "kalle"
        service.output["season"] = 2
        service.output["episode"] = 2
        service.output["ext"] = "mp4"
        if platform.system() == "Windows":
            assert str(formatname(service.output, config)) == "c:\\kalle.s02e02-service.mp4"
        else:
            assert str(formatname(service.output, config)) == "/tmp/kalle.s02e02-service.mp4"
