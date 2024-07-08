from copy import deepcopy
from typing import Any, Dict, List


def path_to_keys(path: str) -> List[str]:
    """Convert a path string to a list of keys.
    Will allow path to include dots inside of the keys by wrapping the part of the key inside of square brackets.
    """
    keys = path.split(".")
    new_keys = []
    concat_key = ""
    for key in keys:
        if "[" in key and "]" not in key:
            concat_key += key + "."
            continue
        elif "]" in key:
            concat_key += key
            key = concat_key.replace("[", "").replace("]", "")
            concat_key = ""
        new_keys.append(key)
    return new_keys


def get_field_data_by_path(data: Dict[str, Any], path: str) -> Any:
    """Get the data from a given path in a (possible) nested dict.
    Will allow path to include dots inside of the keys by wrapping the part of the key inside of square brackets.
    """

    keys = path_to_keys(path)
    current_data = data

    try:
        for key in keys:
            current_data = current_data[key]

        return current_data
    except KeyError:
        return None


def add_field_data_by_path(data: Dict[str, Any], path: str, value: Any) -> Dict[str, Any]:
    """Recursive add data to a given path in a (possible) nested dict.
    Will allow path to include dots inside of the keys by wrapping the part of the key inside of square brackets.
    """

    if not isinstance(data, dict):
        raise ValueError("Data must be a dictionary.")

    keys = path_to_keys(path)
    original_data = deepcopy(data)
    current_data = original_data

    try:
        for key in keys[:-1]:
            if key not in current_data:
                current_data[key] = {}
            current_data = current_data[key]
        current_data[keys[-1]] = value
    except KeyError:
        pass

    return original_data
