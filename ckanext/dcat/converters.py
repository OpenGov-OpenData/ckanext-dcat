from past.builtins import basestring
import json
import logging
import mimetypes
import six
from ckan.common import config
from ckan.plugins import toolkit


log = logging.getLogger(__name__)
mimetypes.init()


def dcat_to_ckan(dcat_dict):

    package_dict = {}

    package_dict['title'] = dcat_dict.get('title')
    package_dict['notes'] = dcat_dict.get('description', '')
    package_dict['url'] = dcat_dict.get('landingPage')

    if 'fluent' in config.get('ckan.plugins'):
        package_dict['title_translated'] = {'en': dcat_dict.get('title')}
        package_dict['notes_translated'] = {'en': dcat_dict.get('description', '') or ''}

    package_dict['tags'] = []
    for keyword in dcat_dict.get('keyword', []):
        package_dict['tags'].append({'name': keyword})

    package_dict['extras'] = []
    for key in ['issued', 'modified']:
        package_dict['extras'].append({'key': 'dcat_{0}'.format(key), 'value': dcat_dict.get(key)})

    package_dict['extras'].append({'key': 'guid', 'value': dcat_dict.get('identifier')})

    dcat_publisher = dcat_dict.get('publisher')
    if isinstance(dcat_publisher, basestring):
        package_dict['extras'].append({'key': 'dcat_publisher_name', 'value': dcat_publisher})
    elif isinstance(dcat_publisher, dict) and dcat_publisher.get('name'):
        package_dict['extras'].append({'key': 'dcat_publisher_name', 'value': dcat_publisher.get('name')})
        package_dict['extras'].append({'key': 'dcat_publisher_email', 'value': dcat_publisher.get('mbox')})
    elif isinstance(dcat_publisher, dict) and dcat_publisher.get('source'):
        package_dict['extras'].append({'key': 'dcat_publisher_name', 'value': dcat_publisher.get('source')})

    bbox_geojson = get_bbox_geojson(dcat_dict.get('spatial'))
    if bbox_geojson:
        package_dict['extras'].append({"key": "spatial", "value": bbox_geojson})

    #package_dict['extras'].append({
    #    'key': 'language',
    #    'value': ','.join(dcat_dict.get('language', []))
    #})

    if dcat_dict.get('license'):
        for license in toolkit.get_action('license_list')({}, {}):
            if license.get('url') == dcat_dict.get('license'):
                package_dict['license_id'] = license.get('id')
                break
            elif license.get('title') == dcat_dict.get('license'):
                package_dict['license_id'] = license.get('id')
                break

    package_dict['resources'] = []
    for distribution in dcat_dict.get('distribution', []):
        # Guess format if not present
        format = ''
        if distribution.get('format'):
            format = distribution.get('format')
        elif distribution.get('mediaType'):
            ext = mimetypes.guess_extension(distribution.get('mediaType'))
            if ext:
                format = ext[1:]

        # skip disallowed formats
        clean_format = ''.join(format.split()).lower()
        if disallow_file_format(clean_format):
            log.debug('Skip disallowed format %s: %s' % (
                format, distribution.get('downloadURL') or distribution.get('accessURL'))
            )
            continue

        resource = {
            'name': distribution.get('title', dcat_dict.get('title')),
            'description': distribution.get('description', ''),
            'url': distribution.get('downloadURL') or distribution.get('accessURL'),
            'format': format,
        }

        if 'fluent' in config.get('ckan.plugins'):
            resource['name_translated'] = {'en': distribution.get('title', dcat_dict.get('title'))}
            resource['description_translated'] = {'en': distribution.get('description', '') or ''}

        if distribution.get('byteSize'):
            try:
                resource['size'] = int(distribution.get('byteSize'))
            except ValueError:
                pass
        package_dict['resources'].append(resource)

    return package_dict


