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


# Subcommand: Data
cli_data = typer.Typer(no_args_is_help=True)


@cli_data.command(name="get")
def data_get(
    sync_name: Annotated[str, typer.Argument(help="Name of the sync to get data for")],
    rule_name: Annotated[str, typer.Argument(help="Name of the rule to get the data for")],
    only_count: Annotated[bool, typer.Option(help="Only display count of items resolved not all items")] = False,
    map_data: Annotated[bool, typer.Option(help="Map all retrieved data to internal type")] = True,
    validate: Annotated[bool, typer.Option(help="Validate all retrieve data")] = True,
) -> None:
    if validate and not map_data:
        typer.echo("Validation requires mapping of data!")
        raise typer.Exit(code=1)

    typer.echo("Getting data...")

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
    internal_type = config.data.get_internal_type(rule.source.type)
    if not internal_type:
        typer.echo(f"Internal type '{rule.source.type}' not found in configuration.")
        raise typer.Exit(code=1)

    # Getting provider
    provider = config.get_provider(rule.source.provider)
    if provider is None:
        typer.echo(f"Provider '{rule.source.provider}' not found in configuration.")
        raise typer.Exit(code=1)

    # Prepare provider
    try:
        provider_instance = provider.make_instance()
        asyncio.run(provider_instance.init())
    except Exception as e:
        typer.echo(f"Could not initialize provider '{rule.source.provider}': {e}")
        raise typer.Exit(code=1)

    # Retrieve data based on sync rule source
    try:
        with Progress(
            SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True
        ) as progress:
            task = progress.add_task(f"Retrieving data for rule '{rule_name}'...", total=1)
            data = asyncio.run(provider_instance.get_data(item_type=rule.source.type, query=rule.source.query))
            progress.update(task, completed=1)
    except Exception as e:
        typer.echo(f"Could not retrieve data for rule '{rule_name}': {e}")
        raise typer.Exit(code=1)

    # Map data to internal type
    mapped_items = []
    if map_data:
        mapping_provider = config.get_mapping_provider(provider.provider)
        if mapping_provider is None:
            typer.echo(f"Mapping provider for provider '{rule.source.provider}' not found in configuration.")
            raise typer.Exit(code=1)

        mapping_exceptions = []
        for item in track(data, description="Mapping data..."):
            try:
                item = mapping_provider.map_raw_data(internal_type.name, item)
                mapped_items.append(item)
            except Exception as e:
                mapping_exceptions.append((item, e))
        if len(mapping_exceptions) > 0:
            for item, mapping_exception in mapping_exceptions:
                logger.error(f"Mapping failed for item '{item}': {mapping_exception}")

            typer.echo(f"Mapping failed for some items {len(mapping_exceptions)}!")
            raise typer.Exit(code=1)

    # Validate data and store in internal storage
    internal_storage = InternalTypeStorage(provider_name=rule.source.provider, internal_type=internal_type)
    if validate and map_data:
        validation_exceptions = []
        for item in track(mapped_items, description="Validating data..."):
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

    # Print data if not only count
    if not only_count and not validate:
        for item in data:
            typer.echo(item)
    if not only_count and validate:
        for item in internal_storage.get():
            typer.echo(item)

    typer.echo(f"Data retrieved for rule '{rule_name}': {len(data)} items")

    # Teardown provider
    try:
        asyncio.run(provider_instance.teardown())
    except Exception as e:
        typer.echo(f"Could not teardown provider '{rule.source.provider}': {e}")
        raise typer.Exit(code=1)


# Main Application
cli = typer.Typer(no_args_is_help=True)
cli.add_typer(cli_config, name="configuration")
cli.add_typer(cli_data, name="data")

if __name__ == "__main__":
    cli()
