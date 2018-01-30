#!/usr/bin/python
# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-

# The unittest framwork doesn't play nice with pylint:
#   pylint: disable-msg=C0103


class HandlesURLsTestMixin():
    """
    This should only be inherited from classes which also inherit
    a unittest compatible base class.
    """
    # pylint: disable-msg=no-init

    def test_handles_urls(self):
        if len(self.urls['ok']) > 0:
            for url in self.urls['ok']:
                self.assertTrue(self.service.handles(url))

        if len(self.urls['bad']) > 0:
            for url in self.urls['bad']:
                self.assertFalse(self.service.handles(url))
