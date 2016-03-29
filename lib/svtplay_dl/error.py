# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-

from __future__ import absolute_import

class UIException(Exception):
    pass

class ServiceError(Exception):
    pass

class NoRequestedProtocols(UIException):
    """
    This excpetion is thrown when the service provides streams,
    but not using any accepted protocol (as decided by
    options.stream_prio).
    """

    def __init__(self, requested, found):
        """
        The constructor takes two mandatory parameters, requested
        and found. Both should be lists. requested is the protocols
        we want and found is the protocols that can be used to
        access the stream.
        """
        self.requested = requested
        self.found = found

        super(NoRequestedProtocols, self).__init__(
            "None of the provided protocols (%s) are in "
            "the current list of accepted protocols (%s)" % (
                self.found, self.requested
            )
        )

    def __repr__(self):
        return "NoRequestedProtocols(requested=%s, found=%s)" % (
            self.requested, self.found)
