from ckanext.dcat.utils import parse_accept_header
from ckanext.dcat.utils import (
    parse_date_iso_format,
    is_xloader_format,
    is_dcat_modified_field_changed,
    parse_identifier
)


def test_accept_header_empty():

    header = ''

    _format = parse_accept_header(header)

    assert _format is None

def test_accept_header_basic_found():

    header = 'application/rdf+xml'

    _format = parse_accept_header(header)

    assert _format == 'rdf'

def test_accept_header_basic_not_found():

    header = 'image/gif'

    _format = parse_accept_header(header)

    assert _format is None

def test_accept_header_multiple():

    header = 'application/rdf+xml, application/ld+json'

    _format = parse_accept_header(header)

    assert _format == 'rdf'

def test_accept_header_multiple_not_found():

    header = 'image/gif, text/unknown'

    _format = parse_accept_header(header)

    assert _format is None

def test_accept_header_multiple_first_not_found():

    header = 'image/gif, application/ld+json, text/turtle'

    _format = parse_accept_header(header)

    assert _format == 'jsonld'

def test_accept_header_q_param():

    header = 'text/turtle; q=0.8'

    _format = parse_accept_header(header)

    assert _format == 'ttl'

def test_accept_header_q_param_multiple():

    header = 'text/turtle; q=0.8, text/n3; q=0.6'

    _format = parse_accept_header(header)

    assert _format == 'ttl'

def test_accept_header_q_param_multiple_first_not_found():

    header = 'image/gif; q=1.0, text/turtle; q=0.8, text/n3; q=0.6'

    _format = parse_accept_header(header)

    assert _format == 'ttl'

def test_accept_header_wildcard():

    header = 'text/*'

    _format = parse_accept_header(header)

    assert _format in ('ttl', 'n3')

def test_accept_header_wildcard_multiple():

    header = 'image/gif; q=1.0, text/*; q=0.5'

    _format = parse_accept_header(header)

    assert _format in ('ttl', 'n3')

def test_accept_header_double_wildcard():

    header = '*/*'

    _format = parse_accept_header(header)

    assert _format is None

def test_accept_header_double_wildcard_multiple():

    header = 'image/gif; q=1.0, text/csv; q=0.8, */*; q=0.1'

    _format = parse_accept_header(header)

    assert _format is None

def test_accept_header_html():

    header = 'text/html'

    _format = parse_accept_header(header)

    assert _format is None

def test_accept_header_html_multiple():

    header = 'image/gif; q=1.0, text/html; q=0.8, text/turtle; q=0.6'

    _format = parse_accept_header(header)

    assert _format is None


class TestDateIsoFormat(object):

    def test_empty_date(self):
        date = ''
        _date = parse_date_iso_format(date)
        assert _date is None

    def test_date_command(self):
        date = 'Thu Sep 25 10:36:28 2020'
        _date = parse_date_iso_format(date)
        assert _date == '2020-09-25T10:36:28'

    def test_iso_datetime(self):
        date = '2020-02-27T21:26:01.123456'
        _date = parse_date_iso_format(date)
        assert _date == '2020-02-27T21:26:01'

    def test_iso_date(self):
        date = '2020-09-25'
        _date = parse_date_iso_format(date)
        assert _date == '2020-09-25T00:00:00'

    def test_iso_datetime_stripped(self):
        date = '20200925T104941'
        _date = parse_date_iso_format(date)
        assert _date == '2020-09-25T10:49:41'

    def test_date_with_slash(self):
        date = '2020/09/25'
        _date = parse_date_iso_format(date)
        assert _date == '2020-09-25T00:00:00'


class TestIsXloaderFormat(object):

    def test_empty_format(self):
        resource_format = ''
        xloader_format = is_xloader_format(resource_format)
        assert not xloader_format

    def test_csv_format(self):
        resource_format = 'csv'
        xloader_format = is_xloader_format(resource_format)
        assert xloader_format

    def test_xls_format(self):
        resource_format = 'xls'
        xloader_format = is_xloader_format(resource_format)
        assert xloader_format


