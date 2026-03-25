"""
Expand the MCF skill dictionary with singular/plural counterparts.

Only expands skills whose last word is a known countable tech noun.
This avoids generating nonsensical plurals like "a/b testings" or
"ability to work under pressures".

Usage:
    uv run python scripts/expand_mcf_plurals.py
    uv run python scripts/expand_mcf_plurals.py --dry-run   # preview only
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

MCF_DICT_PATH = Path("config/mcf_skills.json")

# Countable tech nouns — only these get singular/plural expansion.
# Curated from analysis of the 5,212-entry MCF dictionary.
COUNTABLE_TECH_NOUNS = {
    "algorithm", "api", "application", "architecture", "assessment",
    "benchmark", "branch", "buffer",
    "certificate", "channel", "cluster", "component", "configuration",
    "connection", "connector", "constraint", "container", "controller",
    "credential", "cycle",
    "dashboard", "database", "dataset", "deliverable", "deployment",
    "device", "dimension", "directive", "driver",
    "endpoint", "engine", "environment", "event", "exception",
    "feature", "filter", "firewall", "flow", "format", "framework",
    "function",
    "gateway", "graph", "guard",
    "handler", "hook",
    "indicator", "instance", "integration", "interface", "interpreter",
    "iterator",
    "kernel",
    "layer", "library", "lifecycle", "link", "loader", "log",
    "mechanism", "method", "methodology", "metric", "microservice",
    "middleware", "milestone", "model", "module",
    "namespace", "network", "node",
    "object", "operation", "operator", "optimization",
    "package", "parameter", "parser", "partition", "pattern",
    "pipeline", "platform", "plugin", "pod", "policy", "port",
    "process", "processor", "profile", "program", "project",
    "protocol", "proxy",
    "query", "queue",
    "record", "registry", "repository", "request", "requirement",
    "resource", "response", "role", "router", "rule", "runtime",
    "scanner", "schema", "script", "sensor", "server", "service",
    "signal", "simulation", "snapshot", "socket", "solution",
    "specification", "stack", "standard", "store", "strategy",
    "stream", "structure", "switch", "system",
    "table", "task", "template", "test", "thread", "token", "tool",
    "topic", "transaction", "trigger", "type",
    "utility",
    "variable", "vector", "version", "volume",
    "widget", "workflow", "workspace",
}

# Skills starting with these prefixes are soft-skill phrases, not tech terms
SKIP_PREFIXES = (
    "ability to", "able to", "attention to", "aptitude for",
    "willingness to", "capacity to", "passion for",
    "proven track", "good driving",
)

# Skills containing these words are verb phrases or "X of Y" constructions, not standalone nouns
SKIP_CONTAINS = (
    " of ", " the ", " with ", " for ", " to ", " a ", " an ",
)

# Uncountable / mass nouns that should not be pluralized
UNCOUNTABLE = {
    "software", "hardware", "firmware", "middleware",
    "compliance", "governance", "intelligence", "infrastructure",
    "knowledge", "expertise", "experience", "awareness",
    "research", "maintenance", "performance", "resilience",
    "documentation", "automation", "administration",
}


def pluralize(word: str) -> str:
    """Simple English pluralization."""
    if word.endswith(("s", "x", "z", "ch", "sh")):
        return word + "es"
    if word.endswith("y") and len(word) > 1 and word[-2] not in "aeiou":
        return word[:-1] + "ies"
    return word + "s"


def singularize(word: str) -> str:
    """Simple English singularization."""
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith(("ses", "xes", "zes")):
        return word[:-2]
    if word.endswith("ches") or word.endswith("shes"):
        return word[:-2]
    if word.endswith("s") and not word.endswith("ss") and len(word) > 3:
        return word[:-1]
    return word


def expand_skills(skills: list[str], dry_run: bool = False) -> tuple[list[str], list[str]]:
    """Generate singular/plural counterparts for skills ending in countable tech nouns.

    Returns (updated_skills, additions).
    """
    lower_set = {s.lower() for s in skills}
    additions: list[str] = []

    for skill in skills:
        lower = skill.lower()

        # Skip long phrases, soft-skill phrases, and verb/preposition constructions
        words = lower.split()
        if len(words) > 4:
            continue
        if any(lower.startswith(p) for p in SKIP_PREFIXES):
            continue
        if any(p in f" {lower} " for p in SKIP_CONTAINS):
            continue
        # Skip verb phrases (first word is a common verb or ends in verb suffixes)
        if len(words) > 1:
            first = words[0]
            if first in ("analyze", "analyse", "build", "create", "define", "deploy",
                         "design", "develop", "enhance", "ensure", "establish",
                         "execute", "gather", "identify", "implement", "improve",
                         "lead", "maintain", "manage", "meet", "monitor", "optimize",
                         "plan", "resolve", "setup", "track", "work", "write"):
                continue
            if first.endswith(("ing", "ed", "ize", "ise", "tes", "ses")):
                continue

        last = words[-1]

        # Skip if last word has special characters
        if any(c in last for c in "/-+#.()0123456789"):
            continue

        # Skip uncountable nouns
        if last in UNCOUNTABLE:
            continue

        # Check if last word is a known countable tech noun (or its plural)
        candidate = None
        if last in COUNTABLE_TECH_NOUNS:
            # Singular in dict — generate plural
            candidate_last = pluralize(last)
            candidate = " ".join(words[:-1] + [candidate_last])
        else:
            # Check if it's a plural of a known noun
            singular = singularize(last)
            if singular in COUNTABLE_TECH_NOUNS and singular != last:
                candidate = " ".join(words[:-1] + [singular])

        if candidate and candidate not in lower_set:
            additions.append(candidate)
            lower_set.add(candidate)

    if not dry_run and additions:
        all_skills = skills + additions
        sorted_skills = sorted(set(all_skills), key=str.lower)
        MCF_DICT_PATH.write_text(
            json.dumps(sorted_skills, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    return skills + additions, additions


def main() -> None:
    parser = argparse.ArgumentParser(description="Expand MCF dictionary with singular/plural counterparts")
    parser.add_argument("--dry-run", action="store_true", help="Preview additions without writing")
    args = parser.parse_args()

    skills = json.loads(MCF_DICT_PATH.read_text(encoding="utf-8"))
    print(f"Current MCF dictionary: {len(skills)} skills")

    _, additions = expand_skills(skills, dry_run=args.dry_run)

    print(f"Additions: {len(additions)}")
    if additions:
        for a in sorted(additions):
            print(f"  + {a}")

    if not args.dry_run and additions:
        final = json.loads(MCF_DICT_PATH.read_text(encoding="utf-8"))
        print(f"\nUpdated MCF dictionary: {len(final)} skills")
    elif args.dry_run:
        print("\n(dry run — no changes written)")


if __name__ == "__main__":
    main()
