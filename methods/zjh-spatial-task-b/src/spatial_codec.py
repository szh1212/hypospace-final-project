"""Generate a compact column-height code and decode it into voxel layers."""

import json

import hypospace_runner
from adapted_baseline import transform as adapted_transform
from spatial_columns import _column_heights


ALLOWED_HEIGHTS = (1, 2, 3)


def output_schema(size):
    return {
        'type': 'object',
        'properties': {
            'heights': {
                'type': 'array', 'minItems': size, 'maxItems': size,
                'items': {'type': 'integer', 'enum': list(ALLOWED_HEIGHTS)},
            },
        },
        'required': ['heights'],
        'additionalProperties': False,
    }


def _positions(context, cyclic):
    cells = [divmod(index, 3) for index, value in enumerate(context['observation']) if value == '1']
    shift = context['query_index'] % len(cells) if cyclic else 0
    return cells[shift:] + cells[:shift]


def _prompt(prompt, context, *, cyclic):
    baseline = adapted_transform(prompt, context)
    top_view, _, _ = baseline.partition('Layer 1 is the ground.')
    positions = _positions(context, cyclic)
    observation = context['observation']
    official, _ = hypospace_runner.upstream()
    parser = object.__new__(official.Benchmark3D)
    prior = set()
    for response in context['history']:
        structure = parser.parse_llm_response(response)
        if structure is None:
            continue
        heights = _column_heights(structure.normalize(), observation, positions, parser)
        if heights is not None:
            prior.add(heights)

    cells = ', '.join(f'(row {row + 1}, column {col + 1})' for row, col in positions)
    history = '\n'.join(json.dumps(heights) for heights in sorted(prior)) or '(none yet)'
    return (
        top_view
        + f'Encode your reconstruction in this occupied-cell order: {cells}.\n'
        + f'Give exactly {len(positions)} heights, one for each listed cell. Each height is 1, 2, or 3. '
        + 'A height counts the blocks from the ground up.\n'
        + f'Previously found height codes in this same order:\n{history}\n'
        + 'Choose a height code that is different from all those listed.\n'
        + 'Return a JSON object with one field named "heights" and put your height array in it.\n'
    )


def _decode(response, context, *, cyclic):
    try:
        code = json.loads(response)
    except json.JSONDecodeError:
        return response
    positions = _positions(context, cyclic)
    if not isinstance(code, dict) or code.keys() != {'heights'}:
        return response
    heights = code['heights']
    if (not isinstance(heights, list) or len(heights) != len(positions)
            or any(type(height) is not int or height not in ALLOWED_HEIGHTS for height in heights)):
        return response

    grid = [0] * 9
    for (row, col), height in zip(positions, heights):
        grid[row * 3 + col] = height
    lines = ['Structure:']
    for layer in range(1, max(heights) + 1):
        lines.append(f'Layer {layer}:')
        lines.extend(' '.join(str(int(height >= layer)) for height in grid[row:row + 3])
                     for row in range(0, 9, 3))
    return '\n'.join(lines)


def row_major(prompt, context):
    return _prompt(prompt, context, cyclic=False)


def decode_row_major(response, context):
    return _decode(response, context, cyclic=False)


def cyclic(prompt, context):
    return _prompt(prompt, context, cyclic=True)


def decode_cyclic(response, context):
    return _decode(response, context, cyclic=True)
