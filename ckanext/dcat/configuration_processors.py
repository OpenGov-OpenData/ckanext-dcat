from builtins import str
from past.builtins import basestring
import re
import json

from abc import ABCMeta, abstractmethod
from collections import OrderedDict
from datetime import datetime

from ckan import model
from ckan import plugins as p
from ckan.lib.munge import substitute_ascii_equivalents
from ckan.logic import NotFound, get_action


def munge_to_length(string, min_length, max_length):
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
    tag = munge_to_length(tag, model.MIN_TAG_LENGTH, model.MAX_TAG_LENGTH)
    return tag


def get_extra(key, package_dict):
    for extra in package_dict.get('extras', []):
        if extra['key'] == key:
            return extra


class BaseConfigProcessor:
    __metaclass__ = ABCMeta

    @staticmethod
    @abstractmethod
    def check_config(config_obj):
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def modify_package_dict(package_dict, config, dcat_dict):
        raise NotImplementedError


class ParseID(BaseConfigProcessor):

    @staticmethod
    def check_config(config_obj):
        if 'parse_id_if_url' in config_obj:
            if not isinstance(config_obj['parse_id_if_url'], bool):
                raise ValueError('parse_id_if_url must be boolean')

    @staticmethod
    def modify_package_dict(package_dict, config, dcat_dict):
        pass


class DefaultTags(BaseConfigProcessor):

    @staticmethod
    def check_config(config_obj):
        if 'default_tags' in config_obj:
            if not isinstance(config_obj['default_tags'], list):
                raise ValueError('default_tags must be a list')
            if config_obj['default_tags'] and \
                    not isinstance(config_obj['default_tags'][0], dict):
                raise ValueError('default_tags must be a list of dictionaries')

    @staticmethod
    def modify_package_dict(package_dict, config, dcat_dict):
        # Set default tags if needed
        default_tags = config.get('default_tags', [])
        if default_tags:
            if 'tags' not in package_dict:
                package_dict['tags'] = []
            package_dict['tags'].extend(
                [t for t in default_tags if t not in package_dict['tags']])


class CleanTags(BaseConfigProcessor):

    @staticmethod
    def check_config(config_obj):
        if 'clean_tags' in config_obj:
            if not isinstance(config_obj['clean_tags'], bool):
                raise ValueError('clean_tags must be boolean')

    @staticmethod
    def modify_package_dict(package_dict, config, dcat_dict):
        if config.get('clean_tags', False):
            # clean tags of invalid characters
            tags = package_dict.get('tags', [])

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

            package_dict['tags'] = tags


class DefaultGroups(BaseConfigProcessor):

    @staticmethod
    def check_config(config_obj):
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
                    if 'users' in group:
                        del group['users']
                    # save the dict to the config object, as we'll need it
                    # in the import_stage of every dataset
                    config_obj['default_group_dicts'].append(group)
                except NotFound:
                    raise ValueError('Default group not found')

    @staticmethod
    def modify_package_dict(package_dict, config, dcat_dict):
        default_groups = config.get('default_groups', [])
        if default_groups:
            if 'groups' not in package_dict:
                package_dict['groups'] = []
            existing_group_ids = [g['id'] for g in package_dict['groups']]
            package_dict['groups'].extend(
                [{'name': g['name']} for g in config['default_group_dicts']
                 if g['id'] not in existing_group_ids])


class DefaultExtras(BaseConfigProcessor):

    @staticmethod
    def check_config(config_obj):
        if 'default_extras' in config_obj:
            if not isinstance(config_obj['default_extras'], dict):
                raise ValueError('default_extras must be a dictionary')

    @staticmethod
    def modify_package_dict(package_dict, config, dcat_dict):

        # Set default extras if needed
        default_extras = config.get('default_extras', {})

        def get_extra(key, package_dict):
            for extra in package_dict.get('extras', []):
                if extra['key'] == key:
                    return extra

        if not 'extras' in package_dict:
            package_dict['extras'] = []

        if default_extras:
            override_extras = config.get('override_extras', False)
            for key, value in default_extras.items():
                existing_extra = get_extra(key, package_dict)
                if existing_extra and not override_extras:
                    continue  # no need for the default
                if existing_extra:
                    package_dict['extras'].remove(existing_extra)

                package_dict['extras'].append({'key': key, 'value': value})


