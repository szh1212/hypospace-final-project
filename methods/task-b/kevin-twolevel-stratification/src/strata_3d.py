"""Pure logic for the 3D voxel method: stratification, prompting, repair. No I/O.

Domain (official HypoSpace 3D, upstream c69e931): a top view over a 3x3 grid marks
the b occupied columns. An admissible structure is a height assignment h in
{1,2,3}^b per occupied column (gravity: layers nest downward). Equivalently a
structure is (S2, S3) with S3 subset S2 subset O, where O is the set of occupied
columns and S2/S3 are the columns continued into Layer 2 / Layer 3.

Method (two-level hierarchical stratification + validity filter):
  Level 1 stratum : (k2, k3) = (|S2|, |S3|); the strata partition the space.
  Level 2 anchor  : one column pinned "in S2" / "not in S2", rotating per query.
  Filter          : the model's raw output is repaired to the closest valid
                    structure inside the assigned stratum (counts exact, S3 in S2,
                    Layer 1 = top view). Parse failures fall back to the
                    reading-order-minimal structure of the stratum.
All rules are deterministic; every transformation is replayable from the raw call.
"""
from itertools import combinations
from math import comb

GRID = 3
MAX_HEIGHT = 3


def occupied_cells(observation):
    """Row-major occupied columns of the top view, in reading order."""
    return [(i // GRID, i % GRID) for i, ch in enumerate(observation) if ch == '1']


def n_blocks(observation):
    return observation.count('1')


def strata(b):
    """All level-1 strata for b occupied columns: (k2, k3), 0 <= k3 <= k2 <= b."""
    return [(k2, k3) for k2 in range(b + 1) for k3 in range(k2 + 1)]


def stratum_size(b, k2, k3):
    """Number of admissible structures in stratum (k2, k3): C(b,k2) * C(k2,k3)."""
    return comb(b, k2) * comb(k2, k3)


def stratum_solutions(b, k2, k3):
    """All (S2, S3) solutions of a stratum, S2/S3 as frozensets of column indices."""
    out = []
    for s2_idx in combinations(range(b), k2):
        for s3_idx in combinations(s2_idx, k3):
            out.append((frozenset(s2_idx), frozenset(s3_idx)))
    return out


def feasible_anchors(b, k2, k3):
    """Ordered (column_idx, in_s2, s3_branch) anchor triples feasible for the
    stratum: in_s2=True/False; s3_branch=True (in S3) / False (not in S3) /
    None (no Layer 3 constraint, used when k3 == 0)."""
    pairs = []
    for i in range(b):
        if k3 >= 1:
            pairs.append((i, True, True))
    for i in range(b):
        if k2 >= 1 and k3 <= k2 - 1:
            pairs.append((i, True, False))
    for i in range(b):
        if k2 <= b - 1:
            pairs.append((i, False, False))
    return pairs


def allocation(b, n_queries):
    """Map query index -> (k2,k3). One query per solution per stratum, then the
    remainder round-robin over strata ordered by decreasing size."""
    out = []
    for k2 in range(b + 1):
        for k3 in range(k2 + 1):
            out.extend([(k2, k3)] * stratum_size(b, k2, k3))
    order = sorted(strata(b), key=lambda s: -stratum_size(b, s[0], s[1]))
    i = 0
    while len(out) < n_queries:
        out.append(order[i % len(order)])
        i += 1
    return out[:n_queries]


def single_level_allocation(b, n_queries):
    """Generation 3 allocation: query -> k2 only (k3 left free)."""
    out = []
    for k2 in range(b + 1):
        out.extend([k2] * (comb(b, k2) * (2 ** k2)))
    i = 0
    while len(out) < n_queries:
        out.append(i % (b + 1))
        i += 1
    return out[:n_queries]


def anchor_for(b, k2, k3, rank):
    """Anchor for the rank-th query inside stratum (k2,k3); rank cycles pairs."""
    pairs = feasible_anchors(b, k2, k3)
    return pairs[rank % len(pairs)]


def _rows(cells):
    out = []
    for r in range(GRID):
        out.append(' '.join('1' if (r, c) in cells else '0' for c in range(GRID)))
    return out


def canonical_structure(observation, s2, s3):
    """Canonical 'Structure: Layer 1/2/3 ...' text (parseable by the official parser)."""
    occ = set(occupied_cells(observation))
    lines = ['Structure:', 'Layer 1:'] + _rows(occ)
    if s2:
        lines += ['Layer 2:'] + _rows(s2)
        if s3:
            lines += ['Layer 3:'] + _rows(s3)
    return '\n'.join(lines)


def build_prompt(observation, k2, k3, anchor, prior_outputs):
    """Prompt for generation 4 (final): stratum + anchor + canonical priors.

    The target section mirrors the wording of the SZH adapted baseline prompt so
    parsing behaviour stays comparable; the stratum/anchor lines are the method's
    only addition to the question surface.
    """
    rows = '\n'.join(' '.join(observation[i:i + GRID]) for i in range(0, GRID * GRID, GRID))
    lines = [
        'Reconstruct a 3x3 stack of cubes from this TOP VIEW:',
        rows,
        'Rows run top to bottom; columns run left to right. Each displayed row is one grid row, not a height layer.',
        'Layer 1 is the ground. Each higher layer must be a subset of the layer directly below it.',
        'Every 0 in the top view MUST be 0 in ALL layers. Every 1 must be 1 in Layer 1 and may continue upward to height 2 or 3.',
        'Use between 1 and 3 layers. Copy the top view exactly as Layer 1.',
        '',
        'THIS QUERY\'S TARGET:',
    ]
    if k2 == 0:
        lines.append('- Layer 2 and Layer 3 must be omitted entirely (the structure is Layer 1 only).')
    else:
        lines.append(f'- Layer 2 must contain exactly {k2} block(s).')
        if k3 == 0:
            lines.append('- Layer 3 must be omitted entirely.')
        else:
            lines.append(f'- Layer 3 must contain exactly {k3} block(s).')
    if anchor is not None:
        idx, in_s2, s3_branch = anchor
        r, c = occupied_cells(observation)[idx]
        if not in_s2:
            lines.append(f'- The block at row {r + 1}, column {c + 1} of the top view must NOT continue into '
                         'Layer 2 (so it also stays out of Layer 3).')
        elif s3_branch:
            lines.append(f'- The block at row {r + 1}, column {c + 1} of the top view must continue into '
                         'Layer 2 AND into Layer 3.')
        else:
            lines.append(f'- The block at row {r + 1}, column {c + 1} of the top view must continue into '
                         'Layer 2 but must NOT continue into Layer 3.')
    lines += [
        '',
        'Return ONLY the following format with exactly 3 rows of 3 space-separated binary digits per layer:',
        'Structure:',
        'Layer 1:',
        '<row 1>',
        '<row 2>',
        '<row 3>',
    ]
    if k2 > 0:
        lines += ['Layer 2:', '<row 1>', '<row 2>', '<row 3>']
        if k3 > 0:
            lines += ['Layer 3:', '<row 1>', '<row 2>', '<row 3>']
    lines += [
        'Omit unused upper layers. Do not write explanations.',
        'Prior outputs to avoid repeating:',
        '\n'.join(prior_outputs) if prior_outputs else '(none)',
    ]
    return '\n'.join(lines)


def build_prompt_k2(observation, k2, prior_outputs):
    """Prompt for generation 3: k2 stratum only (no k3 line, no anchor)."""
    rows = '\n'.join(' '.join(observation[i:i + GRID]) for i in range(0, GRID * GRID, GRID))
    lines = [
        'Reconstruct a 3x3 stack of cubes from this TOP VIEW:',
        rows,
        'Rows run top to bottom; columns run left to right. Each displayed row is one grid row, not a height layer.',
        'Layer 1 is the ground. Each higher layer must be a subset of the layer directly below it.',
        'Every 0 in the top view MUST be 0 in ALL layers. Every 1 must be 1 in Layer 1 and may continue upward to height 2 or 3.',
        'Use between 1 and 3 layers. Copy the top view exactly as Layer 1.',
        '',
        'THIS QUERY\'S TARGET:',
        f'- Layer 2 must contain exactly {k2} block(s).',
        '',
        'Return ONLY the following format with exactly 3 rows of 3 space-separated binary digits per layer:',
        'Structure:',
        'Layer 1:',
        '<row 1>',
        '<row 2>',
        '<row 3>',
        'Layer 2:',
        '<row 1>',
        '<row 2>',
        '<row 3>',
        'Layer 3:',
        '<row 1>',
        '<row 2>',
        '<row 3>',
        'Omit unused upper layers. Do not write explanations.',
        'Prior outputs to avoid repeating:',
        '\n'.join(prior_outputs) if prior_outputs else '(none)',
    ]
    return '\n'.join(lines)


def build_prompt_verbal(observation, k2, k3, prior_outputs):
    """Prompt for generation 1: verbal stratification only, no anchor."""
    return build_prompt(observation, k2, k3, None, prior_outputs)


def build_prompt_free(observation, prior_outputs):
    """Prompt for generation 2: no stratification lines, priors only
    (isolates the validity-repair filter; question surface = baseline style)."""
    rows = '\n'.join(' '.join(observation[i:i + GRID]) for i in range(0, GRID * GRID, GRID))
    lines = [
        'Reconstruct a 3x3 stack of cubes from this TOP VIEW:',
        rows,
        'Rows run top to bottom; columns run left to right. Each displayed row is one grid row, not a height layer.',
        'Layer 1 is the ground. Each higher layer must be a subset of the layer directly below it.',
        'Every 0 in the top view MUST be 0 in ALL layers. Every 1 must be 1 in Layer 1 and may continue upward to height 2 or 3.',
        'Use between 1 and 3 layers. Copy the top view exactly as Layer 1.',
        '',
        'Return ONLY the following format with exactly 3 rows of 3 space-separated binary digits per layer:',
        'Structure:',
        'Layer 1:',
        '<row 1>',
        '<row 2>',
        '<row 3>',
        'Layer 2:',
        '<row 1>',
        '<row 2>',
        '<row 3>',
        'Layer 3:',
        '<row 1>',
        '<row 2>',
        '<row 3>',
        'Omit unused upper layers. Do not write explanations.',
        'Prior outputs to avoid repeating:',
        '\n'.join(prior_outputs) if prior_outputs else '(none)',
    ]
    return '\n'.join(lines)


def _ordered_cells(cells):
    return sorted(cells)


def _rotated_order(cells, anchor_idx):
    """Query-specific reading order: start right after the anchor column, wrap."""
    if anchor_idx is None:
        return cells
    return cells[anchor_idx + 1:] + cells[:anchor_idx + 1]


def repair(obs_cells, layers, k2, k3, anchor=None):
    """Repair a parsed raw structure into stratum (k2,k3), optionally enforcing
    the level-2 anchor (column in/out of S2, and in/out of S3).

    layers: list of 3x3 binary grids (official Structure3D.layers) or None when
    parsing failed. anchor: (cell, in_s2, s3_branch) with cell one of obs_cells,
    in_s2 a bool, s3_branch True / False / None, or anchor None.
    Returns (S2, S3) as frozensets of (r,c) cells.

    Rules (deterministic):
      - Layer 1 is always the full top view (forced skeleton).
      - S3 subset of S2; |S2| = k2, |S3| = k3 exactly.
      - The anchor, when given, is enforced on S2 (include / exclude the cell)
        and on S3 (include / exclude).
      - Trimming/filling use a per-query rotated reading order (rotation starts
        after the anchor column) so queries with different anchors complete to
        different S2/S3 patterns instead of colliding on the reading-order first.
      - Parse failure falls back to the order-minimal structure of the anchored
        stratum.
    """
    occ = obs_cells
    anchor_cell = None if anchor is None else anchor[0]
    in_s2 = None if anchor is None else anchor[1]
    s3_branch = None if anchor is None else anchor[2]
    order = _rotated_order(occ, None if anchor is None else occ.index(anchor_cell))
    if layers is None or not layers:
        if in_s2:
            s2 = [anchor_cell] + [c for c in order if c != anchor_cell][:k2 - 1]
        else:
            s2 = [c for c in order if c != anchor_cell][:k2]
        s3_order = [c for c in order if c in s2]
        if s3_branch:
            s3 = [anchor_cell] + [c for c in s3_order if c != anchor_cell][:k3 - 1]
        else:
            s3 = [c for c in s3_order if c != anchor_cell][:k3]
        return frozenset(s2), frozenset(s3)

    def cells_on(layer_idx):
        if layer_idx >= len(layers):
            return set()
        out = set()
        for r, row in enumerate(layers[layer_idx]):
            for c, v in enumerate(row):
                if v:
                    out.add((r, c))
        return out & set(occ)

    s2 = [c for c in occ if c in cells_on(1)]
    s3 = [c for c in occ if c in cells_on(2)]
    # anchor enforcement on S2 (before size fixing)
    if anchor is not None:
        if in_s2 and anchor_cell not in s2:
            s2.append(anchor_cell)
        if not in_s2 and anchor_cell in s2:
            s2.remove(anchor_cell)
    # size fixing (rotated order; anchor cell protected / excluded)
    if len(s2) > k2:
        drop = [c for c in reversed(order) if c != anchor_cell]
        for c in drop:
            if len(s2) == k2:
                break
            if c in s2 and c not in s3:
                s2.remove(c)
        for c in drop:
            if len(s2) == k2:
                break
            if c in s2:
                s2.remove(c)
    if len(s2) < k2:
        for c in order:
            if c in s2:
                continue
            if not in_s2 and c == anchor_cell:
                continue
            s2.append(c)
            if len(s2) == k2:
                break
    s3 = [c for c in s3 if c in s2]
    # S3 anchor enforcement
    if anchor is not None:
        if s3_branch and anchor_cell not in s3:
            s3.append(anchor_cell)
        if not s3_branch and anchor_cell in s3:
            s3.remove(anchor_cell)
    s3_order = [c for c in order if c in s2]
    if len(s3) > k3:
        if s3_branch and anchor_cell in s3:
            s3 = [anchor_cell] + [c for c in s3_order if c != anchor_cell and c in s3][:k3 - 1]
        else:
            s3 = [c for c in s3_order if c in s3][:k3]
    if len(s3) < k3:
        for c in s3_order:
            if not s3_branch and c == anchor_cell:
                continue
            if c not in s3:
                s3.append(c)
            if len(s3) == k3:
                break
    return frozenset(s2), frozenset(s3)


def repair_free(obs_cells, layers):
    """Generation 2 repair: validity only (no count pinning)."""
    occ = obs_cells
    if layers is None or not layers:
        return frozenset(), frozenset()
    s2 = set()
    s3 = set()
    if len(layers) >= 2:
        for r, row in enumerate(layers[1]):
            for c, v in enumerate(row):
                if v:
                    s2.add((r, c))
    if len(layers) >= 3:
        for r, row in enumerate(layers[2]):
            for c, v in enumerate(row):
                if v:
                    s3.add((r, c))
    s2 &= set(occ)
    s3 &= s2
    return frozenset(s2), frozenset(s3)


def repair_k2(obs_cells, layers, k2):
    """Generation 3 repair: pin |S2| = k2, leave S3 free within S2."""
    occ = obs_cells
    if layers is None or not layers:
        s2 = list(occ[:k2])
        return frozenset(s2), frozenset()
    s2, s3 = repair_free(occ, layers)
    s2 = [c for c in occ if c in s2]
    if len(s2) > k2:
        for c in reversed(s2):
            if len(s2) == k2:
                break
            if c not in s3:
                s2.remove(c)
        for c in reversed(s2):
            if len(s2) == k2:
                break
            s2.remove(c)
    if len(s2) < k2:
        for c in occ:
            if c not in s2:
                s2.append(c)
            if len(s2) == k2:
                break
    s3 = frozenset(c for c in s3 if c in s2)
    return frozenset(s2), s3
