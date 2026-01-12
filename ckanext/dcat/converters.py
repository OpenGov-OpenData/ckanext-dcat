from past.builtins import basestring
import json
import logging
import mimetypes
import six
from ckan.plugins.toolkit import get_action, asbool, config


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

        if dcat_publisher.get('email'):
            package_dict['extras'].append({'key': 'dcat_publisher_email', 'value': dcat_publisher.get('email')})

        if dcat_publisher.get('identifier'):
            package_dict['extras'].append({
                'key': 'dcat_publisher_id',
                'value': dcat_publisher.get('identifier')  # This could be a URI like https://ror.org/05wg1m734
            })

    dcat_creator = dcat_dict.get('creator')
    if isinstance(dcat_creator, basestring):
        package_dict['extras'].append({'key': 'dcat_creator_name', 'value': dcat_creator})
    elif isinstance(dcat_creator, dict) and dcat_creator.get('name'):
        if dcat_creator.get('name'):
            package_dict['extras'].append({'key': 'dcat_creator_name', 'value': dcat_creator.get('name')})

        if dcat_creator.get('email'):
            package_dict['extras'].append({'key': 'dcat_creator_email', 'value': dcat_creator.get('email')})

        if dcat_creator.get('identifier'):
            package_dict['extras'].append({
                'key': 'dcat_creator_id',
                'value': dcat_creator.get('identifier')
            })

    if dcat_dict.get('language'):
        package_dict['extras'].append({
            'key': 'language',
            'value': ','.join(dcat_dict.get('language', []))
        })

    bbox_geojson = get_bbox_geojson(dcat_dict.get('spatial'))
    if bbox_geojson:
        package_dict['extras'].append({"key": "spatial", "value": bbox_geojson})

    if dcat_dict.get('license'):
        for license in get_action('license_list')({}, {}):
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

        # Normalize distribution URL values
        if 'downloadURL' in distribution:
            normalized_downloadURL = _normalize_url_value(distribution['downloadURL'], 'downloadURL')
            distribution['downloadURL'] = normalized_downloadURL

        if 'accessURL' in distribution:
            normalized_accessURL = _normalize_url_value(distribution['accessURL'], 'accessURL')
            distribution['accessURL'] = normalized_accessURL

        if not distribution.get('downloadURL') and not distribution.get('accessURL'):
            log.debug('Skip resource %s, no valid URL in downloadURL or accessURL' % (
                distribution.get('title', dcat_dict.get('title'))
            ))
            continue

        # skip data dictionaries
        if asbool(distribution.get('isDataDictionary', False)):
            log.debug('Skip data dictionary for %s: %s' % (
                distribution.get('title', dcat_dict.get('title')),
                distribution.get('downloadURL') or distribution.get('accessURL'))
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

    # Keywords
    dcat_dict['keyword'] = []
    for tag in package_dict.get('tags', []):
        dcat_dict['keyword'].append(tag['name'])

    # Publisher
    dcat_dict['publisher'] = {}
    dcat_dict['creator'] = {}

    for extra in package_dict.get('extras', []):
        if extra['key'] in ['dcat_issued', 'dcat_modified']:
            dcat_dict[extra['key'].replace('dcat_', '')] = extra['value']

        elif extra['key'] == 'language':
            dcat_dict['language'] = extra['value'].split(',')

        # Publisher fields
        elif extra['key'] == 'dcat_publisher_name':
            dcat_dict['publisher']['name'] = extra['value']

        elif extra['key'] == 'dcat_publisher_email':
            dcat_dict['publisher']['email'] = extra['value']

        elif extra['key'] == 'dcat_publisher_id':
            dcat_dict['publisher']['identifier'] = extra['value']

        # Creator fields
        elif extra['key'] == 'dcat_creator_name':
            dcat_dict['creator']['name'] = extra['value']

        elif extra['key'] == 'dcat_creator_email':
            dcat_dict['creator']['email'] = extra['value']

        elif extra['key'] == 'dcat_creator_id':
            dcat_dict['creator']['identifier'] = extra['value']

        # Identifier
        elif extra['key'] == 'guid':
            dcat_dict['identifier'] = extra['value']

    # Fallback for publisher (if no name in extras, use maintainer)
    if not dcat_dict['publisher'].get('name') and package_dict.get('maintainer'):
        dcat_dict['publisher']['name'] = package_dict.get('maintainer')
        if package_dict.get('maintainer_email'):
            dcat_dict['publisher']['email'] = package_dict.get('maintainer_email')

    # Fallback for creator (if no name in extras, optionally use author)
    if not dcat_dict['creator'].get('name') and package_dict.get('author'):
        dcat_dict['creator']['name'] = package_dict.get('author')
        if package_dict.get('author_email'):
            dcat_dict['creator']['email'] = package_dict.get('author_email')

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

        if resource.get('is_data_dict_populated'):
            data_dictionary_distrib = {
                'title': 'Data Dictionary - {}'.format(resource.get('name')),
                'description': 'Data Dictionary for {}'.format(resource.get('url')),
                'format': 'CSV',
                'downloadURL': '{}/datastore/dictionary_download/{}'.format(
                    config.get('ckan.site_url'), resource.get('id')),
                'isDataDictionary': True,
            }
            dcat_dict['distribution'].append(data_dictionary_distrib)
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


def _normalize_url_value(value, field_name='URL'):
    """Extract first valid URL from string or list."""
    if not value:
        return ''

    SUPPORTED_PROTOCOLS = ('http://', 'https://', 'ftp://', 'ftps://', 's3://')

    if isinstance(value, str):
        return value

    if isinstance(value, list):
        log.debug('%s provided as list with %d items', field_name, len(value))
        for item in value:
            if isinstance(item, str) and item.startswith(SUPPORTED_PROTOCOLS):
                log.debug('%s: using first valid URL from list: %s', field_name, item)
                return item
        log.debug('%s provided as list but no valid URLs found', field_name)
        return ''

    log.warning('%s has unexpected type: %s', field_name, type(value).__name__)
    return ''
