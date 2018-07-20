import json
import logging
from hashlib import sha1

from ckanext.dcat import converters
from ckanext.dcat.harvesters.base import DCATHarvester

log = logging.getLogger(__name__)


class DCATJSONHarvester(DCATHarvester):

    def info(self):
        return {
            'name': 'dcat_json',
            'title': 'DCAT JSON Harvester',
            'description': 'Harvester for DCAT dataset descriptions ' +
                           'serialized as JSON'
        }

    def _get_guids_and_datasets(self, content):

        doc = json.loads(content)

        # Filter in/out datasets from particular organizations
        org_filter_include = self.config.get('organizations_filter_include', [])
        org_filter_exclude = self.config.get('organizations_filter_exclude', [])

        if isinstance(doc, list):
            # Assume a list of datasets
            datasets = doc
        elif isinstance(doc, dict):
            datasets = doc.get('dataset', [])
        else:
            raise ValueError('Wrong JSON object')

        for dataset in datasets:

            # Get the organization name for the dataset
            dcat_publisher = dataset.get('publisher')
            if isinstance(dcat_publisher, basestring):
                dcat_publisher_name = dcat_publisher
            elif isinstance(dcat_publisher, dict) and dcat_publisher.get('name'):
                dcat_publisher_name = dcat_publisher.get('name')

            # Include/exclude dataset if from particular organizations
            if org_filter_include:
                if dcat_publisher_name not in org_filter_include:
                    continue
            elif org_filter_exclude:
                if dcat_publisher_name in org_filter_exclude:
                    continue

            as_string = json.dumps(dataset)

            # Get identifier
            guid = dataset.get('identifier')
            if not guid:
                # This is bad, any ideas welcomed
                guid = sha1(as_string).hexdigest()

            yield guid, as_string

    def _get_package_dict(self, harvest_object):

        content = harvest_object.content

        dcat_dict = json.loads(content)

        package_dict = converters.dcat_to_ckan(dcat_dict)

        return package_dict, dcat_dict
