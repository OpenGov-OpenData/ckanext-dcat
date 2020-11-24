import logging
import os
import re

import rdflib
import requests
from ckan import model
from ckan import plugins as p
from ckan.lib.helpers import json
from ckan.lib.munge import substitute_ascii_equivalents
from ckanext.dcat.harvesters.configuration_processors import (
    DefaultTags, CleanTags,
    DefaultGroups, DefaultExtras, DefaultValues,
    MappingFields, Publisher, ContactPoint,
    OrganizationFilter,
    ResourceFormatOrder,
    KeepExistingResources)
from ckanext.dcat.interfaces import IDCATRDFHarvester
from ckanext.harvest.harvesters import HarvesterBase
from ckanext.harvest.model import HarvestObject

log = logging.getLogger(__name__)


def _munge_to_length(string, min_length, max_length):
    '''Pad/truncates a string'''
    if len(string) < min_length:
        string += '_' * (min_length - len(string))
    if len(string) > max_length:
        string = string[:max_length]
    return string


def munge_tag(tag):
    tag = substitute_ascii_equivalents(tag)
    tag = tag.lower().strip()
    tag = re.sub(r'[^a-zA-Z0-9\- ]', '', tag)
    tag = _munge_to_length(tag, model.MIN_TAG_LENGTH, model.MAX_TAG_LENGTH)
    return tag


class DCATHarvester(HarvesterBase):
    MAX_FILE_SIZE = 1024 * 1024 * 50  # 50 Mb
    CHUNK_SIZE = 1024

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
        KeepExistingResources
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
            session = requests.Session()
            for harvester in p.PluginImplementations(IDCATRDFHarvester):
                session = harvester.update_session(session)

            # first we try a HEAD request which may not be supported
            did_get = False
            r = session.head(url)
            if r.status_code == 405 or r.status_code == 400:
                r = session.get(url, stream=True)
                did_get = True
            r.raise_for_status()

            cl = r.headers.get('content-length')
            if cl and int(cl) > self.MAX_FILE_SIZE:
                msg = '''Remote file is too big. Allowed
                    file size: {allowed}, Content-Length: {actual}.'''.format(
                    allowed=self.MAX_FILE_SIZE, actual=cl)
                self._save_gather_error(msg, harvest_job)
                return None, None

            if not did_get:
                r = session.get(url, stream=True)

            length = 0
            content = ''
            for chunk in r.iter_content(chunk_size=self.CHUNK_SIZE):
                content = content + chunk
                length += len(chunk)

                if length >= self.MAX_FILE_SIZE:
                    self._save_gather_error('Remote file is too big.',
                                            harvest_job)
                    return None, None

            if content_type is None and r.headers.get('content-type'):
                content_type = r.headers.get('content-type').split(";", 1)[0]

            return content, content_type

        except requests.exceptions.HTTPError, error:
            if page > 1 and error.response.status_code == 404:
                # We want to catch these ones later on
                raise

            msg = 'Could not get content from %s. Server responded with %s %s' \
                  % (url, error.response.status_code, error.response.reason)
            self._save_gather_error(msg, harvest_job)
            return None, None
        except requests.exceptions.ConnectionError, error:
            msg = '''Could not get content from %s because a
                                connection error occurred. %s''' % (url, error)
            self._save_gather_error(msg, harvest_job)
            return None, None
        except requests.exceptions.Timeout, error:
            msg = 'Could not get content from %s because the connection timed' \
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
            filter(HarvestObject.id == harvest_object_id). \
            first()
        if obj:
            return obj.source.url
        return None

    def _get_existing_dataset(self, guid):
        '''
        Checks if a dataset with a certain guid extra already exists

        Returns a dict as the ones returned by package_show
        '''

        datasets = model.Session.query(model.Package.id) \
                                .join(model.PackageExtra) \
                                .filter(model.PackageExtra.key == 'guid') \
                                .filter(model.PackageExtra.value == guid) \
                                .filter(model.Package.state == 'active') \
                                .all()

        if not datasets:
            return None
        elif len(datasets) > 1:
            log.error('Found more than one dataset with the same guid: {0}'
                      .format(guid))

        return p.toolkit.get_action('package_show')({}, {'id': datasets[0][0]})

    # Start hooks

    def modify_package_dict(self, package_dict, dcat_dict, harvest_object):
        '''
            Allows custom harvesters to modify the package dict before
            creating or updating the actual package.
        '''

        config_str = harvest_object.job.source.config
        self.config = json.loads(config_str) if config_str else {}

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

        config_obj = json.loads(config)

        # Processors validators could change config object. At least DefaultGroups
        for processor in self.config_processors:
            processor.check_config(config_obj)

        config = json.dumps(config_obj, indent=4)
        return config

    def _clean_tags(self, tags):
        try:
            def _update_tag(tag_dict, key, newvalue):
                # update the dict and return it
                tag_dict[key] = newvalue
                return tag_dict

            # assume it's in the package_show form                    
            tags = [_update_tag(t, 'name', munge_tag(t['name'])) for t in tags if munge_tag(t['name']) != '']

        except TypeError:  # a TypeError is raised if `t` above is a string
            # REST format: 'tags' is a list of strings
            tags = [munge_tag(t) for t in tags if munge_tag(t) != '']
            tags = list(set(tags))
            return tags

        return tags

    # End hooks
