import unittest
import espn_starters as e

class StarterTests(unittest.TestCase):
 def test_explicit_probable_starter(self):
  c={"probableStarter":{"athlete":{"id":"123","displayName":"Goalie"},"status":"probable"}}
  x=e._goalie(c);self.assertEqual(x["goalie_id"],123);self.assertEqual(x["status"],"probable")
 def test_missing_starter_fails_closed(self):
  self.assertIsNone(e._goalie({"athlete":{"id":"123"}}))
 def test_match_requires_team_pair(self):
  x=e.match_to_nhl([{"home_abbrev":"VAN","away_abbrev":"CGY","home_goalie_id":1,"away_goalie_id":2}],
                   [{"id":"99","home":"VAN","away":"CGY"}])
  self.assertEqual(x["games"][0]["game_id"],"99")
if __name__=="__main__":unittest.main()