class DefaultValues(BaseConfigProcessor):

    @staticmethod
    def check_config(config_obj):
        if 'default_values' in config_obj:
            if not isinstance(config_obj['default_values'], list):
                raise ValueError('default_values must be a *list* of dictionaries')
            if config_obj['default_values'] and not isinstance(config_obj['default_values'][0], dict):
                raise ValueError('default_values must be a *list* of dictionaries')
            for default_field in config_obj.get('default_values', []):
                for key in default_field:
                    if key in ['id', 'name']:
                        raise ValueError('default_values cannot be used to modify dataset id/name')

    @staticmethod
    def modify_package_dict(package_dict, config, dcat_dict):
        # set default values from config
        default_values = config.get('default_values', [])
        if default_values:
            for default_field in default_values:
                for key in default_field:
                    package_dict[key] = default_field[key]
                    # Remove from extras any keys present in the config
                    existing_extra = get_extra(key, package_dict)
                    if existing_extra:
                        package_dict['extras'].remove(existing_extra)




class MappingFields(BaseConfigProcessor):

    @staticmethod
    def check_config(config_obj):
        if 'map_fields' in config_obj:
            if not isinstance(config_obj['map_fields'], list):
                raise ValueError('map_fields must be a *list* of dictionaries')
            if config_obj['map_fields'] and not isinstance(config_obj['map_fields'][0], dict):
                raise ValueError('map_fields must be a *list* of dictionaries')
            for map_field in config_obj.get('map_fields', []):
                if map_field.get('target', '') in ['id', 'name']:
                    raise ValueError('map_fields cannot be used to modify dataset id/name')

    @staticmethod
    def modify_package_dict(package_dict, config, dcat_dict):
        # Map fields from source to target
        map_fields = config.get('map_fields', [])
        if map_fields:
            for map_field in map_fields:
                source_field = map_field.get('source')
                target_field = map_field.get('target')
                default_value = map_field.get('default')

                value = dcat_dict.get(source_field) if dcat_dict.get(source_field) else default_value

                # If value is a list, convert to string
                if isinstance(value, list):
                    value = ', '.join(str(x) for x in value)

                # If configured convert timestamp to separate date and time formats
                if dcat_dict.get('issued'):
                    if map_field.get('source') == 'issued_date':
                        value = datetime.strptime(
                            dcat_dict.get('issued'),
                            '%Y-%m-%dT%H:%M:%S.%fZ'
                        ).strftime('%Y-%m-%d')
                    if map_field.get('source') == 'issued_time':
                        value = datetime.strptime(
                            dcat_dict.get('issued'),
                            '%Y-%m-%dT%H:%M:%S.%fZ'
                        ).strftime('%H:%M:%S.%fZ')

                if dcat_dict.get('modified'):
                    if map_field.get('source') == 'modified_date':
                        value = datetime.strptime(
                            dcat_dict.get('modified'),
                            '%Y-%m-%dT%H:%M:%S.%fZ'
                        ).strftime('%Y-%m-%d')
                    if map_field.get('source') == 'modified_time':
                        value = datetime.strptime(
                            dcat_dict.get('modified'),
                            '%Y-%m-%dT%H:%M:%S.%fZ'
                        ).strftime('%H:%M:%S.%fZ')

                # Map value to dataset field
                package_dict[target_field] = value

                # Remove from extras any keys present in the config
                existing_extra = get_extra(target_field, package_dict)
                if existing_extra:
                    package_dict['extras'].remove(existing_extra)


class CompositeMapping(BaseConfigProcessor):

    @staticmethod
    def check_config(config_obj):
        if 'composite_field_mapping' in config_obj:
            if not isinstance(config_obj['composite_field_mapping'], list):
                raise ValueError('composite_field_mapping must be a *list* of dictionaries')
            if config_obj['composite_field_mapping'] and not isinstance(config_obj['composite_field_mapping'][0], dict):
                raise ValueError('composite_field_mapping must be a *list* of dictionaries')
            try:
                schema_result = get_action('scheming_dataset_schema_show')({}, {'type': 'dataset'})
                dataset_schema = schema_result.get('dataset_fields')
            except:
                pass
            for composite_map in config_obj.get('composite_field_mapping', []):
                field_found = False
                field_name = list(composite_map)[0]
                for dataset_field in dataset_schema:
                    if dataset_field['field_name'] == field_name:
                        field_found = True
                        if dataset_field['preset'] != 'composite':
                            raise ValueError('The field {} must be a composite field'.format(field_name))
                if not field_found:
                    raise ValueError('The field {} was not found in the dataset schema'.format(field_name))

    @staticmethod
    def modify_package_dict(package_dict, config, dcat_dict):
        composite_mapping = config.get('composite_field_mapping', [])
        for composite_map in composite_mapping:
            field_name = list(composite_map)[0]
            value_dict = {}
            for subfield in list(composite_map.get(field_name)):
                mapped_field = composite_map.get(field_name).get(subfield)
                value_dict[subfield] = dcat_dict.get(mapped_field)
            package_dict[field_name] = json.dumps(value_dict, ensure_ascii=False)


