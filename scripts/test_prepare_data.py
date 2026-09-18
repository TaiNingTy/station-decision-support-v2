"""Small regression checks for material source/weight/unit mistakes."""
import math
import unittest

from prepare_data import ROOT, REPLICATES, WEIGHT, abs_observations, day_factor, logit_jackknife_ci, number, ratio, weighted_proportion


class SourceAndMethodTests(unittest.TestCase):
    def test_abs_matches_verified_published_rows(self):
        result = abs_observations(ROOT / "raw/abs_west_melbourne_2021.html")
        observations = {r["metric"]: r for r in result["observations"]}
        self.assertEqual(observations["resident_population"]["value"], 8025)
        self.assertEqual(observations["median_weekly_household_income"]["value"], 1788)
        self.assertEqual(observations["annual_equivalent_of_weekly_household_median"]["value"], 92976)
        share = observations["household_income_above_threshold_share"]
        self.assertAlmostEqual(share["value"], .237)
        self.assertEqual(share["threshold"]["basis"], "household")

    def test_day_filter_changes_expanded_counts_not_common_factor_ratios(self):
        self.assertEqual(100 * day_factor("Weekday"), 140)
        self.assertEqual(100 * day_factor("Weekend"), 350)
        self.assertAlmostEqual(ratio(40 * day_factor("Weekday"), 100 * day_factor("Weekday")), .4)

    def test_sample_counts_are_not_expanded_shares(self):
        a = {WEIGHT: "100", **{key: "100" for key in REPLICATES}, "is_pt": True}
        b = {WEIGHT: "1", **{key: "1" for key in REPLICATES}, "is_pt": False}
        result = weighted_proportion([a, b], lambda r: r["is_pt"])
        self.assertAlmostEqual(result["value"], 100 / 101)
        self.assertNotAlmostEqual(result["value"], .5)
        for bound in result["interval_95"]:
            self.assertAlmostEqual(bound, 100 / 101)

    def test_zero_and_missing_weights_are_different(self):
        self.assertEqual(number("0", "weight"), 0)
        for bad in ["", None, "NaN", "inf", "-1"]:
            with self.assertRaises(ValueError):
                number(bad, "weight")

    def test_no_fake_confidence_for_undefined_logit(self):
        self.assertIsNone(logit_jackknife_ci(0, [0] * 10)["interval_95"])
        self.assertIsNone(logit_jackknife_ci(1, [1] * 10)["interval_95"])
        self.assertIsNone(logit_jackknife_ci(.5, [None] + [.5] * 9)["interval_95"])
        self.assertIsNone(ratio(0, 0))
        with self.assertRaises(ValueError):
            logit_jackknife_ci(.5, [.5] * 9)


if __name__ == "__main__":
    unittest.main()
