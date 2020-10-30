import nose

from ckanext.dcat.utils import parse_accept_header
from ckanext.dcat.utils import parse_date_iso_format

eq_ = nose.tools.eq_


class TestAcceptHeaders(object):

    def test_empty(self):

        header = ''

        _format = parse_accept_header(header)

        eq_(_format, None)

    def test_basic_found(self):

        header = 'application/rdf+xml'

        _format = parse_accept_header(header)

        eq_(_format, 'rdf')

    def test_basic_not_found(self):

        header = 'image/gif'

        _format = parse_accept_header(header)

        eq_(_format, None)

    def test_multiple(self):

        header = 'application/rdf+xml, application/ld+json'

        _format = parse_accept_header(header)

        eq_(_format, 'rdf')

    def test_multiple_not_found(self):

        header = 'image/gif, text/unknown'

        _format = parse_accept_header(header)

        eq_(_format, None)

    def test_multiple_first_not_found(self):

        header = 'image/gif, application/ld+json, text/turtle'

        _format = parse_accept_header(header)

        eq_(_format, 'jsonld')

    def test_q_param(self):

        header = 'text/turtle; q=0.8'

        _format = parse_accept_header(header)

        eq_(_format, 'ttl')

    def test_q_param_multiple(self):

        header = 'text/turtle; q=0.8, text/n3; q=0.6'

        _format = parse_accept_header(header)

        eq_(_format, 'ttl')

    def test_q_param_multiple_first_not_found(self):

        header = 'image/gif; q=1.0, text/turtle; q=0.8, text/n3; q=0.6'

        _format = parse_accept_header(header)

        eq_(_format, 'ttl')

    def test_wildcard(self):

        header = 'text/*'

        _format = parse_accept_header(header)

        assert _format in ('ttl', 'n3')

    def test_wildcard_multiple(self):

        header = 'image/gif; q=1.0, text/*; q=0.5'

        _format = parse_accept_header(header)

        assert _format in ('ttl', 'n3')

    def test_double_wildcard(self):

        header = '*/*'

        _format = parse_accept_header(header)

        eq_(_format, None)

    def test_double_wildcard_multiple(self):

        header = 'image/gif; q=1.0, text/csv; q=0.8, */*; q=0.1'

        _format = parse_accept_header(header)

        eq_(_format, None)

    def test_html(self):

        header = 'text/html'

        _format = parse_accept_header(header)

        eq_(_format, None)

    def test_html_multiple(self):

        header = 'image/gif; q=1.0, text/html; q=0.8, text/turtle; q=0.6'

        _format = parse_accept_header(header)

        eq_(_format, None)


class TestDateIsoFormat(object):

    def test_empty(self):
        date = ''
        _date = parse_date_iso_format(date)
        eq_(_date, None)

    def test_date_command(self):
        date = 'Thu Sep 25 10:36:28 2020'
        _date = parse_date_iso_format(date)
        eq_(_date, '2020-09-25T10:36:28')

    def test_iso_datetime(self):
        date = '2020-02-27T21:26:01.123456'
        _date = parse_date_iso_format(date)
        eq_(_date, '2020-02-27T21:26:01.123456')

    def test_iso_date(self):
        date = '2020-09-25'
        _date = parse_date_iso_format(date)
        eq_(_date, '2020-09-25T00:00:00')

    def test_iso_datetime_stripped(self):
        date = '20200925T104941'
        _date = parse_date_iso_format(date)
        eq_(_date, '2020-09-25T10:49:41')

    def test_date_with_slash(self):
        date = '2020/09/25'
        _date = parse_date_iso_format(date)
        eq_(_date, '2020-09-25T00:00:00')
