"""Behavioral integration tests: PQ, private share cards and bounded local diagnostics."""
from ast_contract import legacy_dump
import ast
import faulthandler
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ['MAPLE_EXP_DATA'] = tempfile.mkdtemp(prefix='maple-integration-')
import maple_exp as m
from diagnostics import Diagnostics
from share_card import CardStats, make_card


class PQTests(unittest.TestCase):
    def session(self):
        s=m.Session(15);s.start(0);s.exp.req=95700;s.exp._req_exact=True
        s.exp.exp=10000;s.exp.pct=10000/95700*100;s.map_seen('Stage 1')
        return s
    def gain(self,s,exp,now):
        s.observe([(exp,int(exp/95700*10000)/100)],True,now)
    def test_stage_clear_after_two_minutes_and_map_change(self):
        clock=[0]
        with patch.object(m.time,'monotonic',side_effect=lambda:clock[0]):
            s=self.session();s.set_pq(True);clock[0]=30;self.gain(s,11000,30)
            s.map_seen('Stage 2');self.assertTrue(s.exp.running);self.assertIsNone(s.waiting)
            clock[0]=150;s.tick(150);self.assertTrue(s.exp.running)
            self.gain(s,16000,150);self.assertEqual(s.exp.gained,6000)
            clock[0]=751;s.tick(751);self.assertEqual(s.waiting,'idle')
    def test_default_mode_retains_fifteen_second_idle_policy(self):
        with patch.object(m.time,'monotonic',return_value=0):s=self.session()
        self.assertFalse(s.pq);self.assertEqual(s.idle_gap,15)
        with patch.object(m.time,'monotonic',return_value=16):s.tick(16)
        self.assertEqual(s.waiting,'idle')
    def test_pq_off_restores_map_pause(self):
        with patch.object(m.time,'monotonic',return_value=0):
            s=self.session();s.set_pq(True);s.map_seen('Stage 2');s.set_pq(False)
            self.assertEqual(s.map,'Stage 2');s.map_seen('Town');self.assertEqual(s.waiting,'map')
    def test_log_keeps_stage_gains_on_one_pq_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);log=m.AutoLog(15,p/'history.json',p/'history.txt');log.gain(0,100);entry=None
            for t in range(1,301):
                if t%120==0:log.gain(t,3000)
                entry=log.tick(t,m.PQ_MAP,30,4,None,'Bandit',m.PQ_MAP,gap=m.PQ_GAP)
            self.assertIsNotNone(entry);self.assertEqual(entry['map'],m.PQ_MAP);self.assertEqual(entry['exp'],6000)
    def test_original_tracker_and_eta_contracts_are_preserved(self):
        t=ast.parse((ROOT/'maple_exp.py').read_text());expected=json.loads((ROOT/'tests/frames/original-rate-contract.json').read_text())
        for name in ['ExpTracker','MesoTracker']:
            node=next(n for n in t.body if isinstance(n,ast.ClassDef) and n.name==name)
            self.assertEqual(hashlib.sha256(legacy_dump(node).encode()).hexdigest(),expected['class_AST_sha256'][name])


