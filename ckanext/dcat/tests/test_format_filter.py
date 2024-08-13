from ckantoolkit.tests import helpers

from ckanext.dcat import converters


class TestFormatFilters(object):
    @helpers.change_config('ckanext.file_filter.filter_type', 'whitelist')
    @helpers.change_config('ckanext.file_filter.whitelist', 'csv xlsx pdf text/html')
    def test_get_whitelist(self):
        whitelist = converters.get_whitelist()
        assert len(whitelist) == 4
        assert 'csv' in whitelist
        assert 'xlsx' in whitelist

    def test_whitelist_filter(self):
        disallow_exe = converters.disallow_file_format('exe')
        assert disallow_exe

        disallow_csv = converters.disallow_file_format('csv')
        assert not disallow_csv

    @helpers.change_config('ckanext.file_filter.filter_type', 'blacklist')
    @helpers.change_config('ckanext.file_filter.blacklist', 'exe jar')
    def test_get_blacklist(self):
        blacklist = converters.get_blacklist()
        assert len(blacklist) == 2
        assert 'exe' in blacklist

    def test_blacklist_filter(self):
        disallow_exe = converters.disallow_file_format('exe')
        assert disallow_exe

        disallow_csv = converters.disallow_file_format('csv')
        assert not disallow_csv
