from typing import Any, Dict


def get_field_data_by_path(data: Dict[str, Any], path: str) -> Any:
    """Get the data from a given path in a (possible) nested dict.
    Will allow path to include dots inside of the keys by wrapping the part of the key inside of square brackets.
    """

    keys = path.split(".")
    current_data = data

    try:
        concat_key = ""  # This will be used to store the key with dots inside of it
        for key in keys:
            print(key, concat_key)
            if "[" in key and "]" not in key:
                concat_key += key + "."
                continue
            elif "]" in key:
                concat_key += key
                key = concat_key.replace("[", "").replace("]", "")
                concat_key = ""
            current_data = current_data[key]

        return current_data
    except KeyError:
        return None
