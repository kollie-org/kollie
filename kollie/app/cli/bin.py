#!/usr/bin/env python3
import typer

from kollie.cluster.authentication import connect_to_cluster
from kollie.cluster.image_update_automation import watch_for_image_updates
from kollie.heartbeat import start_heartbeat
from kollie.logging_config import configure_logger
from kollie.service import envs

app = typer.Typer()


@app.command()
def reconcile(
    heartbeat: bool = typer.Option(
        False, "--heartbeat", help="Start a heartbeat thread"
    )
):
    if heartbeat:
        start_heartbeat()

    watch_for_image_updates()


@app.command()
def active_envs():
    for env in envs.list_envs():
        typer.echo(env)


@app.command()
def rebuild_env_configs():
    envs.rebuild_configs()


if __name__ == "__main__":
    configure_logger()
    connect_to_cluster()
    app()
