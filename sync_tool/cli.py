import asyncio
from typing import Annotated

import structlog
import typer
from rich.progress import Progress, SpinnerColumn, TextColumn

from sync_tool.configuration import load_configuration
from sync_tool.logging import configure_logging
from sync_tool.sync_controller import SyncController

# setup loggers
configure_logging(is_console=True)

logger = structlog.getLogger(__name__)

# Subcommand: Configuration
cli_config = typer.Typer(no_args_is_help=True)


@cli_config.command(name="validate")
def configuration_validate() -> None:
    typer.echo("Validating configuration...")
    # Validate configuration
    try:
        config = load_configuration()
        typer.echo(f"Loaded configuration: {config.model_dump_json(indent=2)}")
        typer.echo("Configuration is valid!")
    except Exception as e:
        typer.echo(f"Configuration is invalid: {e}")
        raise typer.Exit(code=1)


# Subcommand: Sync
cli_sync = typer.Typer(no_args_is_help=True)


@cli_sync.command(name="validate")
def data_get(
    sync_name: Annotated[str, typer.Argument(help="Name of the sync to validate")],
    rule_name: Annotated[str, typer.Argument(help="Name of the rule to validate")],
    dry_run: Annotated[bool, typer.Option(help="Do not create synced data in destination provider")] = True,
) -> None:
    typer.echo("Validating sync rule...")

    # Load configuration
    try:
        config = load_configuration()
    except Exception as e:
        typer.echo(f"Configuration is invalid: {e}")
        raise typer.Exit(code=1)

    # Getting sync configuration
    sync = config.get_sync(sync_name)
    if sync is None:
        typer.echo(f"Sync '{sync_name}' not found in configuration.")
        raise typer.Exit(code=1)

    # Getting sync rule
    rule = sync.get_rule(rule_name)
    if rule is None:
        typer.echo(f"Rule '{rule_name}' not found in sync '{sync_name}'.")
        raise typer.Exit(code=1)

    # Setup sync controller
    sync_controller = SyncController(configuration=config, sync_rule=rule)

    # Prepare sync controller
    try:
        with Progress(
            SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True
        ) as progress:
            task = progress.add_task(f"Preparing sync controller for '{rule_name}'...", total=1)
            asyncio.run(sync_controller.init())
            progress.update(task, completed=1)
    except Exception as e:
        typer.echo(f"Could not prepare sync controller for rule '{rule_name}': {e}")
        raise typer.Exit(code=1)

    # Perform sync using sync controller
    try:
        with Progress(
            SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True
        ) as progress:
            task = progress.add_task(f"Syncing data for '{rule_name}'...", total=1)
            asyncio.run(sync_controller.sync(dry_run=dry_run))
            progress.update(task, completed=1)
    except Exception as e:
        typer.echo(f"Could not sync data for rule '{rule_name}': {e}")

    """

    # Prepare destination internal storage
    internal_storage_destination = InternalTypeStorage(
        provider=provider_destination_instance, internal_type=internal_type
    )

    # Create data store to handle data checks
    data_store = DataStore()
    data_store.add_storage(storage=internal_storage_source, storage_type=DataStore.StorageType.SOURCE)
    data_store.add_storage(storage=internal_storage_destination, storage_type=DataStore.StorageType.DESTINATION)
    if not data_store.is_ready():
        typer.echo("Data store is not ready!")
        raise typer.Exit(code=1)

    # Get items to be created
    items_to_be_created = data_store.get_items_to_be_created()
    typer.echo(f"Items to be created: {len(items_to_be_created)}")

    # Transform data of fields from one provider to another

    # Map data from internal storage format to external format of specific provider
    mapped_destination_items = []
    mapping_destination_exceptions = []
    for item in track(items_to_be_created, description="Mapping data from internal storage to destination format..."):
        try:
            item = provider_destination.map_internal_data_to_raw_format(rule.destination.mapping, item)
            mapped_destination_items.append(item)
        except Exception as e:
            mapping_destination_exceptions.append((item, e))
    if len(mapping_destination_exceptions) > 0:
        for item, mapping_exception in mapping_destination_exceptions:
            logger.error(f"Mapping failed for item '{item}': {mapping_exception}")

        typer.echo(f"Mapping failed for some items {len(mapping_destination_exceptions)}!")
        raise typer.Exit(code=1)

    # Create data in destination provider
    creating_destination_exceptions = []
    for item in track(mapped_destination_items, description=f"Creating data{' (dry run)' if dry_run else ''}..."):
        try:
            asyncio.run(
                provider_destination_instance.create_data(
                    item_type=rule.destination.mapping, query=rule.destination.query, data=item, dry_run=dry_run
                )
            )
        except Exception as e:
            creating_destination_exceptions.append((item, e))
    if len(creating_destination_exceptions) > 0:
        for item, creating_exception in creating_destination_exceptions:
            logger.error(f"Creating failed for item '{item}': {creating_exception}")

        typer.echo(f"Creating failed for some items {len(creating_destination_exceptions)}!")
        raise typer.Exit(code=1)

    """

    # Teardown providers
    try:
        asyncio.run(sync_controller.teardown())
    except Exception:
        typer.echo("Could not teardown sync controller")
        raise typer.Exit(code=1)


# Main Application
cli = typer.Typer(no_args_is_help=True)
cli.add_typer(cli_config, name="configuration")
cli.add_typer(cli_sync, name="sync")

if __name__ == "__main__":
    cli()
