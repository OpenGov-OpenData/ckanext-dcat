from builtins import str
from past.builtins import basestring
import json
import logging
from hashlib import sha1
import traceback
import uuid

import requests
import sqlalchemy as sa

from ckan import model
from ckan import logic
from ckan import plugins as p
from ckanext.harvest.model import HarvestObject, HarvestObjectExtra
from ckanext.harvest.logic.schema import unicode_safe
from ckanext.dcat import converters
from ckanext.dcat import utils
from ckanext.dcat.harvesters.base import DCATHarvester
from ckanext.dcat.exceptions import JSONDecodeErrorContext

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

        try:
            doc = json.loads(content)
        except json.JSONDecodeError as e:
            # Raise custom exception which adds context
            raise JSONDecodeErrorContext(e.msg, e.doc, e.pos) from e

        if isinstance(doc, list):
            # Assume a list of datasets
            datasets = doc
        elif isinstance(doc, dict):
            datasets = doc.get('dataset', [])
        else:
            raise ValueError('Wrong JSON object')

        # Filter datasets from particular organizations
        org_filter_include = self.config.get('organizations_filter_include', [])
        org_filter_exclude = self.config.get('organizations_filter_exclude', [])

        # Filter datasets with particular formats
        format_filter_exclude = self.config.get('format_filter_exclude', [])
        format_filter_include = self.config.get('format_filter_include', [])

        # Filter datasets with particular tags
        tag_filter_exclude = self.config.get('tag_filter_exclude', [])
        tag_filter_include = self.config.get('tag_filter_include', [])

        for dataset in datasets:
            # Get the organization name for the dataset
            dcat_publisher = dataset.get('publisher')
            if isinstance(dcat_publisher, basestring):
                dcat_publisher_name = dcat_publisher
            elif isinstance(dcat_publisher, dict) and dcat_publisher.get('name'):
                dcat_publisher_name = dcat_publisher.get('name')
            elif isinstance(dcat_publisher, dict) and dcat_publisher.get('source'):
                dcat_publisher_name = dcat_publisher.get('source')
            else:
                dcat_publisher_name = ''

            # Include/exclude dataset if from particular organizations
            if org_filter_include:
                if dcat_publisher_name not in org_filter_include:
                    continue
            elif org_filter_exclude:
                if dcat_publisher_name in org_filter_exclude:
                    continue

            # Exclude/include dataset based on particular formats
            if format_filter_exclude or format_filter_include:
                resource_formats = [
                    dist.get('format', '').lower()
                    for dist in dataset.get('distribution', [])
                    if dist.get('format')
                ]
            if format_filter_exclude:
                if any(fmt in resource_formats for fmt in format_filter_exclude):
                    continue
            if format_filter_include:
                if not any(fmt in resource_formats for fmt in format_filter_include):
                    continue

            # Exclude/include dataset based on particular tags
            if tag_filter_exclude:
                if any(tag in dataset.get('keyword', []) for tag in tag_filter_exclude):
                    continue
            if tag_filter_include:
                if not any(tag in dataset.get('keyword', []) for tag in tag_filter_include):
                    continue

            as_string = json.dumps(dataset)

            # Get identifier
            guid = dataset.get('identifier')
            if not guid:
                # This is bad, any ideas welcomed
                guid = sha1(as_string.encode('utf-8')).hexdigest()

            if self.config.get('parse_id_if_url'):
                # Get id from identifier if it is a url
                guid = utils.parse_identifier(dataset.get('identifier'))

            yield guid, as_string

    def _get_package_dict(self, harvest_object):

        content = harvest_object.content

        dcat_dict = json.loads(content)

        package_dict = converters.dcat_to_ckan(dcat_dict)

        return package_dict, dcat_dict

    def gather_stage(self, harvest_job):
        log.debug('In DCATJSONHarvester gather_stage')

        ids = []

        # Get the previous guids for this source
        query = \
            model.Session.query(HarvestObject.guid, HarvestObject.package_id) \
            .filter(HarvestObject.current == True) \
            .filter(HarvestObject.harvest_source_id == harvest_job.source.id)
        guid_to_package_id = {}

        for guid, package_id in query:
            guid_to_package_id[guid] = package_id

        guids_in_db = list(guid_to_package_id.keys())
        guids_in_source = []

        self._set_config(harvest_job.source.config)

        # Get file contents
        url = harvest_job.source.url

        previous_guids = []
        page = 1
        while True:

            try:
                content, content_type = \
                    self._get_content_and_type(url, harvest_job, page)
            except requests.exceptions.HTTPError as error:
                if error.response.status_code == 404:
                    if page > 1:
                        # Server returned a 404 after the first page, no more
                        # records
                        log.debug('404 after first page, no more pages')
                        break
                    else:
                        # Proper 404
                        msg = 'Could not get content. Server responded with ' \
                            '404 Not Found'
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

                    log.debug('Got identifier: {0}'
                              .format(guid.encode('utf8')))
                    batch_guids.append(guid)

                    if guid not in previous_guids:

                        if guid in guids_in_db:
                            # Dataset needs to be udpated
                            obj = HarvestObject(
                                guid=guid, job=harvest_job,
                                package_id=guid_to_package_id[guid],
                                content=as_string,
                                extras=[HarvestObjectExtra(key='status',
                                                           value='change')])
                        else:
                            # Dataset needs to be created
                            obj = HarvestObject(
                                guid=guid, job=harvest_job,
                                content=as_string,
                                extras=[HarvestObjectExtra(key='status',
                                                           value='new')])
                        obj.save()
                        ids.append(obj.id)

                if len(batch_guids) > 0:
                    guids_in_source.extend(set(batch_guids)
                                           - set(previous_guids))
                else:
                    log.debug('Empty document, no more records')
                    # Empty document, no more ids
                    break

            except ValueError as e:
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
            obj = HarvestObject(
                guid=guid, job=harvest_job,
                package_id=guid_to_package_id[guid],
                extras=[HarvestObjectExtra(key='status', value='delete')])
            ids.append(obj.id)
            model.Session.query(HarvestObject).\
                filter_by(guid=guid).\
                update({'current': False}, False)
            obj.save()

            # Rename package before delete so that its url can be reused
            context = {'model': model, 'session': model.Session,
                       'user': self._get_user_name()}
            p.toolkit.get_action('package_patch')(context, {
                'id': guid_to_package_id[guid],
                'name': guid_to_package_id[guid] + '-deleted'
            })

        return ids

    def fetch_stage(self, harvest_object):
        return True

    def import_stage(self, harvest_object):
        log.debug('In DCATJSONHarvester import_stage')
        if not harvest_object:
            log.error('No harvest object received')
            return False

        try:
            self._set_config(harvest_object.job.source.config)
        except:
            self._set_config('')

        if self.force_import:
            status = 'change'
        else:
            status = self._get_object_extra(harvest_object, 'status')

        if status == 'delete':
            # Delete package
            context = {'model': model, 'session': model.Session,
                       'user': self._get_user_name()}

            p.toolkit.get_action('package_delete')(
                context, {'id': harvest_object.package_id})
            log.info('Deleted package {0} with guid {1}'
                     .format(harvest_object.package_id, harvest_object.guid))

            return True

        if harvest_object.content is None:
            self._save_object_error(
                'Empty content for object %s' % harvest_object.id,
                harvest_object, 'Import')
            return False

        # Get the last harvested object (if any)
        previous_object = model.Session.query(HarvestObject) \
            .filter(HarvestObject.guid == harvest_object.guid) \
            .filter(HarvestObject.current == True) \
            .first()

        # Flag previous object as not current anymore
        if previous_object and not self.force_import:
            previous_object.current = False
            previous_object.add()

        package_dict, dcat_dict = self._get_package_dict(harvest_object)
        if not package_dict:
            return False

        if not package_dict.get('name'):
            package_dict['name'] = \
                self._get_package_name(harvest_object, package_dict['title'])

        # copy across resource ids from the existing dataset, otherwise they'll
        # be recreated with new ids
        if status == 'change':
            existing_dataset = self._get_existing_dataset(harvest_object.guid)
            if existing_dataset:
                copy_across_resource_ids(existing_dataset, package_dict, self.config)

        # Allow custom harvesters to modify the package dict before creating
        # or updating the package
        package_dict = self.modify_package_dict(package_dict,
                                                dcat_dict,
                                                harvest_object)
        # Unless already set by an extension, get the owner organization (if
        # any) from the harvest source dataset
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

        try:
            if status == 'new':
                package_schema = logic.schema.default_create_package_schema()
                context['schema'] = package_schema

                # We need to explicitly provide a package ID
                package_dict['id'] = str(uuid.uuid4())
                package_schema['id'] = [unicode_safe]

                # Save reference to the package on the object
                harvest_object.package_id = package_dict['id']
                harvest_object.add()

                # Defer constraints and flush so the dataset can be indexed with
                # the harvest object id (on the after_show hook from the harvester
                # plugin)
                model.Session.execute(
                    sa.text('SET CONSTRAINTS harvest_object_package_id_fkey DEFERRED')
                )
                model.Session.flush()

            elif status == 'change':
                package_dict['id'] = harvest_object.package_id

            if status in ['new', 'change']:
                action = 'package_create' if status == 'new' else 'package_update'
                message_status = 'Created' if status == 'new' else 'Updated'

                package_id = p.toolkit.get_action(action)(context, package_dict)
                log.info('%s dataset with id %s', message_status, package_id)

                # Upload tabular resources to datastore
                upload_to_datastore = self.config.get('upload_to_datastore', True)
                if upload_to_datastore:
                    if status == 'new':
                        new_package_dict = p.toolkit.get_action('package_show')(context, {'id': package_id})
                        upload_resources_to_datastore(context, new_package_dict, dcat_dict)
                    if status == 'change':
                        # Submit to xloader if dcat_modified date is different since resource urls may not change
                        dcat_modified_changed = utils.is_dcat_modified_field_changed(existing_dataset, package_dict)
                        if dcat_modified_changed:
                            upload_resources_to_datastore(context, package_dict, dcat_dict)

        except Exception as e:
            dataset = json.loads(harvest_object.content)
            dataset_name = dataset.get('name', '')

            self._save_object_error('Error importing dataset %s: %r / %s' % (dataset_name, e, traceback.format_exc()), harvest_object, 'Import')
            return False

        finally:
            model.Session.commit()

        return True

