import sys
import unittest
from pathlib import Path
from unittest.mock import patch

METHOD = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(METHOD / 'src'), str(METHOD.parents[1] / 'src')]
from hypospace_runner import upstream
from spatial_columns import HISTORY_HEADER, grid_history, transform


PINNED_BENCHMARK = upstream()


class SpatialColumnsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.enterClassContext(patch('hypospace_runner.upstream', return_value=PINNED_BENCHMARK))

    def test_history_preserves_column_order_and_keeps_unencodable_grids(self):
        ground = 'Layer 1:\n0 1 0\n0 0 0\n1 0 0'
        second = 'Layer 2:\n0 0 0\n0 0 0\n1 0 0'
        zero = 'Layer 3:\n0 0 0\n0 0 0\n0 0 0'
        valid = f'{ground}\n{second}'
        invalid = 'Layer 1:\n0 0 0\n0 0 0\n1 0 0'
        floating = f'{ground}\nLayer 2:\n0 0 0\n0 0 0\n0 0 0\nLayer 3:\n0 0 0\n0 0 0\n1 0 0'
        context = {
            'observation': '010000100',
            'query_index': 5,
            'history': [valid, invalid, f'{valid}\n{zero}', 'unparseable', floating],
        }

        prompt, history = transform('', context).split(HISTORY_HEADER)
        control, control_history = grid_history('', context).split(HISTORY_HEADER)

        self.assertEqual(prompt, control)
        self.assertIn('C1 = (row 1, column 2), C2 = (row 3, column 1)', prompt)
        self.assertEqual(history, f'(1, 2)\n{invalid}\n{floating}\n')
        self.assertEqual(control_history, f'{valid}\n{invalid}\n{floating}\n')

    def test_empty_history_uses_the_same_prompt_in_both_arms(self):
        context = {'observation': '000010000', 'query_index': 0, 'history': []}
        self.assertEqual(transform('', context), grid_history('', context))
        self.assertTrue(transform('', context).endswith(HISTORY_HEADER + '(none)\n'))
