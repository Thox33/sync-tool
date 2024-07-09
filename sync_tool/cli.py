import asyncio
from typing import Annotated

import structlog
import typer
from rich.progress import Progress, SpinnerColumn, TextColumn, track

from sync_tool.configuration import load_configuration
from sync_tool.core.data.data_store import InternalTypeStorage
from sync_tool.logging import configure_logging

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

    # Getting internal type
    internal_type = config.get_internal_type(rule.type)
    if internal_type is None:
        typer.echo(f"Internal type '{rule.type}' not found in configuration.")
        raise typer.Exit(code=1)

    # Getting source provider
    provider_source = config.get_provider(rule.source.provider)
    if provider_source is None:
        typer.echo(f"Provider '{rule.source.provider}' not found in configuration.")
        raise typer.Exit(code=1)
    # Prepare source provider
    try:
        provider_source_instance = provider_source.make_instance()
        asyncio.run(provider_source_instance.init())
    except Exception as e:
        typer.echo(f"Could not initialize provider '{rule.source.provider}': {e}")
        raise typer.Exit(code=1)

    # Getting destination provider
    provider_destination = config.get_provider(rule.destination.provider)
    if provider_destination is None:
        typer.echo(f"Provider '{rule.destination.provider}' not found in configuration.")
        raise typer.Exit(code=1)
    # Prepare destination provider
    try:
        provider_destination_instance = provider_destination.make_instance()
        asyncio.run(provider_destination_instance.init())
    except Exception as e:
        typer.echo(f"Could not initialize provider '{rule.destination.provider}': {e}")
        raise typer.Exit(code=1)

    # Retrieve data based on sync rule source
    try:
        with Progress(
            SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True
        ) as progress:
            task = progress.add_task(f"Retrieving data for rule '{rule_name}'...", total=1)
            source_data = asyncio.run(
                provider_source_instance.get_data(item_type=rule.source.mapping, query=rule.source.query)
            )
            progress.update(task, completed=1)
    except Exception as e:
        typer.echo(f"Could not retrieve data for rule '{rule_name}': {e}")
        raise typer.Exit(code=1)

    # Map source data to internal type
    mapped_source_items = []
    mapping_source_exceptions = []
    for item in track(source_data, description="Mapping data from source to internal storage format..."):
        try:
            item = provider_source.map_raw_data_to_internal_format(rule.source.mapping, item)
            mapped_source_items.append(item)
        except Exception as e:
            mapping_source_exceptions.append((item, e))
    if len(mapping_source_exceptions) > 0:
        for item, mapping_exception in mapping_source_exceptions:
            logger.error(f"Mapping failed for item '{item}': {mapping_exception}")

        typer.echo(f"Mapping failed for some items {len(mapping_source_exceptions)}!")
        raise typer.Exit(code=1)

    # Validate data and store in internal storage
    internal_storage = InternalTypeStorage(provider_name=rule.source.provider, internal_type=internal_type)
    validation_exceptions = []
    for item in track(mapped_source_items, description="Validating data..."):
        try:
            internal_storage.store_data(item)
        except Exception as e:
            validation_exceptions.append(e)
    if len(validation_exceptions) > 0:
        for validation_exception in validation_exceptions:
            logger.exception(validation_exception)
            if isinstance(validation_exception, ExceptionGroup):
                for exception in validation_exception.exceptions:
                    logger.error(exception)

        typer.echo(f"Validation failed for some items {len(validation_exceptions)}!")
        raise typer.Exit(code=1)

    typer.echo(f"Data retrieved for rule '{rule_name}': {len(source_data)} items")

    # Transform data of fields from one provider to another

    # Map data from internal storage format to external format of specific provider
    mapped_destination_items = []
    mapping_destination_exceptions = []
    for item in track(
        internal_storage.get(), description="Mapping data from internal storage to destination format..."
    ):
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
    for item in track(mapped_destination_items, description="Creating data..."):
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

    # Teardown providers
    try:
        asyncio.run(provider_destination_instance.teardown())
    except Exception as e:
        typer.echo(f"Could not teardown provider '{rule.destination.provider}': {e}")
    try:
        asyncio.run(provider_source_instance.teardown())
    except Exception as e:
        typer.echo(f"Could not teardown provider '{rule.source.provider}': {e}")
        raise typer.Exit(code=1)


# Main Application
cli = typer.Typer(no_args_is_help=True)
cli.add_typer(cli_config, name="configuration")
cli.add_typer(cli_sync, name="sync")

if __name__ == "__main__":
    cli()
