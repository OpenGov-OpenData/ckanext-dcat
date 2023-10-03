import json
import os

from ckanext.dcat.configuration_processors import (
    ParseID,
    DefaultTags, CleanTags,
    DefaultGroups, DefaultExtras, DefaultValues,
    MappingFields, CompositeMapping,
    Publisher, ContactPoint,
    OrganizationFilter,
    ResourceFormatOrder,
    KeepExistingResources
)


class TestParseID:

    processor = ParseID

    def test_validation_correct_format(self):
        config = {
            "parse_id_if_url": True
        }
        try:
            self.processor.check_config(config)
        except ValueError:
            assert False

    def test_validation_wrong_format(self):
        empty_config = {
            "parse_id_if_url": ""
        }
        try:
            self.processor.check_config(empty_config)
            assert False
        except ValueError:
            assert True

        string_config = {
            "parse_id_if_url": "enabled"
        }
        try:
            self.processor.check_config(string_config)
            assert False
        except ValueError:
            assert True


class TestDefaultTags:

    processor = DefaultTags

    def test_validation_correct_format(self):
        list_of_dicts_config = {
            "default_tags": [{"name": "geo"}, {"name": "namibia"}]
        }
        try:
            self.processor.check_config(list_of_dicts_config)
        except ValueError:
            assert False

    def test_validation_wrong_format(self):
        empty_config = {
            "default_tags": ""
        }
        try:
            self.processor.check_config(empty_config)
            assert False
        except ValueError:
            assert True

        string_config = {
            "default_tags": "geo"
        }
        try:
            self.processor.check_config(string_config)
            assert False
        except ValueError:
            assert True

        list_config = {
            "default_tags": ["geo", "namibia"]
        }
        try:
            self.processor.check_config(list_config)
            assert False
        except ValueError:
            assert True

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
        assert tag_names == ["geo", "namibia", "russian", "tolstoy"]


class TestCleanTags:

    processor = CleanTags

    def test_modify_package_clean_tags(self):
        package = {
            "title": "Test Dataset",
            "name": "test-dataset",
            "tags": [{"name": "tolstoy!"}]
        }
        config = {
            "clean_tags": True
        }
        dcat_dict = {}

        self.processor.modify_package_dict(package, config, dcat_dict)

        tag_names = sorted([tag_dict["name"] for tag_dict in package["tags"]])
        assert tag_names == ["tolstoy"]


class TestDefaultGroups:

    processor = DefaultGroups

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
        assert group_names == ["science", "spend-data"]


class TestDefaultExtras:

    processor = DefaultExtras

    def test_validation_correct_format(self):
        dict_config = {
            "default_extras": {
                "encoding": "utf8"
            }
        }
        try:
            self.processor.check_config(dict_config)
        except ValueError:
            assert False

    def test_validation_wrong_format(self):
        empty_config = {
            "default_extras": ""
        }
        try:
            self.processor.check_config(empty_config)
            assert False
        except ValueError:
            assert True

        list_of_dicts_config = {
            "default_extras": [{"encoding": "utf8"}]
        }
        try:
            self.processor.check_config(list_of_dicts_config)
            assert False
        except ValueError:
            assert True

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

        assert package["extras"][0]["key"] == "encoding"
        assert package["extras"][0]["value"] == "utf8"


class TestDefaultValues:

    processor = DefaultValues

    def test_validation_correct_format(self):
        list_of_dicts_config = {
            "default_values": [
                { "notes": "Some notes" }
            ]
        }
        try:
            self.processor.check_config(list_of_dicts_config)
        except ValueError:
            assert False

    def test_validation_wrong_format(self):
        empty_config = {
            "default_values": ""
        }
        try:
            self.processor.check_config(empty_config)
            assert False
        except ValueError:
            assert True

        dict_config = {
            "default_values": { "notes": "Some notes" }
        }
        try:
            self.processor.check_config(dict_config)
            assert False
        except ValueError:
            assert True

    def test_validation_do_not_set_dataset_id(self):
        id_config = {
            "default_values": [
                { "id": "Dataset ID" }
            ]
        }
        try:
            self.processor.check_config(id_config)
            assert False
        except ValueError:
            assert True

    def test_validation_do_not_set_dataset_name(self):
        name_config = {
            "default_values": [
                { "name": "Dataset Name" }
            ]
        }
        try:
            self.processor.check_config(name_config)
            assert False
        except ValueError:
            assert True

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

        assert package["notes"] == "Some notes"
        assert package["language"] == "English"


