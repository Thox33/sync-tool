import structlog
import typer

from sync_tool.configuration import load_configuration

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


# Main Application
cli = typer.Typer(no_args_is_help=True)
cli.add_typer(cli_config, name="configuration")

if __name__ == "__main__":
    cli()
