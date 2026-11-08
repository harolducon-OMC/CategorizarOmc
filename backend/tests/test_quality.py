import unittest

from core import quality


class ComputeQualityTests(unittest.TestCase):
    def test_empty_sample(self):
        result = quality.compute_quality([])
        self.assertEqual(result["reviewed"], 0)
        self.assertIsNone(result["agreement"])

    def test_perfect_agreement(self):
        pairs = [(["Precio"], ["Precio"]), (["Servicio"], ["Servicio"]), (["Precio", "Calidad"], ["Calidad", "Precio"])]
        result = quality.compute_quality(pairs)
        self.assertEqual(result["agreement"], 1.0)
        self.assertEqual(result["level"], "alto")
        self.assertEqual(result["micro_f1"], 1.0)
        self.assertFalse(result["reliable"])  # menos de 50 filas

    def test_per_category_precision_recall_and_f1(self):
        pairs = [
            (["Precio"], ["Precio"]), (["Precio"], ["Precio"]), (["Precio"], ["Servicio"]),   # 1 falso positivo de Precio
            (["Servicio"], ["Servicio"]), (["Servicio"], ["Precio"]),                        # 1 falso positivo de Servicio
        ]
        result = quality.compute_quality(pairs)
        by_category = {item["category"]: item for item in result["categories"]}
        self.assertAlmostEqual(by_category["Precio"]["precision"], 2 / 3)
        self.assertAlmostEqual(by_category["Precio"]["recall"], 2 / 3)
        self.assertAlmostEqual(by_category["Servicio"]["f1"], 0.5)
        self.assertAlmostEqual(result["agreement"], 3 / 5)
        self.assertEqual(result["level"], "bajo")

    def test_multilabel_partial_match_is_not_exact(self):
        result = quality.compute_quality([(["Precio", "Calidad"], ["Precio"])])
        self.assertEqual(result["agreement"], 0.0)
        by_category = {item["category"]: item for item in result["categories"]}
        self.assertEqual(by_category["Precio"]["f1"], 1.0)
        self.assertEqual(by_category["Calidad"]["precision"], 0.0)

    def test_kappa_only_for_single_label_rows(self):
        single = quality.compute_quality([(["A"], ["A"]), (["B"], ["B"]), (["A"], ["B"]), (["B"], ["B"])])
        self.assertIsNotNone(single["kappa"])
        self.assertLess(single["kappa"], 1.0)
        multi = quality.compute_quality([(["A", "B"], ["A"])])
        self.assertIsNone(multi["kappa"])

    def test_weakest_categories_need_enough_support(self):
        pairs = [(["A"], ["B"])] * 3 + [(["A"], ["A"])] * 5 + [(["C"], ["D"])]
        weakest = {item["category"] for item in quality.compute_quality(pairs)["weakest"]}
        self.assertIn("B", weakest)
        self.assertNotIn("D", weakest)  # solo 1 caso: no es concluyente

    def test_wilson_interval_widens_with_small_samples(self):
        small = quality.wilson_interval(9, 10)
        large = quality.wilson_interval(90, 100)
        self.assertGreater(small[1] - small[0], large[1] - large[0])
        self.assertTrue(0 <= small[0] <= 0.9 <= small[1] <= 1)

    def test_reliable_flag_after_minimum_sample(self):
        pairs = [(["A"], ["A"])] * quality.MIN_RELIABLE_SAMPLE
        self.assertTrue(quality.compute_quality(pairs)["reliable"])


class PickSampleTests(unittest.TestCase):
    def test_sample_skips_reviewed_rows_and_never_repeats(self):
        sample = quality.pick_sample(list(range(20)), reviewed={0, 1, 2}, size=10, seed=1)
        self.assertEqual(len(sample), 10)
        self.assertEqual(len(set(sample)), 10)
        self.assertFalse(set(sample) & {0, 1, 2})

    def test_sample_is_capped_by_available_rows(self):
        self.assertEqual(quality.pick_sample([1, 2, 3], reviewed={1}, size=10, seed=0), [2, 3])


if __name__ == "__main__":
    unittest.main(verbosity=2)
