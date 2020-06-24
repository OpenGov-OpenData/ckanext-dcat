import json
import os
import uuid

import ckan.plugins as p
from ckan.lib import search
from ckan.tests import helpers, factories
from nose.tools import assert_equal

from ckanext.dcat.tests import DCATFunctionalTestBase


class TestDCat(DCATFunctionalTestBase):
    def setup(self):
        super(TestDCat, self).setup()
        if not p.plugin_loaded('dcat'):
            p.load('dcat')
        self.user = factories.Sysadmin(name='test-admin')
        self.org = factories.Organization(
            name='test-organisation',
            users=[{u'name': self.user['name'], u'capacity': u'admin'}]
        )

    def teardown(self):
        p.unload('dcat')
        helpers.reset_db()
        search.clear_all()

    def generate_dataset_data(self, name=None):
        if name is None:
            name = str(uuid.uuid4())
        dataset_data = {
            'id': name,
            'name': name,
            'user': self.user,
            'owner_org': self.org['id']
        }
        return dataset_data

    def generate_test_datasets(self):
        for _ in range(3):
            factories.Dataset(**self.generate_dataset_data(name="test_" + str(uuid.uuid4())))

    def test_dataset_creation(self):

        # Create bunch of test datasets to be able to test index position after reindex
        self.generate_test_datasets()

        # Load dataset with harvested metadata from fixtures
        fixtures_path = os.path.dirname(__file__)
        with open(os.path.join(fixtures_path, 'fixtures/dcat_json_harvested_dataset.json'), 'r') as f_file:
            dataset_data = json.load(f_file)

        # Prepare test database to create harvested dataset
        # Create user
        user = factories.Sysadmin(name='admin')
        # Create organization from fixture
        org = dataset_data['organization']
        factories.Organization(users=[{u'name': user['name'], u'capacity': u'admin'}], **org)

        context = {
            'user': user['name']
        }
        helpers.call_action('package_create', context=context, user=user, **dataset_data)

        # Add more test datasets to be to make harvest dataset be in a middle of search list
        self.generate_test_datasets()

        searched_packages = helpers.call_action('package_search')['results']

        harvest_dataset_pos = None
        for pos, package in enumerate(searched_packages):
            if package['name'] == dataset_data['name']:
                harvest_dataset_pos = pos

        # After package search harvested dataset should be in the end
        assert_equal(harvest_dataset_pos, 6)
