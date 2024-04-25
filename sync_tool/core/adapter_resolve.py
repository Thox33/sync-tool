from importlib.metadata import entry_points
from typing import Type

from sync_tool.constants import ADAPTER_ENTRYPOINT_GROUP
from sync_tool.core.adapter_base import AdapterBase


def adapter_resolve(adapter_entry_point_name: str) -> Type[AdapterBase]:
    """Resolve adapter by entry point name.

    Will be used while validating the adapter configurations to import the adapter code
    and validate its options. Additionally used before creating a new adapter object to import the adapter code.

    Args:
        adapter_entry_point_name (str): Entry point name.

    Returns:
        Type[AdapterBase]: Imported adapter class to create new objects with.

    Raises:
        TypeError: If adapter_entry_point_name is not a string.
        ValueError: If adapter_entry_point_name is empty.
        ValueError: If adapter could not be resolved.

    .. code-block:: python

        from sync_tool.adapter_base import adapter_resolve

        adapter = adapter_resolve("detectomat.sync-tool.adapters:TestingAdapter")
    """

    if not isinstance(adapter_entry_point_name, str):
        raise TypeError("adapter_entry_point_name must be a string.")
    if adapter_entry_point_name == "":
        raise ValueError("adapter_entry_point_name must not be empty.")

    # Resolve adapter by entry point name and import it.
    adapter = None
    points = entry_points(group=ADAPTER_ENTRYPOINT_GROUP)
    for point in points:
        if point.name == adapter_entry_point_name:
            adapter = point.load()
            break
    if adapter is None:
        raise ValueError(f"Could not resolve adapter '{adapter_entry_point_name}'.")
    return adapter
