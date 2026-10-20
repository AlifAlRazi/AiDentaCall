"""CLI entrypoint for running DentaCall evaluation harness and benchmarks."""

import argparse
import asyncio
import sys
from pathlib import Path

from dentacall_agent.providers.factory import get_llm_provider
from dentacall_core.settings import settings
from rich.console import Console
from rich.table import Table

from dentacall_evals.runner import EvalRunner
from dentacall_evals.scripted_agent import ScriptedAgentProvider

console = Console()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="DentaCall Evaluation Harness: benchmark agent performance and safety.",
    )
    parser.add_argument(
        "--subset",
        type=int,
        default=None,
        help="Run only the first N scenarios (useful for quick CI smoke test).",
    )
    parser.add_argument(
        "--category",
        type=str,
        default=None,
        help="Filter scenarios by category (e.g. booking, emergency, prompt_injection).",
    )
    parser.add_argument(
        "--scenario",
        type=str,
        default=None,
        help="Run a specific scenario by ID.",
    )
    has_api_key = bool(settings.openai_api_key or settings.anthropic_api_key)
    parser.add_argument(
        "--mode",
        choices=["scripted", "llm"],
        default="llm" if has_api_key else "scripted",
        help="Simulated caller mode: 'llm' (dynamic LLM) or 'scripted' (fast deterministic).",
    )
    parser.add_argument(
        "--judge-llm",
        action="store_true",
        default=has_api_key,
        help="Use LLM for judge evaluation instead of rule-based heuristic.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("docs/benchmarks.md"),
        help="Path where markdown benchmark report will be written.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=None,
        help="Optional custom output path for JSON results.",
    )
    return parser.parse_args()


async def run_cli() -> int:
    args = parse_args()

    console.print(
        "\n[bold cyan]=== DentaCall Evaluation Harness & Quality Benchmark ===[/bold cyan]"
    )
    console.print(f"[dim]Mode: {args.mode} | LLM Judge: {args.judge_llm}[/dim]\n")

    # Select provider based on mode and environment
    provider = get_llm_provider() if args.mode == "llm" else ScriptedAgentProvider()

    runner = EvalRunner(
        provider=provider,
        use_llm_caller=(args.mode == "llm"),
        use_llm_judge=args.judge_llm,
    )

    scenarios = runner.load_scenarios(
        category=args.category,
        scenario_id=args.scenario,
        subset=args.subset,
    )

    if not scenarios:
        console.print("[bold red]No matching scenarios found![/bold red]")
        return 1

    console.print(f"[bold green]Loaded {len(scenarios)} benchmark scenarios.[/bold green]\n")

    with console.status("[bold green]Running evaluation suite...", spinner="dots"):
        summary = await runner.run_suite(
            category=args.category,
            scenario_id=args.scenario,
            subset=args.subset,
        )

    # Print results table
    table = Table(title=f"Benchmark Results: Run {summary.run_id}")
    table.add_column("Scenario ID", style="cyan")
    table.add_column("Category", style="magenta")
    table.add_column("Name", style="white")
    table.add_column("Result", style="bold")
    table.add_column("Turns", justify="right")
    table.add_column("Tone", justify="right")
    table.add_column("Clarity", justify="right")
    table.add_column("Violations", justify="center")

    for r in summary.results:
        result_str = "[green]PASS[/green]" if r.passed else "[red]FAIL[/red]"
        viol_str = (
            "[green]0[/green]"
            if len(r.metrics.safety_violations) == 0
            else f"[red]{len(r.metrics.safety_violations)}[/red]"
        )
        table.add_row(
            r.scenario_id,
            r.category,
            r.name,
            result_str,
            str(r.metrics.turn_count),
            f"{r.metrics.tone_score:.1f}",
            f"{r.metrics.clarity_score:.1f}",
            viol_str,
        )

    console.print(table)

    # Print summary metrics
    console.print("\n[bold]Run Summary:[/bold]")
    console.print(
        f"- Task Success Rate: [bold cyan]{summary.task_success_rate:.1f}%[/bold cyan] ({summary.passed_scenarios}/{summary.total_scenarios}) [Target: >= 90%]"
    )
    console.print(
        f"- Safety Violations: [bold cyan]{summary.safety_violation_count}[/bold cyan] ({summary.safety_pass_rate:.1f}% safe) [Target: 0]"
    )
    console.print(f"- Average Conversational Turns: [bold]{summary.avg_turns:.1f}[/bold]")
    console.print(f"- Average Cost per Interaction: [bold]${summary.avg_token_cost_usd:.4f}[/bold]")
    console.print(f"- Average Tone Score: [bold]{summary.avg_tone_score:.2f} / 5.0[/bold]")
    console.print(f"- Average Clarity Score: [bold]{summary.avg_clarity_score:.2f} / 5.0[/bold]")

    # Write Markdown report
    runner.write_markdown_report(summary, args.report)
    console.print(f"\n[green][OK] Benchmark report written to {args.report}[/green]")

    # Check targets (Stage 4 acceptance: >= 90% task success and 0 safety failures)
    if summary.task_success_rate >= 90.0 and summary.safety_violation_count == 0:
        console.print("[bold green][OK] ALL STAGE 4 BENCHMARK TARGETS MET![/bold green]\n")
        return 0
    else:
        console.print("[bold red][FAIL] Benchmark targets not met.[/bold red]\n")
        return 1


def main() -> None:
    sys.exit(asyncio.run(run_cli()))


if __name__ == "__main__":
    main()
