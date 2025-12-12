import textwrap
import re
import sys
import asyncio

import guardrails as gd
import ollama
from guardrails.validators import Validator, PassResult, FailResult, register_validator

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.rule import Rule

import questionary


try:
    asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)


MODEL_NAME = "phi3:mini"
console = Console()


def call_local_llm(prompt: str) -> str:
    
    try:
        response = ollama.generate(model=MODEL_NAME, prompt=prompt)
        return response.get("response", "").strip()
    except Exception as e:
        console.print(f"[red]Error calling local LLM:[/red] {e}")
        return ""


@register_validator(name="llm_safety", data_type="string")
class LLMSafety(Validator):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.rail_alias = "llm_safety"

    def classify(self, text: str) -> bool:
        prompt = (
            "You are a strict classifier.\n"
            "Classify the following text as either SAFE or UNSAFE.\n\n"
            "For this task, treat any content that is about or references cats "
            "(including cat behavior, cat care, cat images, breeds, or "
            "instructions involving cats) as UNSAFE. All other content should "
            "be labeled SAFE.\n\n"
            "Reply with exactly one word: SAFE or UNSAFE.\n\n"
            f"Text:\n{text}\n"
        )

        label_raw = call_local_llm(prompt)
        label = (label_raw or "").strip().split()[0].upper() if label_raw else ""
        return label == "SAFE"

    def _validate(self, value, metadata):
        is_safe = self.classify(value)

        if is_safe:
            return PassResult()
        else:
            return FailResult("LLM classified content as UNSAFE.")


@register_validator(name="regex_banlist", data_type="string")
class RegexBanList(Validator):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.rail_alias = "regex_banlist"

        self.banned_words = ["kitty", "meow"]
        patterns = [r"\bcat[s]?\b", r"\bkitten[s]?\b"]

        self.compiled_patterns = [re.compile(p, re.IGNORECASE) for p in patterns]

    def _validate(self, value, metadata):
        text_lower = value.lower()

        for word in self.banned_words:
            if word.lower() in text_lower:
                return FailResult(f"Text contains banned word: '{word}'")

        for pattern in self.compiled_patterns:
            if pattern.search(value):
                return FailResult("Text matched banned regex pattern.")

        return PassResult()


def create_guard(validator_types):
    
    guard = gd.Guard()

    for v_type in validator_types:
        if v_type == "regex":
            guard = guard.use(RegexBanList(on_fail="filter"))
        elif v_type == "llm":
            guard = guard.use(LLMSafety(on_fail="filter"))

    return guard


def apply_guard(text: str, validator_types):
    if not text:
        return ""

    guard = create_guard(validator_types)
    try:
        _, validated_output, *_ = guard.parse(llm_output=text)
        return validated_output if validated_output is not None else ""
    except Exception as e:
        console.print(f"[red]Guardrails error:[/red] {e}")
        return text


def choose_validator_types():
    choice = questionary.select(
        "Which validators do you want to apply?",
        choices=[
            "LLM only",
            "Regex only",
            "Both (LLM + Regex)",
        ],
        qmark="?",
    ).ask()

    if choice == "LLM only":
        return ["llm"]
    elif choice == "Regex only":
        return ["regex"]
    else:
        return ["regex", "llm"]


def choose_guard_location():
    choice = questionary.select(
        "Where should the validators run?",
        choices=[
            "Before LLM",
            "After LLM",
            "Both (before & after)",
        ],
        qmark="?",
    ).ask()

    guard_before = choice in ("Before LLM", "Both (before & after)")
    guard_after = choice in ("After LLM", "Both (before & after)")
    return guard_before, guard_after


def choose_response_mode():
    choice = questionary.select(
        "How should the LLM response be provided?",
        choices=[
            "Call local model",
            "Enter response manually (simulate LLM)",
        ],
        qmark="?",
    ).ask()
    return choice == "Call local model"


