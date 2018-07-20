import os
import uuid
import logging

import requests
import rdflib

from ckan import plugins as p
from ckan import logic
from ckan import model

from ckan.logic import ValidationError, NotFound, get_action
from ckan.lib.helpers import json

from ckanext.harvest.harvesters import HarvesterBase
from ckanext.harvest.model import HarvestObject, HarvestObjectExtra

from ckanext.dcat.interfaces import IDCATRDFHarvester


log = logging.getLogger(__name__)


class DCATHarvester(HarvesterBase):

    MAX_FILE_SIZE = 1024 * 1024 * 50  # 50 Mb
    CHUNK_SIZE = 1024

    force_import = False

    _user_name = None

    config = None

    def _get_content_and_type(self, url, harvest_job, page=1, content_type=None):
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
                self._save_gather_error('Could not get content for this url', harvest_job)
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
                    self._save_gather_error('Remote file is too big.', harvest_job)
                    return None, None

            if content_type is None and r.headers.get('content-type'):
                content_type = r.headers.get('content-type').split(";", 1)[0]

            return content, content_type

        except requests.exceptions.HTTPError, error:
            if page > 1 and error.response.status_code == 404:
                # We want to catch these ones later on
                raise

            msg = 'Could not get content from %s. Server responded with %s %s' % (
                url, error.response.status_code, error.response.reason)
            self._save_gather_error(msg, harvest_job)
            return None, None
        except requests.exceptions.ConnectionError, error:
            msg = '''Could not get content from %s because a
                                connection error occurred. %s''' % (url, error)
            self._save_gather_error(msg, harvest_job)
            return None, None
        except requests.exceptions.Timeout, error:
            msg = 'Could not get content from %s because the connection timed out.' % url
            self._save_gather_error(msg, harvest_job)
            return None, None

    def _get_user_name(self):
        if self._user_name:
            return self._user_name

        user = p.toolkit.get_action('get_site_user')(
            {'ignore_auth': True, 'defer_commit': True},
            {})
        self._user_name = user['name']

        return self._user_name

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
                raise Exception('Could not generate a unique name from the title or the GUID. Please choose a more unique title.')
        else:
            name = package.name

        return name

    def get_original_url(self, harvest_object_id):
        obj = model.Session.query(HarvestObject).\
                                    filter(HarvestObject.id==harvest_object_id).\
                                    first()
        if obj:
            return obj.source.url
        return None

    ## Start hooks

    def modify_package_dict(self, package_dict, dcat_dict, harvest_object):
        '''
            Allows custom harvesters to modify the package dict before
            creating or updating the actual package.
        '''
        tags_list = package_dict.get('tags')
        if tags_list:
            package_dict['tags'] = [tag for tag in tags_list if len(tag['name']) > 1]

        self._set_config(harvest_object.job.source.config)

        # Set default tags if needed
        default_tags = self.config.get('default_tags', [])
        if default_tags:
            if not 'tags' in package_dict:
                package_dict['tags'] = []
            package_dict['tags'].extend(
                [t for t in default_tags if t not in package_dict['tags']])

        # Set default groups if needed
        default_groups = self.config.get('default_groups', [])
        if default_groups:
            if not 'groups' in package_dict:
                package_dict['groups'] = []
            existing_group_ids = [g['id'] for g in package_dict['groups']]
            package_dict['groups'].extend(
                [{'name':g['name']} for g in self.config['default_group_dicts']
                 if g['id'] not in existing_group_ids])

        # set default values from config
        default_values = self.config.get('default_values',[])
        if default_values:
            for default_field in default_values:
                for key in default_field:
                    package_dict[key] = default_field[key]
                    # Remove from extras any keys present in the config
                    extras = [x for x in package_dict.get('extras',[]) if not (key == x.get('key'))]
                    package_dict['extras'] = extras

        # set the mapping fields its corresponding default_values
        map_fields = self.config.get('map_fields',[])
        if map_fields:
            for map_field in map_fields:
                source_field = map_field.get('source')
                target_field = map_field.get('target')
                default_value = map_field.get('default')
                package_dict[target_field] = dcat_dict.get(source_field, default_value)
                # Remove from extras any keys present in the config
                extras =  [x for x in package_dict.get('extras',[]) if not (target_field == x.get('key'))]
                package_dict['extras'] = extras

        # set the contact point
        contact_point_mapping = self.config.get('contact_point',[])
        if contact_point_mapping:
            contactPoint = dcat_dict.get('contactPoint',{})
            if contactPoint:
                contactPointName = contactPoint.get('fn')
                contactPointEmail = contactPoint.get('hasEmail',':').split(':')[1]
            for key in contact_point_mapping:
                if contact_point_mapping[key] and key == 'name_field':
                    package_dict[contact_point_mapping[key]] = contactPointName
                if contact_point_mapping[key] and key == 'email_field':
                    package_dict[contact_point_mapping[key]] = contactPointEmail

        # Set default extras if needed
        default_extras = self.config.get('default_extras', {})
        def get_extra(key, package_dict):
            for extra in package_dict.get('extras', []):
                if extra['key'] == key:
                    return extra
        if default_extras:
            override_extras = self.config.get('override_extras', False)
            if not 'extras' in package_dict:
                package_dict['extras'] = []
            for key, value in default_extras.iteritems():
                existing_extra = get_extra(key, package_dict)
                if existing_extra and not override_extras:
                    continue  # no need for the default
                if existing_extra:
                    package_dict['extras'].remove(existing_extra)

                package_dict['extras'].append({'key': key, 'value': value})

        return package_dict

    def _set_config(self, config_str):
        if config_str:
            self.config = json.loads(config_str)
            log.debug('Using config: %r', self.config)
        else:
            self.config = {}

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
                    raise ValueError('default_tags must be a list of '
                                     'dictionaries')

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

            if 'organizations_filter_include' in config_obj \
                and 'organizations_filter_exclude' in config_obj:
                raise ValueError('Harvest configuration cannot contain both '
                    'organizations_filter_include and organizations_filter_exclude')

        except ValueError, e:
            raise e

        return config

    ## End hooks

    def gather_stage(self,harvest_job):
        log.debug('In DCATHarvester gather_stage')

        ids = []

        # Get the previous guids for this source
        query = model.Session.query(HarvestObject.guid, HarvestObject.package_id).\
                                    filter(HarvestObject.current==True).\
                                    filter(HarvestObject.harvest_source_id==harvest_job.source.id)
        guid_to_package_id = {}

        for guid, package_id in query:
            guid_to_package_id[guid] = package_id

        guids_in_db = guid_to_package_id.keys()
        guids_in_source = []

        config = self._set_config(harvest_job.source.config)

        # Get file contents
        url = harvest_job.source.url

        previous_guids = []
        page = 1
        while True:

            try:
                content, content_type = self._get_content_and_type(url, harvest_job, page)
            except requests.exceptions.HTTPError, error:
                if error.response.status_code == 404:
                    if page > 1:
                        # Server returned a 404 after the first page, no more
                        # records
                        log.debug('404 after first page, no more pages')
                        break
                    else:
                        # Proper 404
                        msg = 'Could not get content. Server responded with 404 Not Found'
                        self._save_gather_error(msg, harvest_job)
                        return None
                else:
                    # This should never happen. Raising just in case.
                    raise

            if not content:
                return None


            try:

                batch_guids = []
                for guid, as_string in self._get_guids_and_datasets(content):

                    log.debug('Got identifier: {0}'.format(guid.encode('utf8')))
                    batch_guids.append(guid)

                    if guid not in previous_guids:

                        if guid in guids_in_db:
                            # Dataset needs to be updated
                            obj = HarvestObject(guid=guid, job=harvest_job,
                                            package_id=guid_to_package_id[guid],
                                            content=as_string,
                                            extras=[HarvestObjectExtra(key='status', value='change')])
                        else:
                            # Dataset needs to be created
                            obj = HarvestObject(guid=guid, job=harvest_job,
                                            content=as_string,
                                            extras=[HarvestObjectExtra(key='status', value='new')])
                        obj.save()
                        ids.append(obj.id)

                if len(batch_guids) > 0:
                    guids_in_source.extend(set(batch_guids) - set(previous_guids))
                else:
                    log.debug('Empty document, no more records')
                    # Empty document, no more ids
                    break

            except ValueError, e:
                msg = 'Error parsing file: {0}'.format(str(e))
                self._save_gather_error(msg, harvest_job)
                return None

            if sorted(previous_guids) == sorted(batch_guids):
                # Server does not support pagination or no more pages
                log.debug('Same content, no more pages')
                break


            page = page + 1

            previous_guids = batch_guids

        # Check datasets that need to be deleted
        guids_to_delete = set(guids_in_db) - set(guids_in_source)
        for guid in guids_to_delete:
            obj = HarvestObject(guid=guid, job=harvest_job,
                                package_id=guid_to_package_id[guid],
                                extras=[HarvestObjectExtra(key='status', value='delete')])
            model.Session.query(HarvestObject).\
                  filter_by(guid=guid).\
                  update({'current': False}, False)
            obj.save()
            ids.append(obj.id)


        return ids

    def fetch_stage(self,harvest_object):
        return True

    def import_stage(self,harvest_object):
        log.debug('In DCATHarvester import_stage')

        if not harvest_object:
            log.error('No harvest object received')
            return False

        if self.force_import:
            status = 'change'
        else:
            status = self._get_object_extra(harvest_object, 'status')

        if status == 'delete':
            # Delete package
            context = {'model': model, 'session': model.Session, 'user': self._get_user_name()}

            p.toolkit.get_action('package_delete')(context, {'id': harvest_object.package_id})
            log.info('Deleted package {0} with guid {1}'.format(harvest_object.package_id, harvest_object.guid))

            return True


        if harvest_object.content is None:
            self._save_object_error('Empty content for object %s' % harvest_object.id,harvest_object,'Import')
            return False

        # Get the last harvested object (if any)
        previous_object = model.Session.query(HarvestObject) \
                          .filter(HarvestObject.guid==harvest_object.guid) \
                          .filter(HarvestObject.current==True) \
                          .first()

        # Flag previous object as not current anymore
        if previous_object and not self.force_import:
            previous_object.current = False
            previous_object.add()


        package_dict, dcat_dict = self._get_package_dict(harvest_object)
        if not package_dict:
            return False

        if not package_dict.get('name'):
            package_dict['name'] = self._get_package_name(harvest_object, package_dict['title'])

        # copy across resource ids from the existing dataset, otherwise they'll
        # be recreated with new ids
        if status== 'change':
            existing_dataset = self._get_existing_dataset(harvest_object.guid)
            if existing_dataset:
                # check if resources already exist based on their URL
                existing_resources =  existing_dataset.get('resources')
                resource_mapping = {r.get('url'): r.get('id')
                                    for r in existing_resources}
                for resource in package_dict.get('resources'):
                    res_url = resource.get('url')
                    if res_url and res_url in resource_mapping:
                        resource['id'] = resource_mapping[res_url]

        # Allow custom harvesters to modify the package dict before creating
        # or updating the package
        package_dict = self.modify_package_dict(package_dict,
                                                dcat_dict,
                                                harvest_object)
        # Unless already set by an extension, get the owner organization (if any)
        # from the harvest source dataset
        if not package_dict.get('owner_org'):
            source_dataset = model.Package.get(harvest_object.source.id)
            if source_dataset.owner_org:
                package_dict['owner_org'] = source_dataset.owner_org

        # Flag this object as the current one
        harvest_object.current = True
        harvest_object.add()

        context = {
            'user': self._get_user_name(),
            'return_id_only': True,
            'ignore_auth': True,
        }

        if status == 'new':


            package_schema = logic.schema.default_create_package_schema()
            context['schema'] = package_schema

            # We need to explicitly provide a package ID
            package_dict['id'] = unicode(uuid.uuid4())
            package_schema['id'] = [unicode]

            # Save reference to the package on the object
            harvest_object.package_id = package_dict['id']
            harvest_object.add()

            # Defer constraints and flush so the dataset can be indexed with
            # the harvest object id (on the after_show hook from the harvester
            # plugin)
            model.Session.execute('SET CONSTRAINTS harvest_object_package_id_fkey DEFERRED')
            model.Session.flush()

            package_id = p.toolkit.get_action('package_create')(context, package_dict)
            log.info('Created dataset with id %s', package_id)
        elif status == 'change':

            package_dict['id'] = harvest_object.package_id
            package_id = p.toolkit.get_action('package_update')(context, package_dict)
            log.info('Updated dataset with id %s', package_id)

        model.Session.commit()

        return True
