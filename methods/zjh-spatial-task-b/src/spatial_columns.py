"""Represent voxel stacks as heights indexed by the occupied columns."""

import hypospace_runner
from adapted_baseline import transform as adapted_transform


HISTORY_HEADER = 'Prior outputs to avoid repeating:\n'


def _column_heights(structure, observation, positions, parser):
    """Encode a stack only when its height tuple represents it losslessly."""
    if structure.height > 3 or not parser.validate_structure_matches_observations(
        structure, observation
    ):
        return None
    return tuple(sum(int(layer[row, col]) for layer in structure.layers) for row, col in positions)


def _transform(prompt, context, *, encode_history):
    baseline = adapted_transform(prompt, context)
    instructions, _, history = baseline.partition(HISTORY_HEADER)
    observation = context['observation']
    positions = [divmod(i, 3) for i, cell in enumerate(observation) if cell == '1']
    labels = [f'C{i}' for i in range(1, len(positions) + 1)]
    coordinates = ', '.join(
        f'{label} = (row {row + 1}, column {col + 1})'
        for label, (row, col) in zip(labels, positions)
    )
    column_instructions = (
        f'Occupied columns: {coordinates}.\n'
        f'Plan one height tuple in this fixed order: ({", ".join(labels)}). '
        'Each height is 1, 2, or 3. Any prior tuple uses this same order. '
        'Choose a tuple different from earlier valid stacks.\n'
        'Convert your tuple to the original grid: in Layer k, put a 1 at the listed '
        'coordinates whose chosen height is at least k. Put a 0 everywhere else. '
        'Return only the Structure and Layer grids above.\n'
    )
    if not encode_history or history.strip() == '(none)':
        return instructions + column_instructions + HISTORY_HEADER + history

    official, _ = hypospace_runner.upstream()
    parser = object.__new__(official.Benchmark3D)
    encoded = []
    # Adapted formats each distinct parsed structure starting with Layer 1.
    # Preserve its ordering and retain full grids outside the tuple's domain.
    for previous in history.rstrip('\n').split('\nLayer 1:\n'):
        if not previous.startswith('Layer 1:\n'):
            previous = 'Layer 1:\n' + previous
        structure = parser.parse_llm_response(previous)
        if structure is not None:
            heights = _column_heights(structure, observation, positions, parser)
            if heights is not None:
                encoded.append('(' + ', '.join(map(str, heights)) + ')')
                continue
        encoded.append(previous)
    return instructions + column_instructions + HISTORY_HEADER + '\n'.join(encoded) + '\n'


def transform(prompt, context):
    """Use the same height representation for planning and valid history."""
    return _transform(prompt, context, encode_history=True)


def grid_history(prompt, context):
    """Ablation that retains the Adapted Baseline's layer-grid history."""
    return _transform(prompt, context, encode_history=False)
