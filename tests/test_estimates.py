"""Retained potion usage/cost timing after removal of the restock feature."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from potion_tracking import Usage,estimated_cost

class UsageTimelineTests(unittest.TestCase):
    def stock(self,start=200,drop=1):
        u=Usage()
        for i in range(22):u.observe(start-drop*i,i*3)
        return u
    def test_known_stock_usage_rate_and_cost(self):
        u=self.stock()
        self.assertEqual((u.value,u.used,u.seconds,u.per_minute()),(180,20,60,20))
        self.assertEqual(estimated_cost(u,150),(3000,180000))
        self.assertFalse(hasattr(u,'restock'));self.assertFalse(hasattr(u,'recent'))
    def test_two_items_keep_independent_usage(self):
        a,b=self.stock(),self.stock(500,2)
        self.assertEqual((a.value,a.per_minute(),b.value,b.per_minute()),(180,20,460,40))
    def test_hidden_gap_preserves_totals_without_blind_consumption(self):
        u=self.stock();u.gap();u.observe(100,500);u.observe(99,503)
        self.assertEqual((u.used,u.seconds,u.value),(20,60,100))
    def test_long_gap_preserves_totals_without_blind_consumption(self):
        u=self.stock();u.observe(100,500);u.observe(99,503)
        self.assertEqual((u.used,u.seconds,u.value),(20,60,100))
    def test_unreadable_count_clears_stock_not_session_totals(self):
        u=self.stock();u.observe(None,66)
        self.assertIsNone(u.value);self.assertEqual((u.used,u.seconds),(20,60))
    def test_large_drop_still_requires_resync(self):
        u=self.stock();u.observe(20,66);u.observe(20,69)
        self.assertTrue(u.locked);self.assertEqual(u.used,20)
    def test_one_bad_dip_does_not_count_as_consumption(self):
        u=self.stock();u.observe(20,66);u.observe(180,69);u.observe(180,72)
        self.assertEqual(u.used,20);self.assertFalse(u.locked)
    def test_refill_interval_does_not_dilute_rate(self):
        u=self.stock();u.observe(500,66);u.observe(499,69)
        self.assertEqual((u.used,u.seconds,u.per_minute()),(20,60,20))
    def test_irregular_sampling_uses_real_interval_duration(self):
        u=Usage()
        for at in [0,4,9,12,20,25,31,38,44,49,55,60,66]:u.observe(1000-at,at)
        self.assertEqual((u.value,u.used,u.seconds,u.per_minute()),(940,60,60,60))

if __name__=='__main__':unittest.main()
