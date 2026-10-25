"""Release security contracts: patched runtime and narrow share image decoding."""
import ast
from pathlib import Path
import sys
import unittest
import PIL
ROOT=Path(__file__).resolve().parents[1]
class RuntimeSecurityTests(unittest.TestCase):
 def test_patched_runtime_and_imaging(self):
  self.assertGreaterEqual(sys.version_info[:2],(3,11))
  self.assertGreaterEqual(tuple(map(int,PIL.__version__.split('.'))),(13,0,0))
 def test_share_image_open_is_png_only(self):
  calls=[]
  for name in ['maple_exp.py','platforms/windows.py']:
   for node in ast.walk(ast.parse((ROOT/name).read_text())):
    if isinstance(node,ast.Call) and ast.unparse(node.func)=='Image.open':
     formats=next((kw.value for kw in node.keywords if kw.arg=='formats'),None)
     self.assertIsNotNone(formats,name)
     self.assertEqual(ast.literal_eval(formats),['PNG']);calls.append(name)
  self.assertEqual(len(calls),2)
 def test_original_contract_hashes_unchanged_by_schema_adapter(self):
  from ast_contract import legacy_dump
  import hashlib,json
  tree=ast.parse((ROOT/'maple_exp.py').read_text())
  expected=json.loads((ROOT/'tests/frames/original-rate-contract.json').read_text())
  for name in ['ExpTracker','MesoTracker']:
   n=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==name)
   self.assertEqual(hashlib.sha256(legacy_dump(n).encode()).hexdigest(),expected['class_AST_sha256'][name])
if __name__=='__main__':unittest.main()
