from typing import Annotated

import typer

from memsnapdump import __version__
from memsnapdump.tools.adaptors.snapshot2db import run_dump_to_db
from memsnapdump.tools.slice_dump.dump import run_slice_dump

HELP_OPTION_NAMES = {"help_option_names": ["-h", "--help"]}

app = typer.Typer(
    help="MemSnapDump command line tools.",
    context_settings=HELP_OPTION_NAMES,
)


def version_callback(value: bool):
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def main_callback(
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            help="Show version and exit.",
            callback=version_callback,
            is_eager=True,
        ),
    ] = None,
):
    return None


@app.command(context_settings=HELP_OPTION_NAMES)
def split(
    snapshot_file: str,
    device: Annotated[
        int, typer.Option("--device", "-d", min=0, help="Device id.")
    ] = 0,
    slices: Annotated[
        int,
        typer.Option("--slices", "-s", min=1, help="Number of output slices."),
    ] = 4,
    max_entries: Annotated[
        int,
        typer.Option(
            "--max-entries",
            "-m",
            help="Maximum entries per dump file.",
        ),
    ] = 15000,
    dump_dir: Annotated[
        str, typer.Option("--dump-dir", "-o", help="Output directory.")
    ] = "",
    dump_type: Annotated[
        str, typer.Option("--dump-type", "-t", help="Output format: pkl or json.")
    ] = "pkl",
):
    run_slice_dump(
        snapshot_file=snapshot_file,
        device=device,
        slices=slices,
        max_entries=max_entries,
        dump_dir=dump_dir,
        dump_type=dump_type,
    )


@app.command("dump2db", context_settings=HELP_OPTION_NAMES)
def dump2db(
    snapshot_file: str,
    dump_dir: Annotated[
        str, typer.Option("--dump-dir", "-o", help="Output directory.")
    ] = "",
    log_file: Annotated[str, typer.Option("--log", "-l", help="Log file path.")] = "",
    device: Annotated[
        int | None,
        typer.Option("--device", "-d", min=0, help="Specific device id."),
    ] = None,
):
    ok = run_dump_to_db(
        snapshot_file=snapshot_file,
        dump_dir=dump_dir,
        device=device,
        log_file=log_file,
    )
    if not ok:
        raise typer.Exit(code=1)


def main():
    app()


if __name__ == "__main__":
    main()
