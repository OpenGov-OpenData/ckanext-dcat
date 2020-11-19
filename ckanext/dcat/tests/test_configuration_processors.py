import json
import os

from ckanext.dcat.harvesters.configuration_processors import (
    DefaultTags, CleanTags,
    DefaultGroups, DefaultExtras, DefaultValues,
    MappingFields, Publisher, ContactPoint,
    OrganizationFilter,
    ResourceFormatOrder,
    KeepExistingResources)
from nose.tools import assert_raises, assert_equal, assert_dict_equal, assert_list_equal



class TestDefaultTags:
    @classmethod
    def setup_class(cls):
        cls.processor = DefaultTags

    def test_validation_correct_format(self):
        list_of_dicts_config = {
            "default_tags": [{"name": "geo"}, {"name": "namibia"}]
        }
        self.processor.check_config(list_of_dicts_config)

    def test_validation_wrong_format(self):
        empty_config = {
            "default_tags": ""
        }
        with assert_raises(ValueError):
            self.processor.check_config(empty_config)

        string_config = {
            "default_tags": "geo"
        }
        with assert_raises(ValueError):
            self.processor.check_config(string_config)

        list_config = {
            "default_tags": ["geo", "namibia"]
        }
        with assert_raises(ValueError):
            self.processor.check_config(list_config)

    def test_modify_package_tags(self):
        package = {
            "title": "Test Dataset",
            "name": "test-dataset",
            "tags": [{"name": "russian"}, {"name": "tolstoy"}]
        }
        config = {
            "default_tags": [{"name": "geo"}, {"name": "namibia"}]
        }
        dcat_dict = {}

        self.processor.modify_package_dict(package, config, dcat_dict)

        tag_names = sorted([tag_dict["name"] for tag_dict in package["tags"]])
        assert_equal(tag_names, ["geo", "namibia", "russian", "tolstoy"])


class TestCleanTags:
    @classmethod
    def setup_class(cls):
        cls.processor = CleanTags

    def test_modify_package_clean_tags(self):
        package = {
            "title": "Test Dataset",
            "name": "test-dataset",
            "tags": [{"name": "tolstoy!"}]
        }
        config = {}
        dcat_dict = {}

        self.processor.modify_package_dict(package, config, dcat_dict)

        tag_names = sorted([tag_dict["name"] for tag_dict in package["tags"]])
        assert_equal(tag_names, ["tolstoy"])


class TestDefaultGroups:
    @classmethod
    def setup_class(cls):
        cls.processor = DefaultGroups

    def test_modify_package_groups(self):
        package = {
            "title": "Test Dataset",
            "name": "test-dataset",
            "groups": []
        }
        config = {
            "default_groups": ["science", "spend-data"],
            "default_group_dicts": [
                {
                    "id": "b1084f72-292d-11eb-adc1-0242ac120002",
                    "name": "science",
                    "title": "Science",
                    "display_name": "Science",
                    "is_organization": False,
                    "type": "group",
                    "state": "active"
                },
                {
                    "id": "0d7090cc-12c1-4d19-85ba-9bcfc563ab7e",
                    "name": "spend-data",
                    "title": "Spend Data",
                    "display_name": "Spend Data",
                    "is_organization": False,
                    "type": "group",
                    "state": "active"
                }
            ]
        }
        dcat_dict = {}

        self.processor.modify_package_dict(package, config, dcat_dict)

        group_names = sorted([group_dict["name"] for group_dict in package["groups"]])
        assert_equal(group_names, ["science", "spend-data"])


class TestDefaultExtras:
    @classmethod
    def setup_class(cls):
        cls.processor = DefaultExtras

    def test_validation_correct_format(self):
        dict_config = {
            "default_extras": {
                "encoding": "utf8"
            }
        }
        self.processor.check_config(dict_config)

    def test_validation_wrong_format(self):
        empty_config = {
            "default_extras": ""
        }
        with assert_raises(ValueError):
            self.processor.check_config(empty_config)

        list_of_dicts_config = {
            "default_extras": [{"encoding": "utf8"}]
        }
        with assert_raises(ValueError):
            self.processor.check_config(list_of_dicts_config)

    def test_modify_package_extras(self):
        package = {
            "title": "Test Dataset",
            "name": "test-dataset",
            "extras": []
        }
        config = {
            "default_extras": { "encoding": "utf8" }
        }
        dcat_dict = {}

        self.processor.modify_package_dict(package, config, dcat_dict)

        assert_equal(package["extras"][0]["key"], "encoding")
        assert_equal(package["extras"][0]["value"], "utf8")


class TestDefaultValues:
    @classmethod
    def setup_class(cls):
        cls.processor = DefaultValues

    def test_validation_correct_format(self):
        list_of_dicts_config = {
            "default_values": [
                { "notes": "Some notes" }
            ]
        }
        self.processor.check_config(list_of_dicts_config)

    def test_validation_wrong_format(self):
        empty_config = {
            "default_values": ""
        }
        with assert_raises(ValueError):
            self.processor.check_config(empty_config)

        dict_config = {
            "default_values": { "notes": "Some notes" }
        }
        with assert_raises(ValueError):
            self.processor.check_config(dict_config)

    def test_modify_package_values(self):
        package = {
            "title": "Test Dataset",
            "name": "test-dataset",
            "notes": ""
        }
        config = {
            "default_values": [
                { "notes": "Some notes" },
                { "language": "English" }
            ]
        }
        dcat_dict = {}

        self.processor.modify_package_dict(package, config, dcat_dict)

        assert_equal(package["notes"], "Some notes")
        assert_equal(package["language"], "English")


