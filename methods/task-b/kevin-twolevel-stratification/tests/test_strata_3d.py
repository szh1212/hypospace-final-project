"""Unit tests for the 3D stratification / repair logic (no model, no network)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
import strata_3d as S


def layers_from(s2, s3, obs):
    occ = set(S.occupied_cells(obs))
    grid = [[[0] * 3 for _ in range(3)] for _ in range(3)]
    for r, c in occ:
        grid[0][r][c] = 1
    for r, c in s2:
        grid[1][r][c] = 1
    for r, c in s3:
        grid[2][r][c] = 1
    return grid


class TestStrata(unittest.TestCase):
    def test_strata_partition_space(self):
        for b in (1, 2, 3):
            total = sum(S.stratum_size(b, k2, k3) for k2, k3 in S.strata(b))
            self.assertEqual(total, 3 ** b)

    def test_stratum_solutions_count(self):
        for b in (1, 2, 3):
            for k2, k3 in S.strata(b):
                sols = S.stratum_solutions(b, k2, k3)
                self.assertEqual(len(sols), S.stratum_size(b, k2, k3))
                for s2, s3 in sols:
                    self.assertEqual(len(s2), k2)
                    self.assertEqual(len(s3), k3)
                    self.assertTrue(s3 <= s2)

    def test_allocation_covers_all_strata_at_native_budget(self):
        for b in (1, 2, 3):
            alloc = S.allocation(b, 3 ** b)
            self.assertEqual(len(alloc), 3 ** b)
            self.assertEqual(set(alloc), set(S.strata(b)))
            counts = {s: alloc.count(s) for s in set(alloc)}
            for k2, k3 in counts:
                self.assertEqual(counts[(k2, k3)], S.stratum_size(b, k2, k3))

    def test_anchors_cover_queries_per_stratum(self):
        for b in (1, 2, 3):
            for k2, k3 in S.strata(b):
                c = S.stratum_size(b, k2, k3)
                pairs = S.feasible_anchors(b, k2, k3)
                self.assertGreaterEqual(len(pairs), c)

    def test_repair_counts_exact_and_subset(self):
        obs = '101010000'
        occ = S.occupied_cells(obs)
        for k2 in range(4):
            for k3 in range(k2 + 1):
                s2, s3 = S.repair(occ, layers_from({(0, 0)}, {(0, 0), (1, 0)}, obs), k2, k3)
                self.assertEqual(len(s2), k2)
                self.assertEqual(len(s3), k3)
                self.assertTrue(s3 <= s2 <= set(occ))

    def test_repair_parse_failure_fallback(self):
        obs = '110100000'
        occ = S.occupied_cells(obs)
        s2, s3 = S.repair(occ, None, 1, 1)
        self.assertEqual(s2, frozenset(occ[:1]))
        self.assertEqual(s3, frozenset(occ[:1]))

    def test_repair_unsupported_layer3_removed(self):
        obs = '111000000'
        occ = S.occupied_cells(obs)
        # layer 3 has a block with no support in layer 2
        raw = layers_from(set(), {(0, 2)}, obs)
        s2, s3 = S.repair(occ, raw, 1, 1)
        self.assertEqual(len(s2), 1)
        self.assertEqual(len(s3), 1)
        self.assertTrue(s3 <= s2)

    def test_repair_k2_pins_only_s2(self):
        obs = '111000000'
        occ = S.occupied_cells(obs)
        s2, s3 = S.repair_k2(occ, layers_from({(0, 0), (0, 1)}, {(0, 1)}, obs), 1)
        self.assertEqual(len(s2), 1)
        self.assertTrue(s3 <= s2)

    def test_repair_anchor_enforced(self):
        obs = '111000000'
        occ = S.occupied_cells(obs)
        # identical raw input, different anchors -> different S2 completions
        raw = layers_from({(0, 0)}, {(0, 0)}, obs)
        for k2 in (1, 2):
            for i, cell in enumerate(occ):
                s2_in, _ = S.repair(occ, raw, k2, 0, (cell, True, False))
                s2_out, _ = S.repair(occ, raw, k2, 0, (cell, False, False))
                self.assertIn(cell, s2_in)
                self.assertNotIn(cell, s2_out)
                self.assertEqual(len(s2_in), k2)
                self.assertEqual(len(s2_out), k2)
        # S3 branch enforcement
        for i, cell in enumerate(occ):
            s2_a, s3_a = S.repair(occ, raw, 2, 1, (cell, True, True))
            s2_b, s3_b = S.repair(occ, raw, 2, 1, (cell, True, False))
            self.assertIn(cell, s3_a)
            self.assertNotIn(cell, s3_b)
            self.assertEqual(len(s3_a), 1)
            self.assertEqual(len(s3_b), 1)
        # every stratum solution survives its own repair (idempotence under anchor=False)
        for b in (1, 2, 3):
            obs_full = '1' * b + '0' * (9 - b)
            occ_full = S.occupied_cells(obs_full)
            for k2, k3 in S.strata(b):
                for s2, s3 in S.stratum_solutions(b, k2, k3):
                    cells_s2 = frozenset(occ_full[i] for i in s2)
                    cells_s3 = frozenset(occ_full[i] for i in s3)
                    layers = layers_from(cells_s2, cells_s3, obs_full)
                    r2, r3 = S.repair(occ_full, layers, k2, k3)
                    self.assertEqual(r2, cells_s2)
                    self.assertEqual(r3, cells_s3)

    def test_canonical_parse_back_roundtrip(self):
        import importlib
        from pathlib import Path
        cur = Path(__file__).resolve().parent
        up = None
        for _ in range(8):
            probe = cur / '.cache' / 'hypospace'
            if probe.exists():
                up = probe
                break
            cur = cur.parent
        self.assertIsNotNone(up, '.cache/hypospace checkout not found')
        sys.path.insert(0, str(up / '3d'))
        official = importlib.import_module('run_3d_benchmark')
        bench = official.Benchmark3D(str(Path(__file__).resolve().parents[1] / 'data' / '3d.json'))
        for obs in ('100000000', '110000000', '111000000', '101010000', '111111111'):
            occ = S.occupied_cells(obs)
            for s2 in (frozenset(), frozenset(occ[:1]), frozenset(occ)):
                s3 = frozenset(c for c in s2)
                text = S.canonical_structure(obs, s2, s3)
                parsed = bench.parse_llm_response(text)
                self.assertIsNotNone(parsed)
                self.assertTrue(bench.validate_structure_matches_observations(parsed, obs))


if __name__ == '__main__':
    unittest.main()
