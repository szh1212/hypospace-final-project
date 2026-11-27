"""Per-attempt causal DAG prompts using public observations and previous model outputs."""
from random import Random


def _observations(public):
    return [(obs["perturbed_node"], {node for node, effect in obs["effects"].items() if effect == 1})
            for obs in public["observations"]]


def _descendants(root, edges):
    reached = {root}
    pending = [root]
    while pending:
        source = pending.pop()
        for tail, head in edges:
            if tail == source and head not in reached:
                reached.add(head)
                pending.append(head)
    return reached - {root}


def _key(record):
    if record["edges"] is None:
        return None
    return frozenset(tuple(edge) for edge in record["edges"])


def _names(items):
    return ", ".join(sorted(items)) or "none"


def _reachability(public, previous):
    nodes = set(public["nodes"])
    lines = [
        f"Generate one directed acyclic graph on {_names(nodes)} using at most {public['max_edges']} edges.",
        "Reach means a directed path of one or more edges. Each experiment gives the exact descendants.",
    ]
    for root, required in _observations(public):
        forbidden = nodes - required - {root}
        lines.append(f"From {root}, must reach: {_names(required)}. Must never reach: {_names(forbidden)}.")
    lines.append("A required path may be indirect. No self-loops or cycles. Check every path against all experiments.")
    recent = []
    for record in reversed(previous):
        edges = _key(record)
        if edges is not None and edges not in recent:
            recent.append(edges)
            if len(recent) == 4:
                break
    if recent:
        lines.append("Avoid repeating these recent edge sets:")
        for edges in recent:
            lines.append(", ".join(f"{s}->{t}" for s, t in sorted(edges)) or "No edges")
    lines.append('Return one line beginning with "Graph: " followed by comma-separated source->target '
                 'edges, or "Graph: No edges" for an empty graph. No explanation.')
    return "\n".join(lines)


def _feedback(public, previous):
    if not previous:
        return ""
    last = previous[-1]
    edges = _key(last)
    if edges is None:
        return "The last response failed the graph parser. Check the one-line format, edge limit and acyclicity."
    if last["valid"]:
        duplicate = any(record["valid"] and _key(record) == edges for record in previous[:-1])
        outcome = "repeated an earlier valid graph" if duplicate else "satisfied all experiments"
        return f"The last graph {outcome}. Change at least one direct edge while keeping all reachability conditions."
    lines = []
    for root, expected in _observations(public):
        actual = _descendants(root, edges)
        if expected - actual:
            lines.append(f"From {root}, the last graph missed paths to {_names(expected - actual)}.")
        if actual - expected:
            lines.append(f"From {root}, the last graph had unwanted paths to {_names(actual - expected)}.")
    return " ".join(lines) or "The last graph failed validation. Recheck all constraints."


def _branch_arms(public, seed):
    # Eliminate direct edges contradicted by exact descendants or acyclicity.
    nodes = set(public["nodes"])
    observations = _observations(public)
    forbidden = set()
    for root, downstream in observations:
        reachable = downstream | {root}
        forbidden.update((s, t) for s in reachable for t in nodes - reachable)
        forbidden.update((s, root) for s in downstream)
    allowed = {(s, t) for s in nodes for t in nodes if s != t} - forbidden
    if public["max_edges"] == 0:
        return []
    # If removing an edge from the entire allowed supergraph disconnects a
    # required path, its absence cannot define a productive branch.
    optional = [edge for edge in sorted(allowed)
                if all(required <= _descendants(root, allowed - {edge})
                       for root, required in observations)]
    rng = Random(seed)
    rng.shuffle(optional)
    observed_roots = {root for root, _ in observations}
    optional.sort(key=lambda edge: edge[0] in observed_roots)
    return [(edge, required) for edge in optional[:2] for required in (True, False)]


def _reward(arm, record, seen):
    edges = _key(record)
    if not record["valid"] or edges is None:
        return 0
    edge, required = arm
    reward = int(edges not in seen and (edge in edges) == required)
    seen.add(edges)
    return reward


def adaptive_constraint(public, previous, index, seed):
    """Return ((source, target), must_include) or None when no split is available."""
    if index != len(previous):
        raise ValueError("index must equal the number of previous attempts")
    arms = _branch_arms(public, seed)
    if not arms:
        return None
    # Replay online decisions from the actual samples, including failed attempts.
    # The run budget is small; replay also makes resumed requests deterministic.
    attempts = dict.fromkeys(arms, 0)
    wins = dict.fromkeys(arms, 0)
    seen = set()
    last, streak, reward = None, 0, 0
    for step in range(index + 1):
        candidates = [arm for arm in arms if arm != last or (reward and streak < 2)]
        if step % 4 == 0:
            # Try least-requested arms; break ties toward predicates rarely seen
            # among distinct valid predictions, then by seeded feature order.
            def rank(arm):
                edge, required = arm
                covered = sum((edge in edges) == required for edges in seen)
                return -attempts[arm], -covered
        else:
            def rank(arm):
                return (1 + wins[arm]) / (2 + attempts[arm]), -attempts[arm]
        arm = max(candidates, key=rank)
        if step == index:
            return arm
        streak = streak + 1 if arm == last else 1
        last = arm
        reward = _reward(arm, previous[step], seen)
        attempts[arm] += 1
        wins[arm] += reward


def prompt_for(method, case_public, previous, index, seed, official_prompt):
    """Build one request. Index is zero-based; no reference graphs are accepted."""
    if method == "official":
        return official_prompt
    if method == "edge_count":
        lower = max((len(required) for _, required in _observations(case_public)), default=0)
        count = lower + index % (case_public["max_edges"] + 1 - lower)
        return (official_prompt + "\n\nFor this attempt, also satisfy these subspace constraints:\n"
                + f"Use exactly {count} directed edges.")
    if method not in ("reachability", "feedback", "adaptive", "structural_cycle"):
        raise ValueError(f"Unknown prompt method: {method}")
    base = _reachability(case_public, previous)
    if method == "reachability":
        return base
    feedback = _feedback(case_public, previous)
    if feedback:
        base += "\n" + feedback
    if method in ("adaptive", "structural_cycle"):
        if method == "adaptive":
            arm = adaptive_constraint(case_public, previous, index, seed)
        else:
            arms = _branch_arms(case_public, seed)
            arm = arms[index % len(arms)] if arms else None
        if arm is not None:
            (source, target), required = arm
            verb = "Include" if required else "Exclude"
            base += f"\nStructural constraint for this attempt: {verb} the direct edge {source}->{target}."
    return base
