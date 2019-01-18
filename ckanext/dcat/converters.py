import logging
import mimetypes
import re
from datetime import datetime

log = logging.getLogger(__name__)
mimetypes.init()


def dcat_to_ckan(dcat_dict):

    package_dict = {}

    package_dict['title'] = dcat_dict.get('title')
    package_dict['notes'] = dcat_dict.get('description')

    # Boston uses fluent for multilingual fields
    package_dict['title_translated'] = {'en': dcat_dict.get('title')}
    package_dict['notes_translated'] = {'en': dcat_dict.get('description')}

    package_dict['url'] = dcat_dict.get('landingPage')

    package_dict['tags'] = []
    for keyword in dcat_dict.get('keyword', []):
        package_dict['tags'].append({'name': keyword})

    package_dict['released'] = datetime.strptime(dcat_dict.get('issued'),"%Y-%m-%dT%H:%M:%S.%fZ").strftime("%Y-%m-%d")
    package_dict['modified'] = datetime.strptime(dcat_dict.get('modified'),"%Y-%m-%dT%H:%M:%S.%fZ").strftime("%Y-%m-%d")

    # Default values for Boston metadata
    package_dict['classification'] = 'public'
    package_dict['open'] = 'open'
    package_dict['publisher'] = 'Department of Innovation and Technology'
    package_dict['license_id'] = 'odc-pddl'
    package_dict['btype'] = 'geospatial'

    contactPoint = dcat_dict.get('contactPoint','')
    #contactPointFN = contactPoint.get('fn','GIS Team')
    contactPointFN = 'GIS Team'
    contactPointEmail = contactPoint.get('hasEmail','opengov@cityofboston.gov').split(':')[1]
    package_dict['contact_point'] = contactPointFN
    package_dict['contact_point_email'] = contactPointEmail

    package_dict['extras'] = []

    package_dict['extras'].append({'key': 'guid', 'value': dcat_dict.get('identifier')})

    dcat_publisher = dcat_dict.get('publisher')
    if isinstance(dcat_publisher, basestring):
        package_dict['extras'].append({'key': 'dcat_publisher_name', 'value': dcat_publisher})
    elif isinstance(dcat_publisher, dict) and dcat_publisher.get('name'):
        package_dict['extras'].append({'key': 'dcat_publisher_name', 'value': dcat_publisher.get('name')})
        package_dict['extras'].append({'key': 'dcat_publisher_email', 'value': dcat_publisher.get('mbox')})

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
    format_order = ['GeoJSON','CSV','KML','ZIP','Esri REST','Web page']
    # Boston wants to first add resources in desired order
    for format in format_order:
        for distribution in dcat_dict.get('distribution', []):
            if distribution.get('format') == format:
                resource = get_resource_dict(distribution)
                package_dict['resources'].append(resource)

    # Add resources with other formats
    for distribution in dcat_dict.get('distribution', []):
        if distribution.get('format') not in format_order:
            resource = get_resource_dict(distribution)
            package_dict['resources'].append(resource)

    return package_dict


def get_resource_dict(distribution):
    format = ''
    if distribution.get('format'):
        format = distribution.get('format')
    elif distribution.get('mediaType'):
        ext = mimetypes.guess_extension(distribution.get('mediaType'))
        if ext:
            format = ext[1:]
    resource = {
        'name': distribution.get('title'),
        'description': distribution.get('description'),
        'url': distribution.get('downloadURL') or distribution.get('accessURL'),
        'format': distribution.get('format'),
    }
    if distribution.get('byteSize'):
        try:
            resource['size'] = int(distribution.get('byteSize'))
        except ValueError:
            pass
    return resource


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
