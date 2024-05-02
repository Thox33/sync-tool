from typing import Any, Dict


def get_field_data_by_path(data: Dict[str, Any], path: str) -> Any:
    """Get the data from a given path in a (possible) nested dict."""
    keys = path.split(".")
    current_data = data

    try:
        for key in keys:
            current_data = current_data[key]

        return current_data
    except KeyError:
        return None
