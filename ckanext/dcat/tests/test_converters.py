from builtins import object
import os
import json
import difflib

from ckanext.dcat import converters


def _get_file_as_dict(file_name):
    path = os.path.join(os.path.dirname(__file__),
                        '..', '..', '..', 'examples',
                        file_name)
    with open(path, 'r') as f:
        return json.load(f)

def _poor_mans_dict_diff(d1, d2):
    def _get_lines(d):
        return sorted([l.strip().rstrip(',')
                       for l in json.dumps(d, indent=0).split('\n')
                       if not l.startswith(('{', '}', '[', ']'))])

    d1_lines = _get_lines(d1)
    d2_lines = _get_lines(d2)

    return '\n' + '\n'.join([l for l in difflib.ndiff(d1_lines, d2_lines)
                             if l.startswith(('-', '+'))])

def test_ckan_to_dcat():
    ckan_dict =_get_file_as_dict('full_ckan_dataset.json')
    expected_dcat_dict =_get_file_as_dict('dataset.json')

    dcat_dict = converters.ckan_to_dcat(ckan_dict)

    assert dcat_dict == expected_dcat_dict,_poor_mans_dict_diff(
        expected_dcat_dict, dcat_dict)

def test_dcat_to_ckan():
    dcat_dict =_get_file_as_dict('dataset.json')
    expected_ckan_dict =_get_file_as_dict('ckan_dataset.json')

    # Pop CKAN specific fields
    expected_ckan_dict.pop('id', None)
    expected_ckan_dict['resources'][0].pop('id', None)
    expected_ckan_dict['resources'][0].pop('package_id', None)

    ckan_dict = converters.dcat_to_ckan(dcat_dict)

    assert ckan_dict == expected_ckan_dict,_poor_mans_dict_diff(
        expected_ckan_dict, ckan_dict)

def test_get_bbox_geojson():
    spatial_string = '-124.4820,32.5288,-114.1312,42.0095'
    bbox_geojson_1 = converters.get_bbox_geojson(spatial_string)
    assert bbox_geojson_1 == ('{"type": "Polygon", "coordinates": [['
        '[-124.4820,32.5288],[-124.4820,42.0095],'
        '[-114.1312,42.0095],[-114.1312,32.5288],'
        '[-124.4820,32.5288]]]}'
    )

    spatial_envelope = {
        "type": "envelope",
        "coordinates": [[-124.1986, 32.5586], [-71.3508, 47.299 ]]
    }
    bbox_geojson_2 = converters.get_bbox_geojson(spatial_envelope)
    assert bbox_geojson_2 == ('{"type": "Polygon", "coordinates": [['
        '[-124.1986,32.5586],[-124.1986,47.299],'
        '[-71.3508,47.299],[-71.3508,32.5586],'
        '[-124.1986,32.5586]]]}'
    )

    spatial_polygon = {
        "type": "Polygon",
        "coordinates": [[
            [-124.1610, 32.5718], [-124.1610, 41.3149],
            [-115.5028, 41.3149], [-115.5028, 32.5718],
            [-124.1610, 32.5718]
        ]]
    }
    bbox_geojson_3 = converters.get_bbox_geojson(spatial_polygon)
    assert bbox_geojson_3 == ('{"type": "Polygon", "coordinates": [['
        '[-124.161, 32.5718], [-124.161, 41.3149], '
        '[-115.5028, 41.3149], [-115.5028, 32.5718], '
        '[-124.161, 32.5718]]]}'
    )