def ckan_to_dcat(package_dict):

    dcat_dict = {}

    dcat_dict['title'] = package_dict.get('title')
    dcat_dict['description'] = package_dict.get('notes')
    dcat_dict['landingPage'] = package_dict.get('url')


    dcat_dict['keyword'] = []
    for tag in package_dict.get('tags', []):
        dcat_dict['keyword'].append(tag['name'])


    dcat_dict['publisher'] = {}

    for extra in package_dict.get('extras', []):
        if extra['key'] in ['dcat_issued', 'dcat_modified']:
            dcat_dict[extra['key'].replace('dcat_', '')] = extra['value']

        elif extra['key'] == 'language':
            dcat_dict['language'] = extra['value'].split(',')

        elif extra['key'] == 'dcat_publisher_name':
            dcat_dict['publisher']['name'] = extra['value']

        elif extra['key'] == 'dcat_publisher_email':
            dcat_dict['publisher']['mbox'] = extra['value']

        elif extra['key'] == 'guid':
            dcat_dict['identifier'] = extra['value']

    if not dcat_dict['publisher'].get('name') and package_dict.get('maintainer'):
        dcat_dict['publisher']['name'] = package_dict.get('maintainer')
        if package_dict.get('maintainer_email'):
            dcat_dict['publisher']['mbox'] = package_dict.get('maintainer_email')

    dcat_dict['distribution'] = []
    for resource in package_dict.get('resources', []):
        distribution = {
            'title': resource.get('name'),
            'description': resource.get('description'),
            'format': resource.get('format'),
            'byteSize': resource.get('size'),
            # TODO: downloadURL or accessURL depending on resource type?
            'accessURL': resource.get('url'),
        }
        dcat_dict['distribution'].append(distribution)

        if resource.get('datastore_active'):
            data_dictionary_distro = {
                'title': 'Data Dictionary'.format(resource.get('name')),
                'description': 'Data Dictionary of {}'.format(resource.get('url')),
                'format': 'CSV',
                'accessURL': '{}/datastore/dictionary_download/{}'.format(
                    config.get('ckan.site_url'), resource.get('id')),
                'modified': resource.get('metadata_modified', ""),
            }
            dcat_dict['distribution'].append(data_dictionary_distro)
    return dcat_dict


def disallow_file_format(file_format):
    if config.get('ckanext.format_filter.filter_type') == 'whitelist':
        if file_format in get_whitelist():
            return False
        return True
    elif config.get('ckanext.format_filter.filter_type') == 'blacklist':
        if file_format in get_blacklist():
            return True
    return False


def get_whitelist():
    whitelist_string = config.get('ckanext.format_filter.whitelist', '')
    return convert_to_filter_list(whitelist_string)


def get_blacklist():
    blacklist_string = config.get('ckanext.format_filter.blacklist', '')
    return convert_to_filter_list(blacklist_string)


def convert_to_filter_list(filter_string):
    format_list = []
    try:
        if filter_string:
            if isinstance(filter_string, str):
                filter_string = filter_string.split()
                format_list = [file_format.lower() for file_format in filter_string]
    except Exception as e:
        log.error(e)
    return format_list


def get_bbox_geojson(spatial):
    if isinstance(spatial, six.string_types):
        bbox = spatial.split(',')
        if len(bbox) == 4:
            point_a = '[{},{}]'.format(bbox[0], bbox[1])
            point_b = '[{},{}]'.format(bbox[0], bbox[3])
            point_c = '[{},{}]'.format(bbox[2], bbox[3])
            point_d = '[{},{}]'.format(bbox[2], bbox[1])
            coordinates = '[{},{},{},{},{}]'.format(point_a, point_b, point_c, point_d, point_a)
            bbox_str = '{\"type\": \"Polygon\", \"coordinates\": [' + coordinates + ']}'
            return bbox_str
    elif isinstance(spatial, dict):
        spatial_type = spatial.get('type', '')
        spatial_coordinates = spatial.get('coordinates')
        if spatial_type.lower() in ['point', 'polygon'] and isinstance(spatial_coordinates, list):
            return json.dumps(spatial)
        elif spatial_type.lower() == 'envelope' and isinstance(spatial_coordinates, list):
            point_a = '[{},{}]'.format(spatial_coordinates[0][0], spatial_coordinates[0][1])
            point_b = '[{},{}]'.format(spatial_coordinates[0][0], spatial_coordinates[1][1])
            point_c = '[{},{}]'.format(spatial_coordinates[1][0], spatial_coordinates[1][1])
            point_d = '[{},{}]'.format(spatial_coordinates[1][0], spatial_coordinates[0][1])
            coordinates = '[{},{},{},{},{}]'.format(point_a, point_b, point_c, point_d, point_a)
            bbox_str = '{\"type\": \"Polygon\", \"coordinates\": [' + coordinates + ']}'
            return bbox_str
