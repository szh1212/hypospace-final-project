"""Public, verifier-assisted local graph edits shared by both selection policies."""
from itertools import pairwise, permutations
import random
import re


MENU_SIZE = 4  # KEEP plus at most three alternatives.


def _descendants(nodes, graph):
    """Positive-length reachability, including self exactly when a cycle exists."""
    children = {u: set() for u in nodes}
    for u, v in graph:
        children[u].add(v)
    result = {}
    for root in nodes:
        seen = set()
        pending = list(children[root])
        while pending:
            node = pending.pop()
            if node not in seen:
                seen.add(node)
                pending.extend(children[node] - seen)
        result[root] = seen
    return result


def _valid(public, graph):
    nodes = public["nodes"]
    if len(graph) > public["max_edges"] or any(u not in nodes or v not in nodes for u, v in graph):
        return False
    reach = _descendants(nodes, graph)
    if any(n in reach[n] for n in nodes):
        return False
    return all(
        {n: int(n in reach[row["perturbed_node"]]) for n in nodes} == row["effects"]
        for row in public["observations"]
    )


def _reduce(nodes, graph):
    """Drop an edge u->v if another child of u already reaches v."""
    reach = _descendants(nodes, graph)
    if any(n in reach[n] for n in nodes):
        return None
    return tuple(sorted((u, v) for u, v in graph
                        if not any(w != v and v in reach[w] for w in reach[u])))


def _seed(public):
    nodes = public["nodes"]
    rows = public["observations"]
    positives = {(row["perturbed_node"], v) for row in rows
                 for v, value in row["effects"].items() if value}
    graph = _reduce(nodes, positives)
    if graph is None:
        return None
    if len(graph) > public["max_edges"]:
        # A common descendant chain can encode several positive effects with fewer edges.
        # Ordering indistinguishable unperturbed nodes preserves every measured effect.
        sources = {row["perturbed_node"] for row in rows}
        groups = {}
        for v in sorted(set(nodes) - sources):
            pattern = tuple(row["effects"][v] for row in rows)
            if any(pattern):
                groups.setdefault(pattern, []).append(v)
        for group in groups.values():
            positives.update(pairwise(group))
        graph = _reduce(nodes, positives)
    return graph if graph is not None and _valid(public, graph) else None


def _neighbors(public, source):
    """Examine only individual modifications of this accepted source."""
    edges = set(source)
    for u, v in permutations(sorted(public["nodes"]), 2):
        edge = (u, v)
        if edge in edges:
            yield tuple(sorted(edges - {edge}))
            yield tuple(sorted((edges - {edge}) | {(v, u)}))
        elif (v, u) not in edges and len(edges) < public["max_edges"]:
            yield tuple(sorted(edges | {edge}))


def action_menu(public, previous, index, seed):
    """Prefer the latest accepted source with unseen neighbors, then backtrack.

    The public seed is also a source, even if the selector hasn't emitted it.
    Only emitted valid hypotheses are marked seen. Unselected neighbors never
    become sources. All candidate ranking and source choices are shared.
    """
    start = _seed(public)
    if start is None:
        return []
    seen = set()
    sources = []
    for row in reversed(previous):
        if row["valid"] and row["edges"] is not None:
            graph = tuple(sorted(tuple(edge) for edge in row["edges"]))
            if graph not in seen and _valid(public, graph):
                seen.add(graph)
                sources.append(graph)
    if start not in seen:
        sources.append(start)

    rng = random.Random(f"{seed}/{index}")
    fallback = None
    for source in sources:
        neighbors = [g for g in _neighbors(public, source) if _valid(public, g)]
        rng.shuffle(neighbors)
        neighbors.sort(key=lambda g: g in seen)  # Stable after seeded shuffle.
        menu = [source, *neighbors[:MENU_SIZE - 1]]
        if source not in seen or any(g not in seen for g in neighbors):
            return menu
        if fallback is None:
            fallback = menu
    return fallback


def _edge(edge):
    return "->".join(edge)


def _edges(graph):
    return ", ".join(_edge(e) for e in graph) or "No edges"


def action_prompt(public, menu):
    nodes = public["nodes"]
    lines = [
        f"Nodes {', '.join(nodes)}. Directed acyclic graph with at most {public['max_edges']} edges.",
        "Each intervention affects exactly the descendants listed below.",
    ]
    for row in public["observations"]:
        effects = ", ".join(n for n in nodes if row["effects"][n]) or "none"
        lines.append(f"Perturb {row['perturbed_node']}: {effects}.")
    if not menu:
        return "\n".join([*lines, "No valid starting graph was constructed. Reply: NO ACTION"])
    base = set(menu[0])
    lines += [f"Current graph: {_edges(menu[0])}",
              "Select one edit to explore a distinct compatible graph.", "1. KEEP current graph"]
    for index, graph in enumerate(menu[1:], 2):
        added = set(graph) - base
        removed = base - set(graph)
        if added and removed:
            edit = f"REVERSE {_edge(removed.pop())}"
        elif added:
            edit = f"ADD {_edge(added.pop())}"
        else:
            edit = f"DELETE {_edge(removed.pop())}"
        lines.append(f"{index}. {edit}")
    lines.append("Return only 'Choice: N' with the number of your chosen action.")
    return "\n".join(lines)


def decode_choice(raw, menu):
    """Decode exactly one in-range model response; the official scorer sees all failures."""
    match = re.fullmatch(r"Choice: ([1-9][0-9]*)", raw.strip()) if isinstance(raw, str) else None
    if match and match.group(1) in {str(i) for i in range(1, len(menu) + 1)}:
        return "Graph: " + _edges(menu[int(match.group(1)) - 1])
    return "INVALID_CHOICE"