class TestMappingFields:
    @classmethod
    def setup_class(cls):
        cls.processor = MappingFields

    def test_validation_correct_format(self):
        list_of_dicts_config = {
            "map_fields": [
                {
                    "source": "language",
                    "target": "language",
                    "default": "English"
                }
            ]
        }
        self.processor.check_config(list_of_dicts_config)

    def test_validation_wrong_format(self):
        empty_config = {
            "map_fields": ""
        }
        with assert_raises(ValueError):
            self.processor.check_config(empty_config)

        dict_config = {
            "map_fields": {
                "source": "language",
                "target": "language",
                "default": "English"
            }
        }
        with assert_raises(ValueError):
            self.processor.check_config(dict_config)

    def test_modify_package_mapping_values(self):
        package = {
            "title": "Test Dataset",
            "name": "test-dataset"
        }
        config = {
            "map_fields": [
                {
                    "source": "language",
                    "target": "language",
                    "default": "English"
                }
            ]
        }
        dcat_dict = {
            "title": "Test Dataset",
            "name": "test-dataset",
            "language": "Spanish"
        }

        self.processor.modify_package_dict(package, config, dcat_dict)

        assert_equal(package["language"], "Spanish")


class TestPublisher:
    @classmethod
    def setup_class(cls):
        cls.processor = Publisher

    def test_validation_correct_format(self):
        dict_config = {
            "publisher": {
                "publisher_field": "publisher",
                "default_publisher": "Open Data"
            }
        }
        self.processor.check_config(dict_config)

    def test_validation_wrong_format(self):
        empty_config = {
            "publisher": ""
        }
        with assert_raises(ValueError):
            self.processor.check_config(empty_config)

        list_of_dicts_config = {
            "publisher": [
                { "publisher_field": "publisher" },
                { "default_publisher": "Open Data" }
            ]
        }
        with assert_raises(ValueError):
            self.processor.check_config(list_of_dicts_config)

    def test_modify_package_publisher_field(self):
        package = {
            "title": "Test Dataset",
            "name": "test-dataset"
        }
        config = {
            "publisher": {
                "publisher_field": "publisher",
                "default_publisher": "Open Data"
            }
        }
        dcat_dict = {
            "title": "Test Dataset",
            "name": "test-dataset",
            "publisher": {
                "name": "U.S. Census"
            }
        }

        self.processor.modify_package_dict(package, config, dcat_dict)

        assert_equal(package["publisher"], "U.S. Census")


class TestContactPoint:
    @classmethod
    def setup_class(cls):
        cls.processor = ContactPoint

    def test_validation_correct_format(self):
        dict_config = {
            "contact_point": {
                "name_field": "contact_name",
                "default_name": "nonameprovided",
                "email_field": "contact_email",
                "default_email": "noemailprovided@agency.gov"
            }
        }
        self.processor.check_config(dict_config)

    def test_validation_wrong_format(self):
        empty_config = {
            "contact_point": ""
        }
        with assert_raises(ValueError):
            self.processor.check_config(empty_config)

        list_of_dicts_config = {
            "contact_point": [
                { "name_field": "contact_name" },
                { "default_name": "nonameprovided" },
                { "email_field": "contact_email" },
                { "default_email": "noemailprovided@agency.gov" }
            ]
        }
        with assert_raises(ValueError):
            self.processor.check_config(list_of_dicts_config)

    def test_modify_package_contact_fields(self):
        package = {
            "title": "Test Dataset",
            "name": "test-dataset"
        }
        config = {
            "contact_point": {
                "name_field": "contact_name",
                "default_name": "None",
                "email_field": "contact_email",
                "default_email": "None"
            }
        }
        dcat_dict = {
            "title": "Test Dataset",
            "name": "test-dataset",
            "contactPoint": {
                "@type": "vcard:Contact",
                "fn": "Jane Doe",
                "hasEmail": "mailto:jane.doe@agency.gov"
            }
        }

        self.processor.modify_package_dict(package, config, dcat_dict)

        assert_equal(package["contact_name"], "Jane Doe")
        assert_equal(package["contact_email"], "jane.doe@agency.gov")


class TestResourceFormatOrder:
    @classmethod
    def setup_class(cls):
        cls.processor = ResourceFormatOrder

    def test_validation_correct_format(self):
        config = {
            "resource_format_order": ["CSV", "ZIP"]
        }
        self.processor.check_config(config)

    def test_validation_wrong_format(self):
        config = {
            "resource_format_order": "csv zip"
        }
        with assert_raises(ValueError):
            self.processor.check_config(config)

    def test_modify_package_resource_format_order(self):
        package = {
            "title": "Test Dataset",
            "name": "test-dataset",
            "resources": [
                {
                    "name": "Web Resource",
                    "format": "HTML"
                },
                {
                    "name": "GeoJSON Resource",
                    "format": "GeoJSON"
                },
                {
                    "name": "CSV Resource",
                    "format": "CSV"
                },
                {
                    "name": "ZIP Resource",
                    "format": "ZIP"
                }
            ]
        }
        config = {
            "resource_format_order": ["CSV", "ZIP"]
        }
        dcat_dict = {}

        self.processor.modify_package_dict(package, config, dcat_dict)

        res_formats = [res_dict["format"] for res_dict in package["resources"]]
        assert_equal(res_formats, ["CSV", "ZIP", "HTML", "GeoJSON"])


class TestKeepExistingResources:
    @classmethod
    def setup_class(cls):
        cls.processor = KeepExistingResources

    def test_validation_correct_format(self):
        config = {
            "keep_existing_resources": True
        }
        self.processor.check_config(config)

    def test_validation_wrong_format(self):
        config = {
            "keep_existing_resources": "true"
        }
        with assert_raises(ValueError):
            self.processor.check_config(config)