class TestIsDcatModifiedFieldChanged(object):
    def test_empty_old_package_dict(self):
        old_package_dict = {}
        new_package_dict = {
            "title": "Test Dataset",
            "name": "test-dataset",
            "extras": [
                {
                    "key": "dcat_modified",
                    "value": "2021-03-01T10:10:45.123456"
                }
            ]
        }
        changed_dcat_modified = is_dcat_modified_field_changed(old_package_dict, new_package_dict)
        assert not changed_dcat_modified

    def test_empty_new_package_dict(self):
        old_package_dict = {
            "title": "Test Dataset",
            "name": "test-dataset",
            "extras": [
                {
                    "key": "dcat_modified",
                    "value": "2020-12-01T09:18:30.908070"
                }
            ]
        }
        new_package_dict = {}
        changed_dcat_modified = is_dcat_modified_field_changed(old_package_dict, new_package_dict)
        assert not changed_dcat_modified

    def test_null_old_package_dict(self):
        old_package_dict = None
        new_package_dict = {
            "title": "Test Dataset",
            "name": "test-dataset",
            "extras": [
                {
                    "key": "dcat_modified",
                    "value": "2021-03-01T10:10:45.123456"
                }
            ]
        }
        changed_dcat_modified = is_dcat_modified_field_changed(old_package_dict, new_package_dict)
        assert not changed_dcat_modified

    def test_null_new_package_dict(self):
        old_package_dict = {
            "title": "Test Dataset",
            "name": "test-dataset",
            "extras": [
                {
                    "key": "dcat_modified",
                    "value": "2020-12-01T09:18:30.908070"
                }
            ]
        }
        new_package_dict = None
        changed_dcat_modified = is_dcat_modified_field_changed(old_package_dict, new_package_dict)
        assert not changed_dcat_modified

    def test_missinng_dcat_modified_in_new_package_dict(self):
        old_package_dict = {
            "title": "Test Dataset",
            "name": "test-dataset",
            "extras": [
                {
                    "key": "dcat_modified",
                    "value": "2020-12-01T09:18:30.908070"
                }
            ]
        }
        new_package_dict = {
            "title": "Test Dataset",
            "name": "test-dataset"
        }
        changed_dcat_modified = is_dcat_modified_field_changed(old_package_dict, new_package_dict)
        assert changed_dcat_modified

    def test_changed_dcat_modified(self):
        old_package_dict = {
            "title": "Test Dataset",
            "name": "test-dataset",
            "extras": [
                {
                    "key": "dcat_modified",
                    "value": "2020-12-01T09:18:30.908070"
                }
            ]
        }
        new_package_dict = {
            "title": "Test Dataset",
            "name": "test-dataset",
            "extras": [
                {
                    "key": "dcat_modified",
                    "value": "2021-03-01T10:10:45.123456"
                }
            ]
        }
        changed_dcat_modified = is_dcat_modified_field_changed(old_package_dict, new_package_dict)
        assert changed_dcat_modified

    def test_same_dcat_modified(self):
        old_package_dict = {
            "title": "Test Dataset",
            "name": "test-dataset",
            "extras": [
                {
                    "key": "dcat_modified",
                    "value": "2021-03-01T10:10:45.123456"
                }
            ]
        }
        new_package_dict = {
            "title": "Test Dataset",
            "name": "test-dataset",
            "extras": [
                {
                    "key": "dcat_modified",
                    "value": "2021-03-01T10:10:45.123456"
                }
            ]
        }
        changed_dcat_modified = is_dcat_modified_field_changed(old_package_dict, new_package_dict)
        assert not changed_dcat_modified


class TestParseID(object):
    def test_parse_id_in_url_found(self):
        dataset_1 = {
            'identifier': 'http://example.com/item.html?id=someid&sublayer=0',
            'title': 'Dataset 1'
        }
        guid_1 = parse_identifier(dataset_1.get('identifier'))
        assert guid_1 == 'someid'

    def test_parse_id_in_url_null(self):
        dataset_2 = {
            'identifier': 'http://example.com/item.html?id=null&sublayer=0',
            'title': 'Dataset 2'
        }
        guid_2 = parse_identifier(dataset_2.get('identifier'))
        assert guid_2 == 'null'

    def test_parse_id_in_url_none(self):
        dataset_3 = {
            'identifier': 'http://example.com/item.html?id=none&sublayer=0',
            'title': 'Dataset 3'
        }
        guid_3 = parse_identifier(dataset_3.get('identifier'))
        assert guid_3 == 'none'

    def test_parse_id_in_url_not_found(self):
        dataset_4 = {
            'identifier': 'http://example.com/item.html?id=&sublayer=0',
            'title': 'Dataset 4'
        }
        guid_4 = parse_identifier(dataset_4.get('identifier'))
        assert guid_4 == 'http://example.com/item.html?id=&sublayer=0'
