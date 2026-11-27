"""Boolean hypothesis-space scaffolding for the hierarchical generation route.

Public observations give partial rows of a two-variable truth table. The route
partitions the compatible hypothesis space by

  level 1 - the completion of every unobserved input row (every compatible
            expression's truth table extends the observations), and
  level 2 - a skeleton template with exactly one hole that the model fills.

Both partitions are computed from the public space definition only
(variables, operators, depth) plus the public observations; ground-truth
expressions are never read by the planner.
"""
from itertools import product
from pathlib import Path
from random import Random

import sympy as sp

from boolean_benchmark import MAX_DEPTH, MECH_OPTS, OPERATORS, VARIABLES, load_official

X, Y, H = sp.Symbol("x"), sp.Symbol("y"), sp.Symbol("h")
LITERALS = ("x", "y", "NOT x", "NOT y")
ALL_INPUTS = tuple(product((0, 1), repeat=len(VARIABLES)))


def _plain(expr):
    """NOR(...) printing is only safe for atoms and NOT-atoms (official parser regex)."""
    return isinstance(expr, sp.Symbol) or (isinstance(expr, sp.Not)
                                           and isinstance(expr.args[0], sp.Symbol))


def _needs_parens(child):
    return not (isinstance(child, sp.Symbol)
                or (isinstance(child, sp.Not) and _plain(child.args[0])
                    and not isinstance(child.args[0], sp.Symbol)))


def _print(expr, hole):
    """AST-shaped printing: every binary child keeps explicit parentheses, so the
    official parser rebuilds an AST with the same depth, shape and mechanistic
    key. Flat n-ary nodes are right-nested back into binary pairs, which keeps
    depth <= 2 while the mechanistic key (with associativity flattening) is
    unchanged."""
    if isinstance(expr, sp.Symbol):
        return "[?]" if (hole and expr == H) else str(expr)
    if isinstance(expr, sp.Not):
        inner = expr.args[0]
        if isinstance(inner, sp.Or) and all(_plain(arg) for arg in inner.args):
            return "NOR(" + ", ".join(_print(arg, hole) for arg in inner.args) + ")"
        return "NOT " + (_print(inner, hole) if _needs_parens(inner) is False
                         else "(" + _print(inner, hole) + ")")
    if isinstance(expr, sp.And) or isinstance(expr, sp.Or):
        op = "AND" if isinstance(expr, sp.And) else "OR"

        def fmt(arg):
            return ("(" + _print(arg, hole) + ")") if _needs_parens(arg) else _print(arg, hole)

        if len(expr.args) <= 2:
            return (" " + op + " ").join(fmt(arg) for arg in expr.args)
        acc = fmt(expr.args[-1])
        for arg in reversed(expr.args[:-1]):
            acc = fmt(arg) + " " + op + " " + acc
        return acc
    raise ValueError(f"Unsupported node in boolean space: {expr}")


def _depth(expr):
    if isinstance(expr, sp.Symbol):
        return 0
    return 1 + max((_depth(arg) for arg in expr.args), default=0)


def canonical(expr):
    """Official-style formula text that round-trips the official parser."""
    return _print(expr, hole=False)


def canonical_hole(expr):
    """Like canonical, with the single `h` placeholder printed as [?]."""
    return _print(expr, hole=True)


def observed_rows(public):
    return {tuple(obs["inputs"][v] for v in VARIABLES): obs["output"]
            for obs in public["observations"]}


def _full_table(observed, assignment):
    table = dict(observed)
    table.update(assignment)
    return table


_cache = {}


def space_rows(upstream):
    """In-space hypothesis expressions: (canonical text, key, truth table).

    The official enumeration re-parses its own generated formulas, which turns
    some entries into deeper ASTs that the official depth check rejects. Only
    expressions the official evaluator can accept as valid (depth <= max_depth)
    are usable by the planner, so the space is filtered to those.
    """
    key = str(Path(upstream).resolve())
    if key not in _cache:
        _, dataset_module = load_official(upstream)
        game = dataset_module.BooleanDiscoveryGame
        rows = []
        for be in game.generate_all_expressions(list(VARIABLES), set(OPERATORS), MAX_DEPTH,
                                                MECH_OPTS):
            if _depth(be.sympy_expr) > MAX_DEPTH:
                continue
            rows.append((canonical(be.sympy_expr), be.mechanistic_key(**MECH_OPTS),
                         be.truth_table))
        _cache[key] = rows
    return _cache[key]


_template_cache = {}


