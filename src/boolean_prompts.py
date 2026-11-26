"""Per-attempt boolean prompts from public observations and stratum conditions.

The official baseline prompt is the upstream `create_prompt` (with accumulated
prior hypotheses), replayed verbatim by the runner. These builders implement
the hierarchical-route faces for the same observation data: the completion
variant states the target outputs for unobserved rows (verbal stratum), and the
skeleton variants additionally fix a one-hole skeleton the model must fill.
"""
from itertools import product

from boolean_space import ALL_INPUTS, observed_rows

RULES = ("Use only the variables x, y; only the operators AND, OR, NOT, NOR; "
         "at most 2 levels of nesting; no constants True/False.")
FORMAT_LINE = ('Return one line beginning with "Expression: " followed by the expression. '
               "No explanation.")


def _observations_block(public):
    return "\n".join(obs["string"] for obs in public["observations"])


def target_rows(public, completion):
    """The completion's values on the rows the observations leave unobserved."""
    observed = observed_rows(public)
    rows = [t for t in ALL_INPUTS if t not in observed]
    return [(t, completion[t]) for t in rows]


def _target_block(public, completion):
    lines = []
    for t, value in target_rows(public, completion):
        lines.append(f"(x={t[0]}, y={t[1]}) -> {value}")
    return "\n".join(lines)


def _head(public, target_block):
    return "\n".join([
        "You are given partial observations of a Boolean function with variables: x, y",
        "Allowed operators: AND, OR, NOT, NOR",
        "Observations (input -> output):",
        _observations_block(public),
        "The remaining input rows are unobserved. For this attempt, your expression "
        "must also output:",
        target_block,
    ])


def completion_prompt(public, condition):
    """First-generation face: verbal completion stratum, free-form expression."""
    return "\n".join([
        _head(public, _target_block(public, condition["completion"])),
        "Generate one Boolean expression that matches ALL observations and ALL target rows.",
        RULES, FORMAT_LINE,
    ])


def skeleton_prompt(public, condition):
    """Skeleton face: one-hole template fixed in the prompt, model fills the slot."""
    return "\n".join([
        _head(public, _target_block(public, condition["completion"])),
        "Your expression must use this fixed skeleton with one slot [?]:",
        condition["template"]["hole_text"],
        "Fill [?] with exactly one of: x, y, NOT x, NOT y",
        "so that the completed expression matches ALL observations and ALL target rows.",
        RULES, FORMAT_LINE,
    ])
