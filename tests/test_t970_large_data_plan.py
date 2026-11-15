import importlib.util
from pathlib import Path
import unittest

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('large_data_plan', root / 'scripts/check-t970-large-data-plan.py')
plan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plan)


class LargeDataPlanTest(unittest.TestCase):
    def test_reviewed_window_stays_clear_of_old_overlay(self):
        result = plan.check_window(plan.FIRST, plan.PAGES)
        self.assertEqual(result['last_lba'], 61953352)
        self.assertEqual(result['bitmap_blocks'], 584)
        self.assertLess(result['last_lba'], 62065403)

    def test_geometry_fails_closed(self):
        for first, pages, partition in ((plan.FIRST - 1, plan.PAGES, (plan.PART_FIRST, plan.PART_LAST)),
                                        (plan.FIRST, plan.PAGES + 1, (plan.PART_FIRST, plan.PART_LAST)),
                                        (plan.FIRST, plan.PAGES, (plan.PART_FIRST, plan.PART_LAST + 1))):
            with self.subTest(first=first, pages=pages, partition=partition):
                with self.assertRaises(ValueError):
                    plan.check_window(first, pages, partition)


if __name__ == '__main__':
    unittest.main()
