import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.kinematics import AdaptiveEMAFilter, clamp_joint_angles, is_near_singularity


class TestKinematics(unittest.TestCase):
    def test_adaptive_ema_filter_smooths_small_changes(self):
        filter_x = AdaptiveEMAFilter()
        first = filter_x.update(10.0)
        second = filter_x.update(11.0)

        self.assertAlmostEqual(first, 10.0, places=6)
        self.assertLess(second, 11.0)
        self.assertGreater(second, 10.0)

    def test_clamp_joint_angles_applies_limits(self):
        result = clamp_joint_angles({
            "joint1": 200.0,
            "joint2": -100.0,
            "joint3": 10.0,
        })
        self.assertEqual(result["joint1"], 170.0)
        self.assertEqual(result["joint2"], -90.0)
        self.assertEqual(result["joint3"], 10.0)

    def test_is_near_singularity_detects_joint3(self):
        singular, message = is_near_singularity({"joint3": 1.0})
        self.assertTrue(singular)
        self.assertIn("joint3", message)

    def test_is_near_singularity_detects_joint5(self):
        singular, message = is_near_singularity({"joint5": 89.0})
        self.assertTrue(singular)
        self.assertIn("joint5", message)


if __name__ == "__main__":
    unittest.main()
