"""Partition an observed DAG task by the exact incoming edges at one anchor."""
from itertools import combinations
from random import Random

from causal_prompts import _descendants, _observations


def _retains_paths(edges, observations):
    return all(required <= _descendants(root, edges) for root, required in observations)


def _candidate_parents(public):
    nodes = sorted(public["nodes"])
    observations = _observations(public)
    allowed = {(tail, head) for tail in nodes for head in nodes if tail != head}
    for root, required in observations:
        reached = required | {root}
        # A descendant cannot reach back to its source, or leave its reachable set.
        allowed -= {(tail, head) for tail in reached for head in set(nodes) - reached}
        allowed -= {(tail, root) for tail in required}
    forced = {edge for edge in allowed if not _retains_paths(allowed - {edge}, observations)}
    needs_incoming = {node for _, targets in observations for node in targets}
    families = {}
    for node in nodes:
        incoming = {edge for edge in allowed if edge[1] == node}
        necessary = sorted(tail for tail, head in incoming & forced)
        optional = sorted(tail for tail, head in incoming - forced)
        families[node] = []
        for size in range(len(optional) + 1):
            for extra in combinations(optional, size):
                parents = sorted([*necessary, *extra])
                selected = {(tail, node) for tail in parents}
                mandatory = forced | selected
                # Every affected node needs an incoming edge. Account for each
                # such head once if no mandatory edge already supplies it.
                missing_heads = needs_incoming - {head for _, head in mandatory}
                if len(mandatory) + len(missing_heads) > public["max_edges"]:
                    continue
                if _retains_paths((allowed - incoming) | selected, observations):
                    families[node].append(parents)
    return families


def skeleton_plan(public, seed, budget, variant):
    """Fix the anchor's stratum parents structurally and complete the rest.

    `variant="enforce"` reuses the parent_set wording and enforces the stratum
    after parsing. `variant="complete"` tells the model the fixed edges up
    front and asks for the remaining edges only. Both variants share the same
    a-priori stratum cycle as parent_plan.
    """
    if variant not in ("enforce", "complete"):
        raise ValueError("Unknown skeleton variant")
    if budget < 0:
        raise ValueError("Budget must be nonnegative")
    if budget == 0:
        return []
    families = _candidate_parents(public)
    widest = max(map(len, families.values()))
    if not widest:
        raise ValueError("No feasible parent sets for these observations")
    rng = Random(seed)
    anchor = rng.choice([node for node, family in families.items() if len(family) == widest])
    family = families[anchor]
    rng.shuffle(family)
    cycle = []
    for parents in family:
        if parents:
            arrows = ", ".join(f"{tail}->{anchor}" for tail in parents)
            rule = f"These direct edges are already fixed: {arrows}. No other edge may end at {anchor}."
        else:
            rule = f"No edge may end at {anchor}."
        remaining = public["max_edges"] - len(parents)
        if variant == "complete":
            rule += (f" Add at most {max(remaining, 0)} more directed edges "
                     f"and output only the edges you add.")
        else:
            rule += " Complete the graph so that every reachability condition holds."
        cycle.append(dict(node=anchor, parents=parents, prompt=rule))
    return [cycle[index % len(cycle)] for index in range(budget)]


def assemble(condition, edges):
    """Final graph edges after structural stratum enforcement.

    The stratum's parents at the anchor are fixed by construction; any other
    parsed edge into the anchor is dropped and duplicates collapse.
    """
    fixed = {(tail, condition["node"]) for tail in condition["parents"]}
    added = {tuple(edge) for edge in edges if edge[1] != condition["node"]}
    return frozenset(fixed | added)


def parent_plan(public, seed, budget):
    """Return a fixed cycle over the most ambiguous anchor's surviving parent sets.

    These tests are necessary conditions, so every compatible graph is covered;
    a retained set need not admit a complete compatible DAG in general.
    """
    if budget < 0:
        raise ValueError("Budget must be nonnegative")
    if budget == 0:
        return []
    families = _candidate_parents(public)
    widest = max(map(len, families.values()))
    if not widest:
        raise ValueError("No feasible parent sets for these observations")
    rng = Random(seed)
    anchor = rng.choice([node for node, family in families.items() if len(family) == widest])
    family = families[anchor]
    rng.shuffle(family)
    cycle = []
    for parents in family:
        if parents:
            arrows = ", ".join(f"{tail}->{anchor}" for tail in parents)
            rule = f"Include these direct edges: {arrows}. No other edge may end at {anchor}."
        else:
            rule = f"No edge may end at {anchor}."
        prompt = f"{rule} Complete the graph so that every reachability condition holds."
        cycle.append(dict(node=anchor, parents=parents, prompt=prompt))
    return [cycle[index % len(cycle)] for index in range(budget)]
