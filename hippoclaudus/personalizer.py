# hippoclaudus/personalizer.py
"""Interactive CLAUDE.md customization.

Reads the installed CLAUDE.md, prompts the user for identity info,
and fills in <!-- PERSONALIZE --> blocks.
"""

import re
from pathlib import Path
from typing import Optional

import click


def find_personalize_blocks(content: str) -> list:
    """Find all <!-- PERSONALIZE: tag --> ... <!-- END PERSONALIZE --> blocks."""
    pattern = r'<!-- PERSONALIZE: (\w+) -->.*?<!-- END PERSONALIZE -->'
    matches = []
    for m in re.finditer(pattern, content, re.DOTALL):
        matches.append({
            "tag": m.group(1),
            "start": m.start(),
            "end": m.end(),
            "full_match": m.group(0),
        })
    return matches


def replace_personalize_block(content: str, tag: str, new_content: str) -> str:
    """Replace the content of a specific PERSONALIZE block."""
    pattern = rf'(<!-- PERSONALIZE: {tag} -->)\n.*?\n(<!-- END PERSONALIZE -->)'
    replacement = rf'\1\n{new_content}\n\2'
    return re.sub(pattern, replacement, content, flags=re.DOTALL)


def generate_identity_block(user_name: str, persona_name: Optional[str], work_type: str) -> str:
    """Generate the identity section content."""
    lines = [f"You are working with {user_name}."]
    if persona_name:
        lines.append(f'"{persona_name}" is your working persona for this collaboration.')
    lines.append(f"Primary work focus: {work_type}.")
    return "\n".join(lines)


def generate_people_block(people: list) -> str:
    """Generate the key people section content."""
    if not people:
        return "No key people configured yet. Add them with `hippo personalize`."

    lines = ["| Person | Relationship | Role |", "|--------|-------------|------|"]
    for p in people:
        lines.append(f"| {p['name']} | {p['relationship']} | {p['role']} |")
    return "\n".join(lines)


def generate_machine_block(machine_desc: str) -> str:
    """Generate the machine context section content."""
    return f"**Machine:** {machine_desc}"


def run_personalize(claude_md_path: Path) -> None:
    """Interactive CLI flow for CLAUDE.md personalization."""
    if not claude_md_path.exists():
        click.echo(f"✗ CLAUDE.md not found at {claude_md_path}")
        click.echo("  Run 'hippo install' first.")
        return

    content = claude_md_path.read_text()
    blocks = find_personalize_blocks(content)

    if not blocks:
        click.echo("No <!-- PERSONALIZE --> blocks found in CLAUDE.md.")
        click.echo("Your CLAUDE.md may already be fully customized.")
        return

    click.echo("\n  Hippoclaudus Personalization\n")
    click.echo("  I'll ask a few questions to customize your CLAUDE.md.\n")

    # Identity
    user_name = click.prompt("  Your name")
    persona_name = click.prompt("  A name for your Claude persona (or press Enter to skip)",
                                default="", show_default=False)
    persona_name = persona_name.strip() or None
    work_type = click.prompt("  What kind of work do you primarily do")

    identity_content = generate_identity_block(user_name, persona_name, work_type)

    # Key people
    people = []
    if click.confirm("\n  Would you like to add key people Claude should know about?", default=False):
        while True:
            name = click.prompt("    Name")
            relationship = click.prompt("    Relationship (e.g., colleague, manager, partner)")
            role = click.prompt("    Role/title")
            people.append({"name": name, "relationship": relationship, "role": role})
            if not click.confirm("    Add another person?", default=False):
                break

    people_content = generate_people_block(people)

    # Machine
    machine_desc = click.prompt("\n  Describe your machine (e.g., 'MacBook Pro M3, primary dev machine')",
                                default="", show_default=False)

    # Apply
    for block in blocks:
        tag = block["tag"]
        if tag == "identity":
            content = replace_personalize_block(content, tag, identity_content)
        elif tag == "people":
            content = replace_personalize_block(content, tag, people_content)
        elif tag == "machine":
            if machine_desc.strip():
                content = replace_personalize_block(content, tag, generate_machine_block(machine_desc))

    claude_md_path.write_text(content)
    click.echo(f"\n  ✓ CLAUDE.md updated at {claude_md_path}")
    click.echo("  Run 'hippo personalize' again anytime to update.\n")
