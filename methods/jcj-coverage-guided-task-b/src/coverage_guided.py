"""Adaptive coverage-guided prompting for the HypoSpace follow-up method.

The compatible set of one observation is exactly {1,2,3}^k over its k occupied
cells, so Recovery can only fail because the generator revisits structures it
has already produced. The adapted baseline removes duplicates from the history
it shows and asks for "something different", but it never says *where* the
search has stayed narrow. This hook appends a dimension-level search report:
how many compatible structures have been found, and for each occupied cell
which heights have actually been tried.

It never states an untried structure, so the generator still has to construct
the proposal itself. That is the line between this method and simply
enumerating the answer set.

Pure function of (prompt, context): no state survives between calls, so results
do not depend on the order observations or seeds are visited in.

Ablations (used by the dev study):
    coverage_guided:transform              full report
    coverage_guided:transform_stats_only   k/n only, no per-cell heights
    coverage_guided:transform_cells_only   per-cell heights only, no k/n
"""
from adapted_baseline import transform as base_transform
from hypospace_runner import upstream

MAX_HEIGHT = 3


def _parser():
    """Official parser/validator, used exactly as methods/szh-baseline-3d-task-b/src/export_run.py does."""
    official, _ = upstream()
    return object.__new__(official.Benchmark3D)


def heights_of(text, observation, parser):
    """Height per grid cell (row-major) for one recorded response.

    Returns None unless the response parses *and* passes the official
    validator, so unparseable, unsupported or projection-mismatched proposals
    never count as coverage.
    """
    structure = parser.parse_llm_response(text)
    if structure is None:
        return None
    structure = structure.normalize()
    if not parser.validate_structure_matches_observations(structure, observation):
        return None
    if not structure.layers:
        return None
    rows, cols = structure.layers[0].shape
    return tuple(
        int(sum(1 for layer in structure.layers if layer[r, c]))
        for r in range(rows) for c in range(cols)
    )


def _found(context, parser):
    """Distinct valid height vectors produced so far, in this observation only."""
    observation = context["observation"]
    found = set()
    for text in context["history"]:
        heights = heights_of(text, observation, parser)
        if heights is not None:
            found.add(heights)
    return found


def _report(context, parser, show_total=True, show_cells=True):
    observation = context["observation"]
    grid = int(len(observation) ** 0.5)
    cells = [i for i, bit in enumerate(observation) if bit == "1"]
    total = MAX_HEIGHT ** len(cells)
    found = _found(context, parser)

    if not found:
        return (
            "\nNo compatible structure has been accepted yet. "
            "Propose the lowest stack that matches the top view.\n"
        )

    used = {i: sorted({h[i] for h in found}) for i in cells}
    lines = []
    if show_total:
        lines.append(
            f"Search status: {len(found)} of {total} compatible structures found so far."
        )
    if show_cells:
        lines.append("Heights already used at each occupied cell:")
        for i in cells:
            row, col = divmod(i, grid)
            lines.append(f"  row {row + 1}, column {col + 1}: {', '.join(map(str, used[i]))}")
        fixed = [i for i in cells if len(used[i]) == 1]
        if fixed:
            lines.append(
                "Cells listed with a single height have never been varied. "
                "This answer must change the height of at least one of them."
            )
        else:
            lines.append(
                "Every occupied cell has been varied, so combine heights that have "
                "not appeared together yet. Do not reuse a structure listed above."
            )
    lines.append("Do not copy this report into your answer.")
    return "\n" + "\n".join(lines) + "\n"


def transform(prompt, context):
    """Full report: coverage count plus per-cell height usage."""
    return base_transform(prompt, context) + _report(context, _parser())


def transform_stats_only(prompt, context):
    """Ablation: the k/n count alone, with no per-cell direction."""
    return base_transform(prompt, context) + _report(
        context, _parser(), show_total=True, show_cells=False
    )


def transform_cells_only(prompt, context):
    """Ablation: per-cell direction alone, with no coverage count."""
    return base_transform(prompt, context) + _report(
        context, _parser(), show_total=False, show_cells=True
    )