class TestMappingFields:

    processor = MappingFields

    def test_modify_package_with_empty_description_values(self):
        package = {
            "title": "Test Dataset",
            "name": "test-dataset"
        }
        config = {
            "map_fields": [
                {
                    "default": "No Description",
                    "source": "description",
                    "target": "notes"
                }
            ]
        }
        dcat_dict = {
            "title": "Test Dataset",
            "name": "test-dataset",
            "description": ""
        }

        self.processor.modify_package_dict(package, config, dcat_dict)

        assert package["notes"] == "No Description"

    def test_modify_package_with_no_description_values(self):
        package = {
            "title": "Test Dataset",
            "name": "test-dataset"
        }
        config = {
            "map_fields": [
                {
                    "default": "No Description",
                    "source": "description",
                    "target": "notes"
                }
            ]
        }
        dcat_dict = {
            "title": "Test Dataset",
            "name": "test-dataset",
        }

        self.processor.modify_package_dict(package, config, dcat_dict)

        assert package["notes"] == "No Description"

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
        try:
            self.processor.check_config(list_of_dicts_config)
        except ValueError:
            assert False

    def test_validation_wrong_format(self):
        empty_config = {
            "map_fields": ""
        }
        try:
            self.processor.check_config(empty_config)
            assert False
        except ValueError:
            assert True

        dict_config = {
            "map_fields": {
                "source": "language",
                "target": "language",
                "default": "English"
            }
        }
        try:
            self.processor.check_config(dict_config)
            assert False
        except ValueError:
            assert True

    def test_validation_do_not_set_dataset_id(self):
        id_config = {
            "map_fields": [
                {
                    "source": "description",
                    "target": "id",
                    "default": "Dataset ID"
                }
            ]
        }
        try:
            self.processor.check_config(id_config)
            assert False
        except ValueError:
            assert True

    def test_validation_do_not_set_dataset_name(self):
        name_config = {
            "map_fields": [
                {
                    "source": "description",
                    "target": "name",
                    "default": "Dataset Name"
                }
            ]
        }
        try:
            self.processor.check_config(name_config)
            assert False
        except ValueError:
            assert True

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

        assert package["language"] == "Spanish"

    def test_modify_package_mapping_values_with_issued_date(self):
        package = {
            "title": "Test Dataset",
            "name": "test-dataset"
        }
        config = {
            "map_fields": [
                {
                    "source": "issued_date",
                    "target": "issued_date"
                }
            ]
        }
        dcat_dict = {
            "title": "Test Dataset",
            "name": "test-dataset",
            "issued": "2021-08-01T20:05:31.000Z"
        }

        self.processor.modify_package_dict(package, config, dcat_dict)

        assert package["issued_date"] == "2021-08-01"

    def test_modify_package_mapping_values_with_issued_time(self):
        package = {
            "title": "Test Dataset 1",
            "name": "test-dataset-1"
        }
        config = {
            "map_fields": [
                {
                    "source": "issued_time",
                    "target": "issued_time"
                }
            ]
        }
        dcat_dict = {
            "title": "Test Dataset-1",
            "name": "test-dataset-1",
            "issued": "2021-08-01T20:05:31.000Z"
        }

        self.processor.modify_package_dict(package, config, dcat_dict)

        assert package["issued_time"] == "20:05:31.000000Z"

    def test_modify_package_mapping_values_with_modified_date(self):
        package = {
            "title": "Test Dataset",
            "name": "test-dataset"
        }
        config = {
            "map_fields": [
                {
                    "source": "modified_date",
                    "target": "modified_date"
                }
            ]
        }
        dcat_dict = {
            "title": "Test Dataset",
            "name": "test-dataset",
            "modified": "2022-08-31T11:16:25.000Z"
        }

        self.processor.modify_package_dict(package, config, dcat_dict)

        assert package["modified_date"] == "2022-08-31"

    def test_modify_package_mapping_values_with_modified_time(self):
        package = {
            "title": "Test Dataset 1",
            "name": "test-dataset-1"
        }
        config = {
            "map_fields": [
                {
                    "source": "modified_time",
                    "target": "modified_time"
                }
            ]
        }
        dcat_dict = {
            "title": "Test Dataset-1",
            "name": "test-dataset-1",
            "modified": "2022-08-31T11:16:25.000Z"
        }

        self.processor.modify_package_dict(package, config, dcat_dict)

        assert package["modified_time"] == "11:16:25.000000Z"


class TestCompositeMapping:

    processor = CompositeMapping

    def test_modify_package(self):
        package = {
            "title": "Test Dataset 1",
            "name": "test-dataset-1"
        }

        config = {
            "composite_field_mapping": [
                {
                    "idInfoCitation": {
                        "publicationDate": "metadataReviseDate"
                    }
                }
            ]
        }
        dcat_dict = {
            "title": "Test Dataset-1",
            "name": "test-dataset-1",
            "metadataReviseDate": "2023-01-01T18:35:34.000Z"
        }

        self.processor.modify_package_dict(package, config, dcat_dict)

        assert package["idInfoCitation"] == "{\"publicationDate\": \"2023-01-01T18:35:34.000Z\"}"


