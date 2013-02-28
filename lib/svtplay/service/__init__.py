class Service(object):
    pass

from aftonbladet import Aftonbladet
from dr import Dr
from expressen import Expressen
from hbo import Hbo
from justin import Justin
from kanal5 import Kanal5
from kanal9 import Kanal9
from nrk import Nrk
from qbrick import Qbrick
from ruv import Ruv
from sr import Sr
from svtplay import Svtplay
from tv4play import Tv4play
from urplay import Urplay
from viaplay import Viaplay


def service_handler(url):
    sites = [
        Aftonbladet(),
        Dr(),
        Expressen(),
        Hbo(),
        Justin(),
        Kanal5(),
        Kanal9(),
        Nrk(),
        Qbrick(),
        Ruv(),
        Sr(),
        Svtplay(),
        Tv4play(),
        Urplay(),
        Viaplay()]

    handler = None

    for i in sites:
        if i.handle(url):
            handler = i
            break

    return handler
