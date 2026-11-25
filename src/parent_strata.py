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
