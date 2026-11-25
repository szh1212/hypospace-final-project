import sys
import unittest
from pathlib import Path


METHOD = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(METHOD / 'src'), str(METHOD.parents[1] / 'src')]

from spatial_codec import decode_cyclic, decode_row_major


class CodecTests(unittest.TestCase):
    def setUp(self):
        self.context = {'observation': '010000100', 'query_index': 1}

    def test_cycle_inverse_uses_original_coordinates(self):
        ground = 'Structure:\nLayer 1:\n0 1 0\n0 0 0\n1 0 0'
        upper_at_first_cell = '\n0 1 0\n0 0 0\n0 0 0'
        expected = ground + '\nLayer 2:' + upper_at_first_cell + '\nLayer 3:' + upper_at_first_cell
        self.assertEqual(decode_cyclic('Heights: 1 3', self.context), expected)
        self.assertEqual(decode_row_major('Heights: 3 1', self.context), expected)

    def test_unrecognized_codes_are_unchanged_for_scoring(self):
        for response in ('Heights: 1', 'Heights: 1 4', 'Heights: 1 3\nExtra words'):
            with self.subTest(response=response):
                self.assertEqual(decode_cyclic(response, self.context), response)
