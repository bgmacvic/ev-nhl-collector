import unittest
import feature_engine as f

class FeatureEngineTests(unittest.TestCase):
    def test_frozen_save_quirk_and_expanding_mean(self):
        rows=[
          {'season':'2015','playoffGame':'0','team':'VAN','gameDate':'20151001','situation':'5on5',
           'xGoalsFor':'2','xGoalsAgainst':'1','iceTime':'100','xGoalsPercentage':'.6','corsiPercentage':'.55',
           'fenwickPercentage':'.54','goalsFor':'2','shotsOnGoalFor':'10','savedShotsOnGoalFor':'8','shotsOnGoalAgainst':'20'},
          {'season':'2015','playoffGame':'0','team':'VAN','gameDate':'20151001','situation':'all',
           'goalsFor':'3','shotsOnGoalFor':'12','savedShotsOnGoalFor':'9','shotsOnGoalAgainst':'18'},
        ]
        means,last,counts=f.build_state(rows)
        self.assertAlmostEqual(means[('VAN','home_save_5v5_prior_diff')],8/20)
        self.assertAlmostEqual(means[('VAN','home_all_save_prior_diff')],9/18)
        self.assertEqual(str(last['VAN']),'2015-10-01')

    def test_missing_elo_goalie_blocks_promotion(self):
        rows=[]
        g=[{'id':'1','home':'VAN','away':'CGY','start':'2026-10-05T02:00:00Z'}]
        x=f.live_rows(rows,g)[0]
        self.assertFalse(x['ready_for_v1c'])
        self.assertIn('ELO_STATE_MISSING',x['blockers'])
        self.assertIn('CONFIRMED_STARTER_GOALIE_FEATURE_MISSING',x['blockers'])

if __name__=='__main__': unittest.main()
