import os
import logging

import six
import requests
import rdflib

from ckan import plugins as p
from ckan import model

from ckan.logic import ValidationError, NotFound, get_action
from ckan.lib.helpers import json

from ckanext.harvest.harvesters import HarvesterBase
from ckanext.harvest.model import HarvestObject

from ckanext.dcat.interfaces import IDCATRDFHarvester

if p.toolkit.check_ckan_version(min_version='2.3'):
    from ckan.lib.munge import munge_tag
else:
    # Fallback munge_tag for older ckan versions which don't have a decent
    # munger
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
        tag = re.sub(r'[^a-zA-Z0-9\- ]', '', tag).replace(' ', '-')
        tag = _munge_to_length(tag, model.MIN_TAG_LENGTH, model.MAX_TAG_LENGTH)
        return tag

log = logging.getLogger(__name__)


class DCATHarvester(HarvesterBase):

    MAX_FILE_SIZE = 1024 * 1024 * 50  # 50 Mb
    CHUNK_SIZE = 1024

    force_import = False

    config = None

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
                if six.PY2:
                    content = content + chunk
                else:
                    content = content + chunk.decode('utf8')

                length += len(chunk)

                if length >= self.MAX_FILE_SIZE:
                    self._save_gather_error('Remote file is too big.',
                                            harvest_job)
                    return None, None

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

        return p.toolkit.get_action('package_show')({}, {'id': datasets[0][0]})

    # Start hooks

    def modify_package_dict(self, package_dict, dcat_dict, harvest_object):
        '''
            Allows custom harvesters to modify the package dict before
            creating or updating the actual package.
        '''

        self._set_config(harvest_object.job.source.config)

        # Set default tags if needed
        default_tags = self.config.get('default_tags', [])
        if default_tags:
            if not 'tags' in package_dict:
                package_dict['tags'] = []
            package_dict['tags'].extend(
                [t for t in default_tags if t not in package_dict['tags']])

        # clean tags of invalid characters
        tags = package_dict.get('tags', [])
        package_dict['tags'] = self._clean_tags(tags)

        # Set default groups if needed
        default_groups = self.config.get('default_groups', [])
        if default_groups:
            if not 'groups' in package_dict:
                package_dict['groups'] = []
            existing_group_ids = [g['id'] for g in package_dict['groups']]
            package_dict['groups'].extend(
                [{'name':g['name']} for g in self.config['default_group_dicts']
                 if g['id'] not in existing_group_ids])

        # Set default extras if needed
        default_extras = self.config.get('default_extras', {})
        def get_extra(key, package_dict):
            for extra in package_dict.get('extras', []):
                if extra['key'] == key:
                    return extra

        if not 'extras' in package_dict:
            package_dict['extras'] = []

        if default_extras:
            override_extras = self.config.get('override_extras', False)
            for key, value in default_extras.iteritems():
                existing_extra = get_extra(key, package_dict)
                if existing_extra and not override_extras:
                    continue  # no need for the default
                if existing_extra:
                    package_dict['extras'].remove(existing_extra)

                package_dict['extras'].append({'key': key, 'value': value})

        # set default values from config
        default_values = self.config.get('default_values', [])
        if default_values:
            for default_field in default_values:
                for key in default_field:
                    package_dict[key] = default_field[key]
                    # Remove from extras any keys present in the config
                    existing_extra = get_extra(key, package_dict)
                    if existing_extra:
                        package_dict['extras'].remove(existing_extra)

        # set the mapping fields its corresponding default_values
        map_fields = self.config.get('map_fields', [])
        if map_fields:
            for map_field in map_fields:
                source_field = map_field.get('source')
                target_field = map_field.get('target')
                default_value = map_field.get('default')
                value = dcat_dict.get(source_field, default_value)
                # If value is a list, convert to string
                if isinstance(value, list):
                    value = ', '.join(str(x) for x in value)
                package_dict[target_field] = value
                # Remove from extras any keys present in the config
                existing_extra = get_extra(target_field, package_dict)
                if existing_extra:
                    package_dict['extras'].remove(existing_extra)

        # set the publisher
        publisher_mapping = self.config.get('publisher', {})
        publisher_field = publisher_mapping.get('publisher_field')
        if publisher_field:
            publisher = dcat_dict.get('publisher', {})
            publisher_name = publisher.get('name') or \
                             publisher_mapping.get('default_publisher')
            package_dict[publisher_field] = publisher_name
            # Remove from extras any keys present in the config
            existing_extra = get_extra(publisher_field, package_dict)
            if existing_extra:
                package_dict['extras'].remove(existing_extra)

        # set the contact point
        contact_point_mapping = self.config.get('contact_point', {})
        name_field = contact_point_mapping.get('name_field')
        email_field = contact_point_mapping.get('email_field')
        contactPoint = dcat_dict.get('contactPoint',{})

        if name_field:
            contactPointName = contactPoint.get('fn') or \
                               contact_point_mapping.get('default_name')
            package_dict[name_field] = contactPointName
            # Remove from extras the name field
            existing_extra = get_extra(name_field, package_dict)
            if existing_extra:
                package_dict['extras'].remove(existing_extra)

        if email_field:
            contactPointEmail = contactPoint.get('hasEmail', ':').split(':')[1] or \
                                contact_point_mapping.get('default_email')
            package_dict[email_field] = contactPointEmail
            # Remove from extras the email field
            existing_extra = get_extra(email_field, package_dict)
            if existing_extra:
                package_dict['extras'].remove(existing_extra)

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

            if 'default_tags' in config_obj:
                if not isinstance(config_obj['default_tags'], list):
                    raise ValueError('default_tags must be a list')
                if config_obj['default_tags'] and \
                        not isinstance(config_obj['default_tags'][0], dict):
                    raise ValueError('default_tags must be a list of dictionaries')

            if 'default_groups' in config_obj:
                if not isinstance(config_obj['default_groups'], list):
                    raise ValueError('default_groups must be a *list* of group names/ids')
                if config_obj['default_groups'] and not isinstance(config_obj['default_groups'][0], basestring):
                    raise ValueError('default_groups must be a list of group names/ids (i.e. strings)')

                # Check if default groups exist
                context = {'model': model, 'user': p.toolkit.c.user}
                config_obj['default_group_dicts'] = []
                for group_name_or_id in config_obj['default_groups']:
                    try:
                        group = get_action('group_show')(context, {'id': group_name_or_id})
                        # save the dict to the config object, as we'll need it
                        # in the import_stage of every dataset
                        config_obj['default_group_dicts'].append(group)
                    except NotFound, e:
                        raise ValueError('Default group not found')
                config = json.dumps(config_obj)

            if 'default_extras' in config_obj:
                if not isinstance(config_obj['default_extras'], dict):
                    raise ValueError('default_extras must be a dictionary')

            if 'default_values' in config_obj:
                if not isinstance(config_obj['default_values'], list):
                    raise ValueError('default_values must be a *list* of dictionaries')
                if config_obj['default_values'] and not isinstance(config_obj['default_values'][0], dict):
                    raise ValueError('default_values must be a *list* of dictionaries')

            if 'map_fields' in config_obj:
                if not isinstance(config_obj['map_fields'], list):
                    raise ValueError('map_fields must be a *list* of dictionaries')
                if config_obj['map_fields'] and not isinstance(config_obj['map_fields'][0], dict):
                    raise ValueError('map_fields must be a *list* of dictionaries')

            if 'publisher' in config_obj:
                if not isinstance(config_obj['publisher'], dict):
                    raise ValueError('publisher must be a dictionary')

            if 'contact_point' in config_obj:
                if not isinstance(config_obj['contact_point'], dict):
                    raise ValueError('contact_point must be a dictionary')

            if 'organizations_filter_include' in config_obj \
                and 'organizations_filter_exclude' in config_obj:
                raise ValueError('Harvest configuration cannot contain both '
                    'organizations_filter_include and organizations_filter_exclude')

        except ValueError, e:
            raise e

        return config

    def _clean_tags(self, tags):
        try:
            def _update_tag(tag_dict, key, newvalue):
                # update the dict and return it
                tag_dict[key] = newvalue
                return tag_dict

            # assume it's in the package_show form                    
            tags = [_update_tag(t, 'name', munge_tag(t['name'])) for t in tags if munge_tag(t['name']) != '']

        except TypeError: # a TypeError is raised if `t` above is a string
           # REST format: 'tags' is a list of strings
           tags = [munge_tag(t) for t in tags if munge_tag(t) != '']
           tags = list(set(tags))
           return tags

        return tags

    # End hooks