class Publisher(BaseConfigProcessor):

    @staticmethod
    def check_config(config_obj):
        if 'publisher' in config_obj:
            if not isinstance(config_obj['publisher'], dict):
                raise ValueError('publisher must be a dictionary')
            if config_obj.get('publisher', {}).get('publisher_field', '') in ['id', 'name']:
                raise ValueError('publisher cannot be used to modify dataset id/name')

    @staticmethod
    def modify_package_dict(package_dict, config, dcat_dict):
        publisher_mapping = config.get('publisher', {})
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


class ContactPoint(BaseConfigProcessor):

    @staticmethod
    def check_config(config_obj):
        if 'contact_point' in config_obj:
            if not isinstance(config_obj['contact_point'], dict):
                raise ValueError('contact_point must be a dictionary')
            if config_obj.get('contact_point', {}).get('name_field', '') in ['id', 'name']:
                raise ValueError('contact_point name_field cannot be used to modify dataset id/name')
            if config_obj.get('contact_point', {}).get('email_field', '') in ['id', 'name']:
                raise ValueError('contact_point email_field cannot be used to modify dataset id/name')

    @staticmethod
    def modify_package_dict(package_dict, config, dcat_dict):
        # set the contact point
        contact_point_mapping = config.get('contact_point', {})
        name_field = contact_point_mapping.get('name_field')
        email_field = contact_point_mapping.get('email_field')
        contactPoint = dcat_dict.get('contactPoint', {})

        if name_field:
            contactPointName = contactPoint.get('fn') or \
                               contact_point_mapping.get('default_name')
            package_dict[name_field] = contactPointName
            # Remove from extras the name field
            existing_extra = get_extra(name_field, package_dict)
            if existing_extra:
                package_dict['extras'].remove(existing_extra)

        if email_field:
            contactPointEmail = contactPoint.get('hasEmail', ':').split(':')[-1] or \
                                contact_point_mapping.get('default_email')
            package_dict[email_field] = contactPointEmail
            # Remove from extras the email field
            existing_extra = get_extra(email_field, package_dict)
            if existing_extra:
                package_dict['extras'].remove(existing_extra)


class OrganizationFilter(BaseConfigProcessor):

    @staticmethod
    def check_config(config_obj):
        if 'organizations_filter_include' in config_obj \
                and 'organizations_filter_exclude' in config_obj:
            raise ValueError('Harvest configuration cannot contain both '
                             'organizations_filter_include and organizations_filter_exclude')

    @staticmethod
    def modify_package_dict(package_dict, config, dcat_dict):
        pass


class ResourceFormatOrder(BaseConfigProcessor):

    @staticmethod
    def check_config(config_obj):
        if 'resource_format_order' in config_obj:
            if not isinstance(config_obj['resource_format_order'], list):
                raise ValueError('Resource format order should be provided as a list of strings')

    @staticmethod
    def modify_package_dict(package_dict, config_obj, dcat_dict):
        resource_order = config_obj.get('resource_format_order')
        if not resource_order:
            return package_dict
        resource_order = [res_format.strip().lower() for res_format in resource_order]

        # create OrderedDict to group resources by format
        result = OrderedDict([(res_format, []) for res_format in resource_order])
        result['unspecified_format'] = []

        for resource in package_dict['resources']:
            res_format = resource.get('format', '').strip().lower()
            if res_format not in resource_order:
                result['unspecified_format'].append(resource)
                continue
            result[res_format].append(resource)

        # add resources by format order, unspecified formats appear at the end
        package_dict['resources'] = []
        for val in result.values():
            package_dict['resources'] += val


class KeepExistingResources(BaseConfigProcessor):

    @staticmethod
    def check_config(config_obj):
        if 'keep_existing_resources' in config_obj:
            if not isinstance(config_obj.get('keep_existing_resources'), bool):
                raise ValueError('keep_existing_resources must be boolean')

    @staticmethod
    def modify_package_dict(package_dict, config, dcat_dict):
        pass


class UploadToDatastore(BaseConfigProcessor):

    @staticmethod
    def check_config(config_obj):
        if 'upload_to_datastore' in config_obj:
            if not isinstance(config_obj.get('upload_to_datastore'), bool):
                raise ValueError('upload_to_datastore must be boolean')

    @staticmethod
    def modify_package_dict(package_dict, config, dcat_dict):
        pass