def template_rows(upstream):
    """Mechanistically distinct skeletons with exactly one hole, plus their
    in-space instances. Instances are built by text substitution (sympy
    structural replacement would simplify, e.g. NOT(NOT x) -> x) and kept only
    when the official depth check accepts them and their mechanistic key
    belongs to the official hypothesis space, so every usable instance is a
    real candidate for recovery."""
    key = str(Path(upstream).resolve())
    if key not in _template_cache:
        _, dataset_module = load_official(upstream)
        game = dataset_module.BooleanDiscoveryGame
        official_keys = {be.mechanistic_key(**MECH_OPTS)
                         for be in game.generate_all_expressions(list(VARIABLES),
                                                                 set(OPERATORS),
                                                                 MAX_DEPTH, MECH_OPTS)}
        templates = []
        for be in game.generate_all_expressions(["x", "y", "h"], set(OPERATORS), MAX_DEPTH,
                                                MECH_OPTS):
            expr = be.sympy_expr
            if sum(1 for node in sp.preorder_traversal(expr) if node == H) != 1:
                continue
            hole_text = canonical_hole(expr)
            if hole_text.count("[?]") != 1:
                continue
            instances = {}
            for lit in LITERALS:
                text = hole_text.replace("[?]", lit)
                parsed = dataset_module.BooleanExpression(text, list(VARIABLES), set(OPERATORS))
                if parsed.sympy_expr is None or _depth(parsed.sympy_expr) > MAX_DEPTH:
                    continue
                inst_key = parsed.mechanistic_key(**MECH_OPTS)
                if inst_key not in official_keys:
                    continue
                instances[lit] = dict(text=canonical(parsed.sympy_expr), key=inst_key,
                                      table=parsed.truth_table)
            if instances:
                templates.append(dict(expr=expr, hole_text=hole_text,
                                      key=be.mechanistic_key(**MECH_OPTS), instances=instances))
        _template_cache[key] = templates
    return _template_cache[key]


def completions(upstream, public):
    """Feasible completions of the unobserved truth-table rows (level-1 strata)."""
    observed = observed_rows(public)
    unobserved = [t for t in ALL_INPUTS if t not in observed]
    space_tables = [row[2] for row in space_rows(upstream)]
    out = []
    for assignment in product((0, 1), repeat=len(unobserved)):
        table = _full_table(observed, dict(zip(unobserved, assignment)))
        if any(all(s_table[t] == table[t] for t in ALL_INPUTS) for s_table in space_tables):
            out.append(table)
    return out


def _matches(table, target):
    return all(table[t] == target[t] for t in ALL_INPUTS)


def feasible_cells(upstream, completion):
    """Templates with at least one hole value matching the completion (level-2 strata)."""
    cells = []
    for template in template_rows(upstream):
        matches = {lit: inst for lit, inst in template["instances"].items()
                   if _matches(inst["table"], completion)}
        if matches:
            cells.append(dict(template=template, matches=matches))
    return cells


def completion_plan(upstream, public, seed, budget):
    """Level-1 stratum cycle for the first-generation verbal variant."""
    if budget < 0:
        raise ValueError("Budget must be nonnegative")
    if budget == 0:
        return []
    rng = Random(seed)
    comps = completions(upstream, public)
    if not comps:
        raise ValueError("No feasible truth-table completions for these observations")
    rng.shuffle(comps)
    return [dict(completion=comps[index % len(comps)]) for index in range(budget)]


def skeleton_plan(upstream, public, seed, budget):
    """Two-level joint stratum cycle: completions round-robin, templates within each."""
    if budget < 0:
        raise ValueError("Budget must be nonnegative")
    if budget == 0:
        return []
    rng = Random(seed)
    comps = completions(upstream, public)
    if not comps:
        raise ValueError("No feasible truth-table completions for these observations")
    rng.shuffle(comps)
    blocks = []
    for table in comps:
        cells = feasible_cells(upstream, table)
        rng.shuffle(cells)
        if cells:
            blocks.append(dict(completion=table, cells=cells))
    if not blocks:
        raise ValueError("No feasible skeleton cells for these observations")
    plan = []
    for index in range(budget):
        block = blocks[index % len(blocks)]
        cell = block["cells"][(index // len(blocks)) % len(block["cells"])]
        plan.append(dict(completion=block["completion"], template=cell["template"],
                         matches=cell["matches"]))
    return plan


def parse_expression(dataset, response):
    """Parse a raw response through the official parser into (text, key, table) or None."""
    text = dataset.bench.parse_llm_response(response)
    if not text:
        return None
    _, dataset_module = load_official(dataset._upstream)
    try:
        be = dataset_module.BooleanExpression(text, list(VARIABLES), set(OPERATORS))
    except Exception:
        return None
    if be.sympy_expr is None:
        return None
    return dict(text=canonical(be.sympy_expr), key=be.mechanistic_key(**MECH_OPTS),
                table=be.truth_table)


def assemble(dataset, condition, response, variant):
    """Deterministic output assembly per variant.

    `completion` accepts the parsed expression as-is (verbal stratum; the
    official evaluator decides validity against the observations).
    `skeleton` enforces the stratum structurally: the expression is kept only
    when its full truth table matches the cell's completion, otherwise the
    attempt is rejected. `skeleton_valid` keeps the model's hole value when it
    matches the completion and otherwise repairs it to the first literal, in a
    fixed public order, whose instantiation of the model's skeleton matches the
    completion - a minimal leaf repair of the model's own structure. The repair
    also runs when the model's output does not parse, which is when it is
    needed most.
    """
    parsed = parse_expression(dataset, response)
    if variant == "completion":
        return parsed["text"] if parsed is not None else None
    completion = condition["completion"]
    template = condition["template"]
    if variant == "skeleton":
        if parsed is None:
            return None
        return parsed["text"] if _matches(parsed["table"], completion) else None
    if variant == "skeleton_valid":
        order = []
        hole = None
        if parsed is not None:
            hole = next((lit for lit, inst in template["instances"].items()
                         if inst["key"] == parsed["key"]), None)
            if hole is not None:
                order.append(hole)
        order += [lit for lit in LITERALS if lit != hole]
        for lit in order:
            inst = template["instances"].get(lit)
            if inst is not None and _matches(inst["table"], completion):
                return inst["text"]
        return None
    raise ValueError(f"Unknown boolean variant: {variant}")
