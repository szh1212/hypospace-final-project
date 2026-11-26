import sys
import unittest
from pathlib import Path


METHOD = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(METHOD / 'src'), str(next(p for p in METHOD.parents if (p/'.git').exists()) / 'src')]

from spatial_codec import decode_cyclic, decode_row_major, output_schema


class CodecTests(unittest.TestCase):
    def setUp(self):
        self.context = {'observation': '010000100', 'query_index': 1}

    def test_cycle_inverse_uses_original_coordinates(self):
        ground = 'Structure:\nLayer 1:\n0 1 0\n0 0 0\n1 0 0'
        upper_at_first_cell = '\n0 1 0\n0 0 0\n0 0 0'
        expected = ground + '\nLayer 2:' + upper_at_first_cell + '\nLayer 3:' + upper_at_first_cell
        self.assertEqual(decode_cyclic('{"heights":[1,3]}', self.context), expected)
        self.assertEqual(decode_row_major('{"heights":[3,1]}', self.context), expected)

    def test_unrecognized_codes_are_unchanged_for_scoring(self):
        bad_codes = ('{"heights":[1]}', '{"heights":[1,4]}', '{"heights":[true,2]}',
                     '{"heights":[1,3],"notes":"extra"}', '{"heights":[1,3]}\nExtra words')
        for response in bad_codes:
            with self.subTest(response=response):
                self.assertEqual(decode_cyclic(response, self.context), response)

    def test_one_column_schema_has_exactly_one_height(self):
        heights = output_schema(1)['properties']['heights']
        self.assertEqual((heights['minItems'], heights['maxItems']), (1, 1))
        self.assertEqual(heights['items']['enum'], [1, 2, 3])
