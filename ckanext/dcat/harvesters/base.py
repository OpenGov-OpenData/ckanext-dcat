import os
import logging

import six
import requests
import rdflib

from ckan import plugins as p
from ckan import model

from ckantoolkit import config
import ckan.plugins.toolkit as toolkit

from ckanext.harvest.harvesters import HarvesterBase
from ckanext.harvest.model import HarvestObject

from ckanext.dcat.interfaces import IDCATRDFHarvester

from ckan.lib.helpers import json
from ckanext.dcat.configuration_processors import (
    DefaultTags, CleanTags,
    DefaultGroups, DefaultExtras, DefaultValues,
    MappingFields, Publisher, ContactPoint,
    OrganizationFilter,
    ResourceFormatOrder,
    KeepExistingResources,
    UploadToDatastore
)


log = logging.getLogger(__name__)


class DCATHarvester(HarvesterBase):

    DEFAULT_MAX_FILE_SIZE_MB = 50
    CHUNK_SIZE = 1024 * 512

    force_import = False

    config = None
    config_processors = [
        DefaultTags,
        CleanTags,
        DefaultGroups,
        DefaultExtras,
        DefaultValues,
        MappingFields,
        Publisher,
        ContactPoint,
        OrganizationFilter,
        ResourceFormatOrder,
        KeepExistingResources,
        UploadToDatastore
    ]

    def _get_content_and_type(self, url, harvest_job, page=1,
                              content_type=None):
        '''
        Gets the content and type of the given url.

        :param url: a web url (starting with http) or a local path
        :param harvest_job: the job, used for error reporting
        :param page: adds paging to the url
        :param content_type: will be returned as type
        :return: a tuple containing the content and content-type
        '''

        if not url.lower().startswith('http'):
            # Check local file
            if os.path.exists(url):
                with open(url, 'r') as f:
                    content = f.read()
                content_type = content_type or rdflib.util.guess_format(url)
                return content, content_type
            else:
                self._save_gather_error('Could not get content for this url',
                                        harvest_job)
                return None, None

        try:

            if page > 1:
                url = url + '&' if '?' in url else url + '?'
                url = url + 'page={0}'.format(page)

            log.debug('Getting file %s', url)

            # get the `requests` session object
            with requests.Session() as session:
                for harvester in p.PluginImplementations(IDCATRDFHarvester):
                    session = harvester.update_session(session)

                # first we try a HEAD request which may not be supported
                did_get = False
                r = session.head(url)

                if r.status_code == 405 or r.status_code == 400:
                    r = session.get(url, stream=True, timeout=30)
                    did_get = True
                r.raise_for_status()

                max_file_size = 1024 * 1024 * toolkit.asint(config.get('ckanext.dcat.max_file_size', self.DEFAULT_MAX_FILE_SIZE_MB))
                cl = r.headers.get('content-length')
                if cl and int(cl) > max_file_size:
                    msg = '''Remote file is too big. Allowed
                        file size: {allowed}, Content-Length: {actual}.'''.format(
                        allowed=max_file_size, actual=cl)
                    self._save_gather_error(msg, harvest_job)
                    return None, None

                if not did_get:
                    r = session.get(url, stream=True, timeout=30)

                length = 0
                content = '' if six.PY2 else b''
                for chunk in r.iter_content(chunk_size=self.CHUNK_SIZE):
                    content = content + chunk

                    length += len(chunk)

                    if length >= max_file_size:
                        self._save_gather_error('Remote file is too big.',
                                                harvest_job)
                        return None, None

                if not six.PY2:
                    content = content.decode('utf-8')

                if content_type is None and r.headers.get('content-type'):
                    content_type = r.headers.get('content-type').split(";", 1)[0]

                return content, content_type

        except requests.exceptions.HTTPError as error:
            if page > 1 and error.response.status_code == 404:
                # We want to catch these ones later on
                raise

            msg = 'Could not get content from %s. Server responded with %s %s'\
                % (url, error.response.status_code, error.response.reason)
            self._save_gather_error(msg, harvest_job)
            return None, None
        except requests.exceptions.ConnectionError as error:
            msg = '''Could not get content from %s because a
                                connection error occurred. %s''' % (url, error)
            self._save_gather_error(msg, harvest_job)
            return None, None
        except requests.exceptions.Timeout as error:
            msg = 'Could not get content from %s because the connection timed'\
                ' out.' % url
            self._save_gather_error(msg, harvest_job)
            return None, None

    def _get_object_extra(self, harvest_object, key):
        '''
        Helper function for retrieving the value from a harvest object extra,
        given the key
        '''
        for extra in harvest_object.extras:
            if extra.key == key:
                return extra.value
        return None

    def _get_package_name(self, harvest_object, title):

        package = harvest_object.package
        if package is None or package.title != title:
            name = self._gen_new_name(title)
            if not name:
                raise Exception(
                    'Could not generate a unique name from the title or the '
                    'GUID. Please choose a more unique title.')
        else:
            name = package.name

        return name

    def get_original_url(self, harvest_object_id):
        obj = model.Session.query(HarvestObject). \
            filter(HarvestObject.id == harvest_object_id).\
            first()
        if obj:
            return obj.source.url
        return None

    def _read_datasets_from_db(self, guid):
        '''
        Returns a database result of datasets matching the given guid.
        '''

        datasets = model.Session.query(model.Package.id) \
                                .join(model.PackageExtra) \
                                .filter(model.PackageExtra.key == 'guid') \
                                .filter(model.PackageExtra.value == guid) \
                                .filter(model.Package.state == 'active') \
                                .all()
        return datasets

    def _get_existing_dataset(self, guid):
        '''
        Checks if a dataset with a certain guid extra already exists

        Returns a dict as the ones returned by package_show
        '''

        datasets = self._read_datasets_from_db(guid)

        if not datasets:
            return None
        elif len(datasets) > 1:
            log.error('Found more than one dataset with the same guid: {0}'
                      .format(guid))

        return p.toolkit.get_action('package_show')({'ignore_auth': True}, {'id': datasets[0][0]})

    # Start hooks

    def modify_package_dict(self, package_dict, dcat_dict, harvest_object):
        '''
            Allows custom harvesters to modify the package dict before
            creating or updating the actual package.
        '''

        try:
            self._set_config(harvest_object.job.source.config)
        except:
            self._set_config('')

        # Modify package_dict using config_processors
        for processor in self.config_processors:
            processor.modify_package_dict(package_dict, self.config, dcat_dict)

        return package_dict

    def _set_config(self, config_str):
        if config_str:
            self.config = json.loads(config_str)
            log.debug('Using config: %r', self.config)
        else:
            self.config = {}

    def validate_config(self, config):
        if not config:
            return config

        try:
            config_obj = json.loads(config)

            # Validate harvest config using config_processors
            # Processor validators can change config object (i.e. DefaultGroups)
            for processor in self.config_processors:
                processor.check_config(config_obj)

            config = json.dumps(config_obj, indent=4)
        except ValueError as e:
            raise e

        return config

    # End hooks
