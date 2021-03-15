from ckanext.dcat.utils import parse_accept_header
from ckanext.dcat.utils import parse_date_iso_format


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

    def test_empty(self):
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