class TestPublisher:

    processor = Publisher

    def test_validation_correct_format(self):
        dict_config = {
            "publisher": {
                "publisher_field": "publisher",
                "default_publisher": "Open Data"
            }
        }
        try:
            self.processor.check_config(dict_config)
        except ValueError:
            assert False

    def test_validation_wrong_format(self):
        empty_config = {
            "publisher": ""
        }
        try:
            self.processor.check_config(empty_config)
            assert False
        except ValueError:
            assert True

        list_of_dicts_config = {
            "publisher": [
                { "publisher_field": "publisher" },
                { "default_publisher": "Open Data" }
            ]
        }
        try:
            self.processor.check_config(list_of_dicts_config)
            assert False
        except ValueError:
            assert True

    def test_validation_do_not_set_dataset_id(self):
        id_config = {
            "publisher": {
                "publisher_field": "id",
                "default_publisher": "Open Data"
            }
        }
        try:
            self.processor.check_config(id_config)
            assert False
        except ValueError:
            assert True

    def test_validation_do_not_set_dataset_name(self):
        name_config = {
            "publisher": {
                "publisher_field": "name",
                "default_publisher": "Open Data"
            }
        }
        try:
            self.processor.check_config(name_config)
            assert False
        except ValueError:
            assert True

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

        assert package["publisher"] == "U.S. Census"


class TestContactPoint:

    processor = ContactPoint

    def test_validation_correct_format(self):
        dict_config = {
            "contact_point": {
                "name_field": "contact_name",
                "default_name": "nonameprovided",
                "email_field": "contact_email",
                "default_email": "noemailprovided@agency.gov"
            }
        }
        try:
            self.processor.check_config(dict_config)
        except ValueError:
            assert False

    def test_validation_wrong_format(self):
        empty_config = {
            "contact_point": ""
        }
        try:
            self.processor.check_config(empty_config)
            assert False
        except ValueError:
            assert True

        list_of_dicts_config = {
            "contact_point": [
                { "name_field": "contact_name" },
                { "default_name": "nonameprovided" },
                { "email_field": "contact_email" },
                { "default_email": "noemailprovided@agency.gov" }
            ]
        }
        try:
            self.processor.check_config(list_of_dicts_config)
            assert False
        except ValueError:
            assert True

    def test_validation_do_not_set_contact_name_to_dataset_id(self):
        id_config = {
            "contact_point": {
                "name_field": "id",
                "default_name": "nonameprovided",
                "email_field": "contact_email",
                "default_email": "noemailprovided@agency.gov"
            }
        }
        try:
            self.processor.check_config(id_config)
            assert False
        except ValueError:
            assert True

    def test_validation_do_not_set_contact_name_to_dataset_name(self):
        name_config = {
            "contact_point": {
                "name_field": "name",
                "default_name": "nonameprovided",
                "email_field": "contact_email",
                "default_email": "noemailprovided@agency.gov"
            }
        }
        try:
            self.processor.check_config(name_config)
            assert False
        except ValueError:
            assert True

    def test_validation_do_not_set_contact_email_to_dataset_id(self):
        id_config = {
            "contact_point": {
                "name_field": "contact_name",
                "default_name": "nonameprovided",
                "email_field": "id",
                "default_email": "noemailprovided@agency.gov"
            }
        }
        try:
            self.processor.check_config(id_config)
            assert False
        except ValueError:
            assert True

    def test_validation_do_not_set_contact_name_to_dataset_name(self):
        name_config = {
            "contact_point": {
                "name_field": "contact_name",
                "default_name": "nonameprovided",
                "email_field": "name",
                "default_email": "noemailprovided@agency.gov"
            }
        }
        try:
            self.processor.check_config(name_config)
            assert False
        except ValueError:
            assert True

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

        assert package["contact_name"] == "Jane Doe"
        assert package["contact_email"] == "jane.doe@agency.gov"


class TestResourceFormatOrder:

    processor = ResourceFormatOrder

    def test_validation_correct_format(self):
        config = {
            "resource_format_order": ["CSV", "ZIP"]
        }
        try:
            self.processor.check_config(config)
        except ValueError:
            assert False

    def test_validation_wrong_format(self):
        config = {
            "resource_format_order": "csv zip"
        }
        try:
            self.processor.check_config(config)
            assert False
        except ValueError:
            assert True

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
        assert res_formats == ["CSV", "ZIP", "HTML", "GeoJSON"]


class TestKeepExistingResources:

    processor = KeepExistingResources

    def test_validation_correct_format(self):
        config = {
            "keep_existing_resources": True
        }
        try:
            self.processor.check_config(config)
        except ValueError:
            assert False

    def test_validation_wrong_format(self):
        config = {
            "keep_existing_resources": "true"
        }
        try:
            self.processor.check_config(config)
            assert False
        except ValueError:
            assert True
