from copy import deepcopy
from dataclasses import replace
import csv
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine import Scenario,POSITIONS
from freeplay import *
from practice import pockets

class FreePlayTests(unittest.TestCase):
    def spin(self,data,number):
        pending=begin_game_spin(data,choose=lambda legal:number)
        return finish_game_spin(pending,pending['pending']['id'])

    def test_all_positions_payout_on_every_pocket(self):
        # Independent payout oracle for all standard bets, all wheel pockets.
        for wheel in ('single','french','double','triple'):
            s=replace(Scenario(),wheel=wheel)
            for key,position in positions(wheel).items():
                self.assertTrue(set(position['numbers'])<=set(pockets(wheel)))
                for number in pockets(wheel):
                    expected=10*(position['gross']-1) if number in position['numbers'] else -5 if wheel=='french' and number=='0' and key in EVEN_CHOICES else -10
                    self.assertEqual(net_result(s,[dict(position=key,amount=10)],number),expected,(wheel,key,number))

    def test_standard_positions_match_existing_engine(self):
        for wheel in ('single','french'):
            for key,p in POSITIONS.items():
                self.assertEqual(positions(wheel)[key]['numbers'],[str(n) for n in p['numbers']])
                self.assertEqual(positions(wheel)[key]['gross'],p['multiplier'])

    def test_unequal_overlapping_bets_all_pay_and_stakes_return(self):
        d=new_game(Scenario());d=edit_bet(d,'red',10);d=edit_bet(d,'straight:1',5);d=edit_bet(d,'street:0',15)
        original=deepcopy(d);d=self.spin(d,'1')
        self.assertEqual(d['history'][-1]['net'],350) # returns 20+180+180 minus30
        self.assertEqual(d['history'][-1]['bankroll'],1350)
        self.assertEqual(original['history'],[])
        self.assertEqual(sum(e['amount'] for e in d['bets']),30)

    def test_distinct_zeros_and_special_payouts(self):
        for wheel,number in [('double','00'),('triple','000')]:
            d=edit_bet(new_game(replace(Scenario(),wheel=wheel)),'straight:'+number,5)
            d=self.spin(d,number)
            self.assertEqual(d['history'][-1]['net'],175)
            self.assertEqual(d['history'][-1]['number'],number)
        s=replace(Scenario(),wheel='double')
        self.assertEqual(net_result(s,[dict(position='basket',amount=10)],'00'),60)
        self.assertEqual(net_result(s,[dict(position='basket',amount=10)],'4'),-10)
        s=replace(s,wheel='triple')
        self.assertEqual(net_result(s,[dict(position='topline',amount=10)],'000'),50)

    def test_french_all_even_positions_half_refund_with_overlap(self):
        s=replace(Scenario(),wheel='french')
        d=new_game(s)
        for key in EVEN_CHOICES:d=edit_bet(d,key,5)
        d=edit_bet(d,'straight:0',5);d=self.spin(d,'0')
        self.assertEqual(d['history'][-1]['net'],160) # +175 on0 -15 even half losses
        self.assertEqual(d['history'][-1]['bankroll'],1160)

    def test_uniform_draw_once_pending_freeze_replay_and_stale(self):
        d=edit_bet(new_game(Scenario()),'black',5)
        with patch('freeplay.secrets.choice',return_value='2') as choose:
            p=begin_game_spin(d);choose.assert_called_once_with(pockets('single'))
            p=validate_game(json.loads(json.dumps(p)))
            for mutate in [lambda:edit_bet(p,'red',5),lambda:undo_game(p),lambda:begin_game_spin(p)]:
                with self.assertRaises(ValueError):mutate()
            with self.assertRaises(ValueError):finish_game_spin(p,'wrong')
            bad=deepcopy(p);bad['bets'][0]['amount']=10
            with self.assertRaises(ValueError):validate_game(bad)
            done=finish_game_spin(p,p['pending']['id']);choose.assert_called_once()
        with self.assertRaises(ValueError):finish_game_spin(done,p['pending']['id'])
        self.assertEqual(done['history'][0]['net'],5)

    def test_replay_ignores_forged_balances_and_undo_restores_slip(self):
        d=edit_bet(new_game(Scenario()),'red',10);d=self.spin(d,'2')
        d=edit_bet(d,'black',20);d=self.spin(d,'2')
        d=edit_bet(d,clear=True)
        d['history'][0]['bankroll']=999999
        resumed=validate_game(json.loads(json.dumps(d)))
        self.assertEqual(status(resumed)['bankroll'],1000)
        undone=undo_game(resumed)
        self.assertEqual(status(undone)['bankroll'],990)
        self.assertEqual(undone['bets'],[dict(position='red',amount=10),dict(position='black',amount=20)])

    def test_limits_minimum_chip_and_reduce_after_loss(self):
        s=replace(Scenario(),bankroll=100,loss_limit=50,maximum=50)
        d=new_game(s)
        for key,amount in [('red',1),('red',7),('straight:00',5),('red',55),('red',float('nan')),('red',True)]:
            with self.assertRaises(ValueError):edit_bet(d,key,amount)
        d=edit_bet(d,'red',30);d=self.spin(d,'2')
        self.assertIn('Reduce',status(d)['problem'])
        with self.assertRaises(ValueError):begin_game_spin(d)
        d=edit_bet(d,clear=True);d=edit_bet(d,'red',20);d=self.spin(d,'2')
        self.assertEqual(status(d)['bankroll'],50)
        self.assertIsNotNone(status(d)['stop'])
        with self.assertRaises(ValueError):begin_game_spin(d)

    def test_target_spin_and_empty_slip_stopping(self):
        for s,number in [(replace(Scenario(),target=5),'1'),(replace(Scenario(),spins=1),'2')]:
            d=edit_bet(new_game(s),'red',5);d=self.spin(d,number)
            with self.assertRaises(ValueError):begin_game_spin(d)
            self.assertIsNone(status(undo_game(d))['stop'])
        with self.assertRaises(ValueError):begin_game_spin(new_game(Scenario()))

    def test_csv_and_current_spin_stats(self):
        d=edit_bet(new_game(replace(Scenario(),wheel='double')),'straight:00',10)
        current=status(d)
        self.assertAlmostEqual(current['profit_chance'],1/38)
        self.assertAlmostEqual(current['mean'],-20/38)
        d=self.spin(d,'00');row=list(csv.DictReader(io.StringIO(game_csv(d))))[0]
        self.assertEqual(row['session_mode'],'Free play / virtual money')
        self.assertEqual(row['winning_pocket'],'Pocket 00')
        self.assertEqual(row['bankroll'],'1350.00')
        self.assertEqual(row['net'],'350.00')

if __name__=='__main__':unittest.main()
