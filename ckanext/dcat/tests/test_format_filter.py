import nose
from ckantoolkit.tests import helpers

from ckanext.dcat import converters

eq_ = nose.tools.eq_


class TestFormatFilters(object):
    @helpers.change_config('ckanext.file_filter.filter_type', 'whitelist')
    @helpers.change_config('ckanext.file_filter.whitelist', 'csv xlsx pdf')

    def test_get_whitelist(self):
        whitelist = converters.get_whitelist()
        eq_(len(whitelist), 3)
        assert 'csv' in whitelist
        assert 'xlsx' in whitelist

    def test_whitelist_filter(self):
        disallow_exe = converters.disallow_file_format('exe')
        eq_(disallow_exe, True)

        disallow_csv = converters.disallow_file_format('csv')
        eq_(disallow_csv, False)

    @helpers.change_config('ckanext.file_filter.filter_type', 'blacklist')
    @helpers.change_config('ckanext.file_filter.blacklist', 'exe jar')
    def test_get_blacklist(self):
        blacklist = converters.get_blacklist()
        eq_(len(blacklist), 2)
        assert 'exe' in blacklist

    def test_blacklist_filter(self):
        disallow_exe = converters.disallow_file_format('exe')
        eq_(disallow_exe, True)

        disallow_csv = converters.disallow_file_format('csv')
        eq_(disallow_csv, False)
