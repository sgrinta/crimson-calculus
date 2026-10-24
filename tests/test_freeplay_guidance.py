from dataclasses import replace
from copy import deepcopy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine import Scenario,POSITIONS,inspect_policy
from freeplay import new_game,edit_bet,begin_game_spin,finish_game_spin,undo_game,validate_game,status,positions
from freeplay_advisor import choose_advisor,suggested_bets,load_suggestion
from table_targets import inside_targets

class GuidanceTests(unittest.TestCase):
    def spin(self,data,number):
        pending=begin_game_spin(data,choose=lambda legal:number)
        return finish_game_spin(pending,pending['pending']['id'])

    def test_inside_target_coordinates_match_the_physical_grid(self):
        targets=inside_targets();keys=[t['key'] for t in targets]
        self.assertEqual(len(targets),79) # 57 split lines + 22 corner intersections
        self.assertEqual(len(keys),len(set(keys)))
        self.assertEqual(set(keys),{k for k in POSITIONS if k.startswith(('split:h:','split:v:','corner:'))})
        for target in targets:
            # Cell centers from the horizontal layout, derived from its actual numbers.
            centers=[(((n-1)//3+.5)/12*100,(2-(n-1)%3+.5)/3*100) for n in POSITIONS[target['key']]['numbers']]
            self.assertAlmostEqual(target['x'],sum(x for x,y in centers)/len(centers))
            self.assertAlmostEqual(target['y'],sum(y for x,y in centers)/len(centers))
        from freeplay_ui import betting_table
        board=betting_table(Scenario(),[],False)
        def buttons(node):
            if isinstance(node,list):return sum((buttons(n) for n in node),[])
            if not hasattr(node,'to_plotly_json'):return []
            info=node.to_plotly_json();props=info['props']
            own=[props['id']['position']] if isinstance(props.get('id'),dict) and props['id'].get('type')=='free-table-bet' else []
            return own+buttons(props.get('children',[]))
        ids=buttons(board)
        self.assertEqual(len(ids),len(set(ids)))
        self.assertTrue({f'street:{i}' for i in range(12)}<=set(ids))
        self.assertTrue(set(keys)<=set(ids))

    def test_actual_combined_profit_loss_and_break_even_odds(self):
        s=replace(Scenario(),wheel='double')
        d=edit_bet(edit_bet(new_game(s),'red',5),'black',5)
        current=status(d)
        self.assertEqual(current['profit_chance'],0)
        self.assertAlmostEqual(current['loss_chance'],2/38)
        self.assertAlmostEqual(current['break_even_chance'],36/38)
        # A return on red still loses overall when the larger straight wager misses.
        d=edit_bet(edit_bet(new_game(s),'red',5),'straight:17',10)
        self.assertAlmostEqual(status(d)['profit_chance'],1/38)
        self.assertAlmostEqual(sum(status(d)[k] for k in ('profit_chance','loss_chance','break_even_chance')),1)

    def test_martingale_follows_only_actual_matching_wagers(self):
        d=choose_advisor(new_game(Scenario()),'martingale',5,'black')
        self.assertEqual(suggested_bets(d)['entries'],[dict(position='black',amount=5)])
        d=load_suggestion(d);d=self.spin(d,'1')
        self.assertEqual(suggested_bets(d)['entries'][0]['amount'],10)
        d=load_suggestion(d);d=self.spin(d,'1')
        self.assertEqual(suggested_bets(d)['entries'][0]['amount'],20)
        # Manual inside wager resets the progression instead of inventing a system result.
        d=edit_bet(d,clear=True);d=edit_bet(d,'straight:2',5);d=self.spin(d,'3')
        self.assertEqual(suggested_bets(d)['entries'][0]['amount'],5)
        self.assertIn('restarted',suggested_bets(d)['note'])
        d=undo_game(d)
        self.assertEqual(suggested_bets(d)['entries'][0]['amount'],20)

    def test_french_half_loss_and_even_selection_keep_the_progression(self):
        d=choose_advisor(new_game(replace(Scenario(),wheel='french')),'grand_martingale',10,'low')
        d=self.spin(load_suggestion(d),'0')
        self.assertEqual(status(d)['bankroll'],995)
        self.assertEqual(suggested_bets(d)['entries'],[dict(position='low',amount=30)])
        d=choose_advisor(d,'grand_martingale',10,'odd')
        self.assertEqual(suggested_bets(d)['entries'],[dict(position='odd',amount=30)])
        d=self.spin(load_suggestion(d),'1')
        self.assertEqual(suggested_bets(d)['entries'][0]['amount'],10)

    def test_change_system_starts_now_and_undo_keeps_valid_start(self):
        d=edit_bet(new_game(Scenario()),'red',5);d=self.spin(d,'2')
        d=choose_advisor(d,'martingale',10)
        self.assertEqual(d['advisor']['start'],1)
        self.assertEqual(suggested_bets(d)['entries'][0]['amount'],10)
        d=undo_game(d)
        self.assertEqual(validate_game(d)['advisor']['start'],0)
        self.assertEqual(suggested_bets(d)['entries'][0]['amount'],10)
        self.assertIsNone(choose_advisor(d,None)['advisor'])

    def test_adaptive_guidance_uses_actual_cash_after_manual_bets(self):
        s=replace(Scenario(),bankroll=100,target=20,loss_limit=100,maximum=100,spins=5,wheel='double')
        d=choose_advisor(new_game(s),'sixline')
        d=edit_bet(d,'red',5);d=self.spin(d,'2')
        expected=inspect_policy(s,'sixline',95,4)
        suggestion=suggested_bets(d);available=positions(s.wheel)
        self.assertEqual(sum(e['amount'] for e in suggestion['entries']),expected['total'])
        self.assertEqual({n for e in suggestion['entries'] for n in available[e['position']]['numbers']},{str(n) for e in expected['entries'] for n in e['numbers']})
        self.assertEqual(load_suggestion(d)['bets'],suggestion['entries'])

    def test_load_replaces_slip_and_stops_at_required_limits(self):
        d=choose_advisor(new_game(Scenario()),'martingale',200)
        d=edit_bet(d,'straight:17',5);old=deepcopy(d)
        loaded=load_suggestion(d)
        self.assertEqual(d,old)
        self.assertEqual(loaded['bets'],[dict(position='red',amount=200)])
        d=self.spin(loaded,'2');d=self.spin(load_suggestion(d),'2')
        self.assertIsNotNone(suggested_bets(d)['stop'])
        with self.assertRaises(ValueError):load_suggestion(d)
        # Free play itself can still accept a smaller manual wager.
        d=edit_bet(d,clear=True);d=edit_bet(d,'red',5)
        self.assertIsNone(status(d)['problem'])

    def test_suggestions_cannot_change_a_pending_wager_and_legacy_saves_resume(self):
        d=choose_advisor(new_game(Scenario()),'flat',5)
        pending=begin_game_spin(load_suggestion(d),choose=lambda legal:'2')
        for action in (lambda:choose_advisor(pending,'martingale',5),lambda:load_suggestion(pending)):
            with self.assertRaises(ValueError):action()
        legacy=new_game(Scenario())
        self.assertIsNone(validate_game(legacy)['advisor'])
        d=choose_advisor(new_game(Scenario()),'oneshot',5)
        d=self.spin(load_suggestion(d),'2')
        self.assertIn('One-shot',suggested_bets(d)['stop'])
        with self.assertRaises(ValueError):choose_advisor(d,'martingale',1)

if __name__=='__main__':unittest.main()
