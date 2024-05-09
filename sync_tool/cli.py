import asyncio
from typing import Annotated

import structlog
import typer

from sync_tool.configuration import load_configuration
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
) -> None:
    typer.echo("Getting data...")

    # Load configuration
    config = None
    try:
        config = load_configuration()
    except Exception as e:
        typer.echo(f"Configuration is invalid: {e}")
        raise typer.Exit(code=1)

    # Getting sync rule
    sync = config.get_sync(sync_name)
    if sync is None:
        typer.echo(f"Sync '{sync_name}' not found in configuration.")
        raise typer.Exit(code=1)

    # Getting sync rule
    rule = sync.get_rule(rule_name)
    if rule is None:
        typer.echo(f"Rule '{rule_name}' not found in sync '{sync_name}'.")
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
        typer.echo(f"Retrieving data for rule '{rule_name}'...")
        data = asyncio.run(provider_instance.get_data(item_type=rule.source.type, query=rule.source.query))
        if not only_count:
            logger.info(data)
        typer.echo(f"Data retrieved for rule '{rule_name}': {len(data)} items")
    except Exception as e:
        typer.echo(f"Could not retrieve data for rule '{rule_name}': {e}")
        raise typer.Exit(code=1)

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