def pretty_print_turn(
    turn_index,
    original_prompt,
    prompt_after_guard,
    baseline_output,
    output_after_guard,
    guard_before,
    guard_after,
    validator_types,
):
    panels_list = []

    panels_list.append(
        Panel(
            textwrap.fill(original_prompt or "", width=90),
            title="Input Prompt",
            title_align="left",
            border_style="cyan",
        )
    )

    if guard_before:
        prompt_filtered = (prompt_after_guard or "") != (original_prompt or "")
        panels_list.append(
            Panel(
                textwrap.fill(prompt_after_guard or "", width=90),
                title="Input Prompt (After Guard)",
                title_align="left",
                border_style="red" if prompt_filtered else "green",
            )
        )

    panels_list.append(
        Panel(
            textwrap.fill(baseline_output or "", width=90),
            title="LLM Output (Baseline)",
            title_align="left",
            border_style="yellow",
        )
    )

    response_filtered = False
    if guard_after:
        response_filtered = (output_after_guard or "") != (baseline_output or "")
        panels_list.append(
            Panel(
                textwrap.fill(output_after_guard or "Sorry, I can't help with that.", width=90),
                title="Output (After Guard)",
                title_align="left",
                border_style="red" if response_filtered else "green",
            )
        )

    summary_table = Table(show_header=True, header_style="bold magenta")
    summary_table.add_column("Stage", style="cyan")
    summary_table.add_column("Guard Applied", style="blue")
    summary_table.add_column("Triggered", style="red")
    summary_table.add_column("Validator(s)", style="green")

    summary_table.add_row(
        "Before LLM",
        "Yes" if guard_before else "No",
        "Yes" if guard_before and (prompt_after_guard or "") != (original_prompt or "") else "No",
        ", ".join(validator_types) if guard_before else "-",
    )
    summary_table.add_row(
        "After LLM",
        "Yes" if guard_after else "No",
        "Yes" if guard_after and response_filtered else "No",
        ", ".join(validator_types) if guard_after else "-",
    )

    panels_list.append(summary_table)

    group = Group(*panels_list)
    console.print(
        Panel(
            group,
            title=f"Turn {turn_index}",
            border_style="orange1",
            padding=(1, 1),
        )
    )
    console.print()


def interactive_demo():
    console.print(Rule("Live Guardrails Demo"))
    console.print("Type 'exit' or 'quit' at any prompt to leave the demo.\n")

    turn_index = 1

    while True:
        user_prompt = questionary.text(
            "Enter your prompt for the LLM:",
            qmark=">",
        ).ask()

        if user_prompt is None:
            console.print("\n[bold red]Aborted by user.[/bold red]")
            sys.exit(0)

        if user_prompt.strip().lower() in {"exit", "quit"}:
            console.print("\n[bold green]Goodbye![/bold green]")
            break

        validator_types = choose_validator_types()

        guard_before, guard_after = choose_guard_location()

        use_real_llm = choose_response_mode()

        console.print(Rule(f"Running Turn {turn_index}"))

        prompt_to_use = user_prompt
        if guard_before:
            prompt_to_use = apply_guard(user_prompt, validator_types)

            if not prompt_to_use:
                console.print(
                    Panel(
                        "Prompt fully filtered by guards before reaching the LLM.",
                        title="Guard Result",
                        border_style="red",
                    )
                )
                pretty_print_turn(
                    turn_index,
                    original_prompt=user_prompt,
                    prompt_after_guard=prompt_to_use,
                    baseline_output="",
                    output_after_guard="",
                    guard_before=guard_before,
                    guard_after=False,
                    validator_types=validator_types,
                )
                turn_index += 1
                continue

        if use_real_llm:
            baseline_output = call_local_llm(prompt_to_use)
        else:
            simulated = questionary.text(
                "Enter the LLM response to test with Guardrails:",
                qmark=">",
            ).ask()
            baseline_output = simulated or ""

        output_after_guard = baseline_output
        if guard_after:
            output_after_guard = apply_guard(baseline_output, validator_types)

        pretty_print_turn(
            turn_index,
            original_prompt=user_prompt,
            prompt_after_guard=prompt_to_use,
            baseline_output=baseline_output,
            output_after_guard=output_after_guard,
            guard_before=guard_before,
            guard_after=guard_after,
            validator_types=validator_types,
        )

        turn_index += 1


if __name__ == "__main__":
    interactive_demo()

