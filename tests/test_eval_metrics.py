import unittest

from tests import _helpers  # noqa: F401

from utils.eval_metrics import (
    heading_level_accuracy,
    heading_precision_recall_f1,
    non_space_preservation_rate,
    spacing_edit_distance,
    warning_count_delta,
)


class EvalMetricsTests(unittest.TestCase):
    def test_heading_precision_recall_f1(self):
        metrics = heading_precision_recall_f1(["h1", "h2"], ["h2", "h3"])

        self.assertEqual(metrics["precision"], 0.5)
        self.assertEqual(metrics["recall"], 0.5)
        self.assertEqual(metrics["f1"], 0.5)

    def test_heading_level_accuracy_ignores_missing_predictions(self):
        accuracy = heading_level_accuracy({"h1": 1, "h2": None}, {"h1": 1, "h2": 2})

        self.assertEqual(accuracy, 1.0)

    def test_spacing_metrics(self):
        self.assertEqual(non_space_preservation_rate("a b c", "abc"), 1.0)
        self.assertGreater(spacing_edit_distance("a b c", "abc"), 0)

    def test_warning_count_delta(self):
        delta = warning_count_delta(
            [{"code": "orphan_table"}],
            [{"code": "orphan_table"}, {"code": "orphan_figure"}],
            codes=["orphan_table", "orphan_figure"],
        )

        self.assertEqual(delta, {"orphan_figure": 1, "orphan_table": 0})


if __name__ == "__main__":
    unittest.main()
