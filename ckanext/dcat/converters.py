from past.builtins import basestring
import logging
import mimetypes
import re

try:
    from ckan.common import config
except ImportError:
    from pylons import config

log = logging.getLogger(__name__)
mimetypes.init()


def dcat_to_ckan(dcat_dict):

    package_dict = {}

    package_dict['title'] = dcat_dict.get('title')
    package_dict['notes'] = dcat_dict.get('description')
    package_dict['url'] = dcat_dict.get('landingPage')


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

    bbox = dcat_dict.get('spatial','').split(',')
    if len(bbox) == 4:
        point_a = '[{},{}]'.format(bbox[0], bbox[1])
        point_b = '[{},{}]'.format(bbox[0], bbox[3])
        point_c = '[{},{}]'.format(bbox[2], bbox[3])
        point_d = '[{},{}]'.format(bbox[2], bbox[1])
        coordinates = '[{},{},{},{},{}]'.format(point_a, point_b, point_c, point_d, point_a)
        bbox_str = '{\"type\": \"Polygon\", \"coordinates\": [' + coordinates + ']}'
        package_dict['extras'].append({"key": "spatial", "value": bbox_str})

    #package_dict['extras'].append({
    #    'key': 'language',
    #    'value': ','.join(dcat_dict.get('language', []))
    #})

    package_dict['resources'] = []
    for distribution in dcat_dict.get('distribution', []):
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
            'description': distribution.get('description'),
            'url': distribution.get('downloadURL') or distribution.get('accessURL'),
            'format': format,
        }

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
