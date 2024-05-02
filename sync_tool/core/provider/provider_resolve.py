from importlib.metadata import entry_points
from typing import Type

from sync_tool.contants import PROVIDER_ENTRYPOINT_GROUP
from sync_tool.core.provider.provider_base import ProviderBase


def provider_resolve(
    provider_entry_point_name: str, provider_entrypoint_group: str = PROVIDER_ENTRYPOINT_GROUP
) -> Type[ProviderBase]:
    """Resolve provider by entry point name.

    Will be used while validating the provider configurations to import the provider code
    and validate its options. Additionally used before creating a new provider object to import the provider code.

    Args:
        provider_entry_point_name (str): Entry point name.
        provider_entrypoint_group (str): Entry point group name. Default is 'sync.tool.provider'.

    Returns:
        Type[ProviderBase]: Imported provider class to create new objects with.

    Raises:
        TypeError: If provider_entry_point_name is not a string.
        ValueError: If provider_entry_point_name is empty.
        ValueError: If provider could not be resolved.

    .. code-block:: python

        from sync-tool.core.provider import provider_resolve

        adapter = adapter_resolve("sync-tool.provider.testing:TestingProvider")
    """

    if not isinstance(provider_entry_point_name, str):
        raise TypeError("provider_entry_point_name must be a string.")
    if provider_entry_point_name == "":
        raise ValueError("provider_entry_point_name must not be empty.")

    # Resolve provider by entry point name and import it.
    provider = None
    points = entry_points(group=provider_entrypoint_group)
    for point in points:
        if point.name == provider_entry_point_name:
            provider = point.load()
            break
    if provider is None:
        raise ValueError(f"Could not resolve provider '{provider_entry_point_name}'.")
    return provider
