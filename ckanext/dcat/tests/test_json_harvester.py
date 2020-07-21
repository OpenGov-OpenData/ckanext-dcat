import httpretty
from mock import call, patch, Mock

import nose

from ckan.logic import ValidationError
import ckantoolkit.tests.helpers as h

import ckan.tests.factories as factories

from ckanext.dcat.harvesters._json import copy_across_resource_ids, DCATJSONHarvester
from test_harvester import FunctionalHarvestTest

eq_ = nose.tools.eq_


class TestCopyAcrossResourceIds:
    def test_copied_because_same_uri(self):
        harvested_dataset = {'resources': [
            {'uri': 'http://abc', 'url': 'http://abc'}]}
        copy_across_resource_ids({'resources': [
            {'uri': 'http://abc', 'url': 'http://def', 'id': '1'}]},
            harvested_dataset,
        )
        eq_(harvested_dataset['resources'][0].get('id'), '1')
        eq_(harvested_dataset['resources'][0].get('url'), 'http://abc')

    def test_copied_because_same_url(self):
        harvested_dataset = {'resources': [
            {'url': 'http://abc'}]}
        copy_across_resource_ids({'resources': [
            {'url': 'http://abc', 'id': '1'}]},
            harvested_dataset,
        )
        eq_(harvested_dataset['resources'][0].get('id'), '1')

    def test_copied_with_same_url_and_changed_title(self):
        harvested_dataset = {'resources': [
            {'url': 'http://abc', 'title': 'link updated'}]}
        copy_across_resource_ids({'resources': [
            {'url': 'http://abc', 'title': 'link', 'id': '1'}]},
            harvested_dataset,
        )
        eq_(harvested_dataset['resources'][0].get('id'), '1')

    def test_copied_with_repeated_urls_but_unique_titles(self):
        harvested_dataset = {'resources': [
            {'url': 'http://abc', 'title': 'link1'},
            {'url': 'http://abc', 'title': 'link5'},
            {'url': 'http://abc', 'title': 'link3'},
            {'url': 'http://abc', 'title': 'link2'},
            {'url': 'http://abc', 'title': 'link4'},
            {'url': 'http://abc', 'title': 'link new'},
            ]}
        copy_across_resource_ids({'resources': [
            {'url': 'http://abc', 'title': 'link1', 'id': '1'},
            {'url': 'http://abc', 'title': 'link2', 'id': '2'},
            {'url': 'http://abc', 'title': 'link3', 'id': '3'},
            {'url': 'http://abc', 'title': 'link4', 'id': '4'},
            {'url': 'http://abc', 'title': 'link5', 'id': '5'},
            ]},
            harvested_dataset,
        )
        eq_([(r.get('id'), r['title']) for r in harvested_dataset['resources']],
            [('1', 'link1'), ('5', 'link5'), ('3', 'link3'), ('2', 'link2'),
             ('4', 'link4'), (None, 'link new')])

    def test_not_copied_because_completely_different(self):
        harvested_dataset = {'resources': [
            {'url': 'http://def', 'title': 'link other'}]}
        copy_across_resource_ids({'resources': [
            {'url': 'http://abc', 'title': 'link', 'id': '1'}]},
            harvested_dataset,
        )
        eq_(harvested_dataset['resources'][0].get('id'), None)
