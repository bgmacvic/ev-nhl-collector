import unittest,model_engine as m
class ModelTests(unittest.TestCase):
 def test_probability_bounds(self):
  row={k:v for k,v in zip(m.FEATURES,m.MEAN)}
  raw,cal=m.probability(row)
  self.assertGreater(raw,0);self.assertLess(raw,1);self.assertGreater(cal,0);self.assertLess(cal,1)
 def test_ladder_and_plus_money_gate(self):
  row={k:v for k,v in zip(m.FEATURES,m.MEAN)}
  x=m.evaluate(row,110,-120,1)
  self.assertEqual(len(x["candidates"]),2)
  self.assertFalse(x["candidates"][1]["qualifies"])
if __name__=="__main__":unittest.main()