def copy_across_resource_ids(existing_dataset, harvested_dataset, config=None):
    '''Compare the resources in a dataset existing in the CKAN database with
    the resources in a freshly harvested copy, and for any resources that are
    the same, copy the resource ID into the harvested_dataset dict.
    '''
    # take a copy of the existing_resources so we can remove them when they are
    # matched - we don't want to match them more than once.
    existing_resources_still_to_match = \
        [r for r in existing_dataset.get('resources')]

    # we match resources a number of ways. we'll compute an 'identity' of a
    # resource in both datasets and see if they match.
    # start with the surest way of identifying a resource, before reverting
    # to closest matches.
    resource_identity_functions = [
        lambda r: r['uri'],  # URI is best
        lambda r: (r['url'], r['title'], r['format']),
        lambda r: (r['url'], r['title']),
        lambda r: r['url'],  # same URL is fine if nothing else matches
    ]

    datastore_fields = [
        'datastore_active',
        'datastore_contains_all_records_of_source_file'
    ]

    for resource_identity_function in resource_identity_functions:
        # calculate the identities of the existing_resources
        existing_resource_identities = {}
        for r in existing_resources_still_to_match:
            try:
                identity = resource_identity_function(r)
                existing_resource_identities[identity] = r
            except KeyError:
                pass

        # calculate the identities of the harvested_resources
        for resource in harvested_dataset.get('resources'):
            try:
                identity = resource_identity_function(resource)
            except KeyError:
                identity = None
            if identity and identity in existing_resource_identities:
                # we got a match with the existing_resources - copy the id
                matching_existing_resource = \
                    existing_resource_identities[identity]
                resource['id'] = matching_existing_resource['id']
                # copy datastore specific fields
                for field in datastore_fields:
                    if matching_existing_resource.get(field):
                        resource[field] = matching_existing_resource.get(field)
                # make sure we don't match this existing_resource again
                del existing_resource_identities[identity]
                existing_resources_still_to_match.remove(
                    matching_existing_resource)
        if not existing_resources_still_to_match:
            break

    # If configured add rest of existing resources to harvested dataset
    try:
        keep_existing_resources = config.get('keep_existing_resources', False)
        if keep_existing_resources and harvested_dataset.get('resources'):
            for existing_resource in existing_resources_still_to_match:
                if existing_resource.get('url'):
                    harvested_dataset['resources'].append(existing_resource)
    except Exception:
        pass
    if 'private' in existing_dataset.keys():
        harvested_dataset['private'] = existing_dataset['private']

