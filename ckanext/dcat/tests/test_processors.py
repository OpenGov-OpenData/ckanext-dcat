import json
import os

from ckanext.dcat.harvesters.configuration_processors import ResourceOrder
from nose.tools import assert_raises, assert_equal, assert_dict_equal, assert_list_equal

fixtures_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')


def get_package_dict():
    with open(os.path.join(fixtures_path, 'package_dict.json'), 'r') as f:
        result = json.load(f)
    return result


def get_dcat_config():
    with open(os.path.join(fixtures_path, 'package_dict.json'), 'r') as f:
        result = json.load(f)
    return result


class TestResourceOrder:

    @classmethod
    def setup_class(cls):
        cls.processor = ResourceOrder

    def test_validation_correct_format(self):
        config = {
            "resources_order": ["CSV", "ZIP"]
        }
        self.processor.check_config(config)

    def test_validation_incorrect_format(self):
        config = {
            "resources_order": "csv zip"
        }
        with assert_raises(ValueError):
            self.processor.check_config(config)

    def test_modify_package(self):
        package = get_package_dict()
        dcat_config = {}
        config = {
            "resources_order": ["CSV", "ZIP"]
        }
        resources_before = package['resources'][:]
        self.processor.modify_package_dict(package, config, dcat_config)
        resources_after = package['resources'][:]

        resource_order = [f.strip().lower() for f in config["resources_order"]]
        step = 0
        # Check that reordering resources
        for i, res_format in enumerate(resource_order):
            for res in resources_before:
                step_res_format = res.get('format', '').strip().lower()
                if res_format == step_res_format:
                    assert_equal(resources_after[step], res)
                    step += 1

        # Check all other types of resources
        for res in resources_before:
            step_res_format = res.get('format', '').strip().lower()
            if step_res_format not in resource_order:
                assert_equal(resources_after[step], res)
                step += 1
        # assert_equal(resources_after[0], resources_before[0])

    def test_modify_package_unnchangable(self):
        package = get_package_dict()
        resources_before = package['resources'][:]
        self.processor.modify_package_dict(package_dict=package, config_obj={}, dcat_dict={})
        resources_after = package['resources'][:]
        assert_list_equal(resources_after, resources_before)
