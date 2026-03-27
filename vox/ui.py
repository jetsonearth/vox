"""Terminal UI helpers (Rich)."""

from __future__ import annotations

import sys
import time
from collections.abc import Callable
from contextlib import contextmanager
from typing import Generator

_console = None


def get_console():
    global _console
    if _console is None:
        from rich.console import Console

        _console = Console(highlight=False, soft_wrap=True)
    return _console


def esc(s: str) -> str:
    from rich.markup import escape

    return escape(s)


def section(title: str) -> None:
    from rich.panel import Panel
    from rich.text import Text

    t = Text(title, style="bold white")
    get_console().print()
    get_console().print(Panel.fit(t, border_style="cyan", padding=(0, 2)))


def muted(text: str) -> None:
    get_console().print(f"  [dim]{esc(text)}[/dim]")


def info(text: str) -> None:
    get_console().print(f"  [cyan]›[/cyan] {esc(text)}")


def recording_hint() -> None:
    get_console().print("  [cyan]›[/cyan] [bold]Recording…[/bold] [dim](press Enter to stop)[/dim]")


def format_elapsed(seconds: float) -> str:
    """Format elapsed seconds as human-readable string."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    secs = seconds % 60
    if minutes < 60:
        return f"{minutes}m {secs:04.1f}s"
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}h {mins}m {secs:04.1f}s"


def ok(text: str, elapsed: float | None = None) -> None:
    suffix = f" [dim]({format_elapsed(elapsed)})[/dim]" if elapsed is not None else ""
    get_console().print(f"  [green]✓[/green] {esc(text)}{suffix}")


def warn(text: str) -> None:
    get_console().print(f"  [yellow]![/yellow] {esc(text)}")


def err(text: str) -> None:
    get_console().print(f"  [red]✗[/red] {esc(text)}")


def label_value(label: str, value: str) -> None:
    get_console().print(f"  [dim]{esc(label)}:[/dim] [bright_white]{esc(value)}[/bright_white]")


def speakers_intro(count: int) -> None:
    get_console().print()
    get_console().print(
        f"  [bold white]Found {count} speaker(s)[/bold white] [dim]in transcript[/dim]"
    )
    get_console().print(
        "  [dim]Type[/dim] [bold]q[/bold] [dim]at a name prompt to stop here — "
        "this speaker and all later ones keep Soniox labels (Speaker N).[/dim]\n"
    )


def banner_subtitle(subtitle: str) -> None:
    from rich.text import Text

    line = Text()
    line.append("vox", style="bold cyan")
    line.append("  ")
    line.append(esc(subtitle), style="dim")
    get_console().print(line)
    get_console().print()


def panel_done(title: str, rows: list[tuple[str, str]], analysis_ok: bool, total_elapsed: float | None = None) -> None:
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column(style="dim", justify="right", width=14)
    table.add_column()
    for k, v in rows:
        table.add_row(k, Text(esc(v), style="white"))
    if analysis_ok:
        table.add_row("Analysis", Text("included", style="green"))
    else:
        table.add_row(
            "Analysis",
            Text("skipped", style="yellow") + Text(" (add manually or re-run)", style="dim"),
        )
    if total_elapsed is not None:
        table.add_row("Total time", Text(format_elapsed(total_elapsed), style="bold cyan"))
    get_console().print()
    get_console().print(
        Panel(
            table,
            title=Text(esc(title), style="bold green"),
            border_style="green",
            padding=(1, 2),
        )
    )


def init_header() -> None:
    from rich.panel import Panel
    from rich.text import Text

    t = Text()
    t.append("Vox", style="bold cyan")
    t.append(" setup", style="bold white")
    get_console().print(Panel.fit(t, border_style="cyan", subtitle="Voice → vault pipeline"))


@contextmanager
def spinner(message: str) -> Generator[None, None, None]:
    c = get_console()
    if not sys.stdout.isatty():
        c.print(f"  [cyan]…[/cyan] {esc(message)}")
        yield
        return
    with c.status(f"[bold cyan]{esc(message)}[/bold cyan]", spinner="dots12", speed=0.8):
        yield


@contextmanager
def timed_spinner(message: str) -> Generator[Callable[[], float], None, None]:
    """Spinner with elapsed time display. Yields a callable that returns elapsed seconds."""
    t0 = time.monotonic()

    def elapsed() -> float:
        return time.monotonic() - t0

    c = get_console()
    if not sys.stdout.isatty():
        c.print(f"  [cyan]…[/cyan] {esc(message)}")
        yield elapsed
        return

    from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

    with Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        TimeElapsedColumn(),
        console=c,
        transient=True,
        refresh_per_second=4,
    ) as progress:
        progress.add_task(f"[bold cyan]{esc(message)}[/bold cyan]", total=None)
        yield elapsed


@contextmanager
def soniox_poll_progress(
    initial_message: str,
) -> Generator[Callable[[str], None], None, None]:
    """Indeterminate progress line for long Soniox polls.

    Rich ``Status`` spinners can stop redrawing after a few minutes on some
    terminals; ``Progress`` + periodic ``refresh`` stays visible. Yields a
    ``set_status(text: str)`` callback to update the label each poll.
    """
    c = get_console()
    if not sys.stdout.isatty():
        c.print(f"  [cyan]…[/cyan] {esc(initial_message)}")

        def noop(_t: str = "") -> None:
            pass

        yield noop
        return

    from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

    with Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        TimeElapsedColumn(),
        console=c,
        transient=True,
        refresh_per_second=4,
    ) as progress:
        tid = progress.add_task(f"[bold cyan]{esc(initial_message)}[/bold cyan]", total=None)

        def set_status(text: str) -> None:
            progress.update(tid, description=f"[bold cyan]{esc(text)}[/bold cyan]")
            progress.refresh()

        yield set_status


def speaker_block(label: str, quote: str) -> None:
    from rich.panel import Panel
    from rich.text import Text

    c = get_console()
    w = c.width
    panel_w = min(88, w - 2) if w else 88
    body = Text(esc(label), style="bold")
    body.append("\n")
    body.append(esc(quote), style="dim")
    c.print(Panel(body, border_style="blue", padding=(0, 1), width=panel_w))
