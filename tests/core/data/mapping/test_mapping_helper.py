from sync_tool.core.data.mapping.mapping_helper import get_field_data_by_path


def test_get_field_data_by_path_simple_dict():
    data = {"key": "value"}
    path = "key"
    assert get_field_data_by_path(data, path) == "value"


def test_get_field_data_by_path_simple_nested_dict():
    data = {"key1": {"key2": "value"}}
    path = "key1.key2"
    assert get_field_data_by_path(data, path) == "value"


def test_get_field_data_by_path_deeper_nested_dict():
    data = {"key1": {"key2": {"key3": "value"}}}
    path = "key1.key2.key3"
    assert get_field_data_by_path(data, path) == "value"


def test_get_field_data_by_path_non_existing_key():
    data = {"key1": {"key2": "value"}}
    path = "key1.key3"
    assert get_field_data_by_path(data, path) is None


def test_get_field_data_by_path_empty_path():
    data = {"key1": "value"}
    path = ""
    assert get_field_data_by_path(data, path) is None


def test_get_field_data_by_path_with_dots_in_keys():
    data = {"key1.key2": "value"}
    path = "[key1.key2]"
    assert get_field_data_by_path(data, path) == "value"


def test_get_field_data_by_path_with_dots_in_keys_nested():
    data = {"other": {"key1.key2": "value"}}
    path = "other.[key1.key2]"
    assert get_field_data_by_path(data, path) == "value"


def test_get_field_data_by_path_with_dots_in_keys_nested_alternative():
    data = {"key1.key2": {"other": "value"}}
    path = "[key1.key2].other"
    assert get_field_data_by_path(data, path) == "value"


def test_get_field_data_by_path_with_real_data():
    data = {
        "id": 9608,
        "documentKey": "DP1001-SRQ-20",
        "globalId": "GID-55962",
        "itemType": 86,
        "project": 53,
        "createdDate": "2024-04-03T11:18:23.000+0000",
        "modifiedDate": "2024-04-15T09:39:52.000+0000",
        "lastActivityDate": "2024-04-15T09:39:52.000+0000",
        "createdBy": 15,
        "modifiedBy": 15,
        "fields": {
            "documentKey": "DP1001-SRQ-20",
            "globalId": "GID-55962",
            "name": "Input definitions BBM in DPT for fiber optic converters",
            "object$86": "DC3500 in CON-Xnet",
            "priority": 300,
            "description": "<p>The input definitions of the basis board module in the DPT must be extended.</p>\n\n<p>"
            'There should be a new column next to the column "Comments" with the designation "Info / Technical '
            'alarm" ("Info / Technischer Alarm").</p>\n\n<p>&nbsp;</p>\n\n<p>Underneath this designation field '
            "there should be a combo-box with the following information in there:</p>\n\n<p><span>-"
            '<span style="width:14.39pt"> </span></span>"Info message (Without panel LED activation)"'
            ' ("Infomeldung (Ohne Aktivierung Zentralen-LED")) <span style="font-family:Wingdings">'
            '\uf0e0</span> default</p>\n\n<p><span>-<span style="width:14.39pt"> </span></span>"Technical'
            ' Alarm as Fault with auto reset" ("Technischer Alarm als Störung mit Autoreset")<br />\n<span '
            'style="font-family:Wingdings">\uf0e0</span> relevant setting for VLV / GHDC</p>\n\n<p>&nbsp;</p>'
            '\n\n<p><img alt="see attached image: Aspose.Words.5859951f-aa7c-4685-8079-674a52d3b367.008.png"'
            ' height="256" src="https://detectomat-prod.jamacloud.com/attachment/264/Aspose.Words.5859951f'
            '-aa7c-4685-8079-674a52d3b36 7.008.png" width="539" /></p>\n\n<p>&nbsp;</p>\n\n<p>&nbsp;</p>'
            '\n\n<p><a href="https://detectomat-prod.jamacloud.com/perspective.req?projectId=53&amp;docId=9609"'
            ' target="_blank">Relates to: </a><a href="https://detectomat-prod.jamacloud.com/perspective.req?'
            'docId=9609&amp;projectId=53">8234522-SRQ-21</a><a href="https://detectomat-prod.jamacloud.com/'
            "perspective.req?"
            'projectId=53&amp;docId=9609" target="_blank"> </a><a href="https://detectomat-prod.jamacloud.com/'
            'perspective.req?projectId=53&amp;docId=9609" target="_blank">Input definitions BBM on '
            "Panel and FCP display</a></p>\n",
            "notessources$86": "<p>CDC_VLV-GHDC_150.1</p>",
            "testable$86": 619,
            "assignedTo": 15,
            "release": 75,
            "status": 293,
        },
        "resources": {"self": {"allowed": ["GET", "PUT", "PATCH", "DELETE"]}},
        "location": {"sortOrder": 0, "globalSortOrder": 894784800, "sequence": "2.1.1.1.1", "parent": {"item": 9644}},
        "lock": {"locked": False, "lastLockedDate": "2024-04-15T09:39:53.000+0000"},
        "type": "items",
    }
    path = "fields.name"
    assert get_field_data_by_path(data, path) == "Input definitions BBM in DPT for fiber optic converters"