class ShareTests(unittest.TestCase):
    def test_card_contains_only_selected_session_fields(self):
        t=m.ExpTracker();t._accum=60;t.gained=2000;t.req=95700
        app=SimpleNamespace(tracker=t,meso=m.MesoTracker(),pq_mode=True,map_name='Stage 2',level=30,job='Bandit',party=4,_trend=[10000,12000],secret='wallet secret',autolog=SimpleNamespace(entries=[{'note':'PRIVATE NOTE'}]))
        stats=m.App._card_stats(app)
        self.assertEqual(stats.map_name,m.PQ_MAP);self.assertEqual(stats.exp_hr,'120,000')
        self.assertNotIn('PRIVATE',repr(stats));self.assertNotIn('wallet',repr(stats));self.assertNotIn('github.com',stats.footer)
        img=make_card(stats,m.ASSETS/'fonts');self.assertEqual(img.size,(1280,688))
    def test_no_rate_yet_does_not_save_card_or_touch_clipboard(self):
        app=SimpleNamespace(_card_stats=lambda:None,root=None,_show_card=Mock(),_copy_card=Mock())
        with patch.object(m.messagebox,'showinfo'):m.App.share_card(app)
        app._copy_card.assert_not_called();app._show_card.assert_not_called()
    def test_share_action_saves_generated_card_not_capture(self):
        with tempfile.TemporaryDirectory() as tmp:
            app=SimpleNamespace(_card_stats=lambda:CardStats('1,000'),_show_card=Mock(),_copy_card=Mock(return_value=True),status=Mock(),root=None)
            with patch.object(m,'DATA_DIR',Path(tmp)):m.App.share_card(app)
            app._copy_card.assert_called_once_with(Path(tmp)/'share-card.png')
            self.assertEqual([f.name for f in Path(tmp).iterdir()],['share-card.png'])


class DiagnosticTests(unittest.TestCase):
    def test_export_allowlist_and_redaction(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);d=Diagnostics(p,'test');d.activity('Ready')
            (p/'crash.log').write_text('Frame C:\\Users\\SomePrivateName\\app.py /Users/SomeoneElse/app.py')
            for n in ['exp_log.json','config.json','share-card.png','secrets.txt']:(p/n).write_text('DO NOT SHARE')
            z=d.export({'version':'test','private':'DO NOT SHARE'})
            with zipfile.ZipFile(z) as a:
                text=''.join(a.read(n).decode() for n in a.namelist())
                self.assertEqual(set(a.namelist()),{'overlay.log','crash.log','diagnostic-details.txt'})
                for secret in ['DO NOT SHARE','SomePrivateName','SomeoneElse']:self.assertNotIn(secret,text)
    def test_error_does_not_record_exception_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Diagnostics(tmp,'test');d.error('OCR',ValueError('SEED PHRASE PRIVATE'))
            text=(Path(tmp)/'overlay.log').read_text();self.assertIn('ValueError',text);self.assertNotIn('SEED',text)
    def test_export_rejects_symlink_to_outside_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'data').mkdir();(p/'secret').write_text('PRIVATE')
            (p/'data/crash.log').symlink_to(p/'secret');d=Diagnostics(p/'data','test')
            with self.assertRaises(ValueError):d.export({})
    def test_export_reads_bounded_tail(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Diagnostics(tmp,'test');(Path(tmp)/'errors.log').write_text('x'*(d.LIMIT*2))
            with zipfile.ZipFile(d.export({})) as z:self.assertEqual(len(z.read('errors.log')),d.LIMIT)
    def test_crash_marker_and_hooks_restore_on_clean_close(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Diagnostics(tmp,'test');old=(sys.excepthook,__import__('threading').excepthook)
            try:
                self.assertFalse(d.start());self.assertTrue(faulthandler.is_enabled());self.assertTrue((Path(tmp)/'running.flag').exists())
            finally:d.end()
            self.assertFalse((Path(tmp)/'running.flag').exists());self.assertEqual(old,(sys.excepthook,__import__('threading').excepthook))
            (Path(tmp)/'running.flag').write_text('unclean')
            try:self.assertTrue(d.start())
            finally:d.end()
    def test_unwritable_diagnostic_location_does_not_block_startup(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'not-a-directory';path.write_text('keep')
            d=Diagnostics(path,'test')
            try:self.assertFalse(d.start())
            finally:d.end()
            self.assertEqual(path.read_text(),'keep')
    def test_recent_only_logs_new_status_once(self):
        sink=Mock();recent=m.Recent(sink=sink);recent.add('Ready');recent.add('Ready');self.assertEqual(sink.call_count,1)

if __name__=='__main__':unittest.main()