def upload_resources_to_datastore(context, package_dict, dcat_dict):
    for resource in package_dict.get('resources'):
        if utils.is_xloader_format(resource.get('format')) and resource.get('id'):
            # Get data dictionary if available and push to datastore
            push_data_dictionary(context, resource, dcat_dict.get('distribution', []))

            # Submit the resource to be pushed to the datastore
            try:
                log.info('Submitting harvested resource {0} to be xloadered'.format(resource.get('id')))
                xloader_dict = {
                    'resource_id': resource.get('id'),
                    'ignore_hash': False
                }
                p.toolkit.get_action('xloader_submit')(context, xloader_dict)
            except p.toolkit.ValidationError as e:
                log.debug(e)
                pass

def push_data_dictionary(context, resource, distribution):
    # Check for resource's data dictionary in the distribution
    fields = []
    for dist in distribution:
        if ((dist.get('downloadURL') == resource.get('url') or dist.get('accessURL') == resource.get('url'))
                and dist.get('title') == resource.get('name')
                and 'action/datastore_search' in dist.get('describedBy', '')):
            try:
                datastore_response = requests.get(dist.get('describedBy'), timeout=90)
                data = datastore_response.json()
                result = data.get('result', {})
                fields = result.get('fields', [])
                if len(fields) > 0 and fields[0].get('id') == '_id':
                    del fields[0]  # Remove the first dictionary which is only for ckan row number
                break
            except Exception as e:
                log.debug(e)
                pass
    # If fields are defined push the data dictionary to datastore
    if fields:
        log.info('Pushing data dictionary for resource '.format(resource.get('id')))
        try:
            datastore_dict = {
                'resource_id': resource.get('id'),
                'fields': fields,
                'force': True
            }
            p.toolkit.get_action('datastore_create')(context, datastore_dict)
        except p.toolkit.ValidationError as e:
            log.debug(e)
            pass
