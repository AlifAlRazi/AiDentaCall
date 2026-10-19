"""Interactive terminal chat interface for talking to DentaCall Agent."""

import asyncio
import sys

from dentacall_core.settings import settings
from dentacall_core.timezone import format_dublin, now_utc, to_dublin
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from dentacall_agent.agent import DentaCallAgent
from dentacall_agent.providers.factory import get_llm_provider

console = Console()


async def run_cli() -> None:
    """Run interactive text chat loop with DentaCall Agent."""
    dublin_time = format_dublin(to_dublin(now_utc()), "%A, %d %B %Y at %H:%M %Z")

    console.print(
        Panel.fit(
            f"[bold cyan]🦷 Grand Canal Dental Clinic — AI Receptionist[/bold cyan]\n"
            f"[dim]Dublin Time: {dublin_time}[/dim]\n"
            f"[dim]Provider: {settings.default_llm_provider} | API Base: {settings.api_base_url}[/dim]\n\n"
            f"Commands: [yellow]/reset[/yellow] to restart, [yellow]/state[/yellow] for session details, [yellow]/exit[/yellow] to quit.",
            border_style="cyan",
            title="DentaCall Text Agent",
        )
    )

    try:
        provider = get_llm_provider()
    except Exception as exc:
        console.print(f"[bold red]Configuration error: {exc}[/bold red]")
        console.print(
            "[dim]Set OPENAI_API_KEY or ANTHROPIC_API_KEY in your .env file to chat with live LLM.[/dim]"
        )
        return

    agent = DentaCallAgent(provider=provider)

    with console.status("[italic cyan]Connecting to Grand Canal Dental Clinic...[/italic cyan]"):
        greeting = await agent.start_call()

    console.print(f"\n[bold green]Receptionist:[/bold green] {greeting}\n")

    while True:
        try:
            user_input = Prompt.ask("[bold blue]You[/bold blue]").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Call ended by caller.[/dim]")
            break

        if not user_input:
            continue

        if user_input.lower() in ("/exit", "/quit", "exit", "quit"):
            console.print("[dim]Goodbye from Grand Canal Dental Clinic![/dim]")
            break

        if user_input.lower() == "/reset":
            agent = DentaCallAgent(provider=provider)
            with console.status("[italic cyan]Starting new call...[/italic cyan]"):
                greeting = await agent.start_call()
            console.print(f"\n[bold green]Receptionist:[/bold green] {greeting}\n")
            continue

        if user_input.lower() == "/state":
            st = agent.state
            console.print(
                Panel.fit(
                    f"Call ID: {st.call_id}\n"
                    f"Caller Phone: {st.caller_phone}\n"
                    f"Caller Name: {st.caller_name}\n"
                    f"Patient ID: {st.patient_id}\n"
                    f"Active Hold ID: {st.active_hold_id}\n"
                    f"Turn Count: {st.turn_count}",
                    title="Conversation State",
                    border_style="yellow",
                )
            )
            continue

        with console.status("[italic cyan]Receptionist is typing/calling tools...[/italic cyan]"):
            response = await agent.step(user_input)

        console.print(f"\n[bold green]Receptionist:[/bold green] {response}\n")


def main() -> None:
    """Entry point for dentacall-chat script."""
    try:
        asyncio.run(run_cli())
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
