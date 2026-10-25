"""Characterize the requested original rate behavior, including its limitations.

These are not claims that active-time rates equal net real-hour earnings.
A separately authorized rate-policy correction should update this contract.
"""
from ast_contract import legacy_dump
import ast,hashlib,json,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import maple_exp as m

class OriginalRateAuditTests(unittest.TestCase):
    def test_rate_classes_match_pinned_original_source(self):
        fixture=json.loads((Path(__file__).parent/'frames/original-rate-contract.json').read_text())
        # Session has the explicitly requested upstream PQ extension; its default-mode behavior is tested below.
        fixture['class_AST_sha256']['Session'] = json.loads((Path(__file__).parent/'frames/pq-session-contract.json').read_text())['Session']
        tree=ast.parse((Path(__file__).resolve().parents[1]/'maple_exp.py').read_text())
        for name,expected in fixture['class_AST_sha256'].items():
            with self.subTest(name=name):
                node=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==name)
                self.assertEqual(hashlib.sha256(legacy_dump(node).encode()).hexdigest(),expected)
        self.assertEqual((m.POLL_SECONDS,m.ROLLING_WINDOW,m.DEFAULTS['gap_seconds']),(1.5,300,15))
    def seed(self,session):
        t=session.exp;t.req=95700;t._req_exact=True;t.exp=10000;t.pct=10000/95700*100
    def test_original_idle_exclusion_can_exceed_wall_clock_projection(self):
        clock=[0.0]
        with patch.object(m.time,'monotonic',side_effect=lambda:clock[0]):
            s=m.Session(15);s.start(0);self.seed(s)
            for i in range(1,21):
                clock[0]=i*3;e=10000+100*i;s.observe([(e,int(e/95700*10000)/100)],True,clock[0])
            s.meso.start=0;s.meso.gained=6000
            clock[0]=90;s.tick(90)
            self.assertEqual(s.exp.elapsed(),60)
            self.assertAlmostEqual(s.exp.rate(),120000)
            self.assertEqual(s.meso.per_hour(s.exp.elapsed()),360000)
            self.assertAlmostEqual(s.exp.gained/90*3600,80000)
            self.assertAlmostEqual(s.meso.gained/90*3600,240000)
    def test_original_exp_excludes_confirmed_death_loss_from_gained(self):
        with patch.object(m.time,'monotonic',return_value=60):
            s=m.Session(15);s.start(60);self.seed(s);s.exp.exp=12000;s.exp.pct=12000/95700*100;s.exp.gained=3000
            e=10000;c=[(e,int(e/95700*10000)/100)]
            s.observe(c,True,60);s.observe(c,True,61)
            self.assertEqual((s.exp.exp,s.exp.gained,s.exp.deaths),(10000,3000,1))
    def test_manual_pause_without_observations_can_credit_unseen_exp(self):
        clock=[0.0]
        with patch.object(m.time,'monotonic',side_effect=lambda:clock[0]):
            s=m.Session(15);s.start(0);self.seed(s)
            clock[0]=60;s.pause();clock[0]=360;s.start(360);clock[0]=363
            e=11000;s.observe([(e,int(e/95700*10000)/100)],True,363)
            self.assertEqual(s.exp.gained,1000)
            self.assertEqual(s.exp.elapsed(),63) # paused 300s are not denominator
    def test_mesos_is_balance_delta_not_a_drop_or_profit_ledger(self):
        t=m.MesoTracker();t.value=1000000;t.start=0;t.counting=True
        for _ in range(2):t.observe(1002000,30,30,True)
        self.assertEqual(t.gained,2000);self.assertAlmostEqual(t.per_hour(30),240000)
        for _ in range(2):t.observe(1001000,60,60,True)
        self.assertEqual(t.gained,1000);self.assertAlmostEqual(t.per_hour(60),60000)

if __name__=='__main__':unittest.main()
