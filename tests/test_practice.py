"""Practice is virtual, independently saved, and settled by the real payout engine."""
from copy import deepcopy
from dataclasses import replace
import csv
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine import Scenario,POSITIONS
from practice import (new_practice,begin_spin,finish_spin,undo_practice,validate_practice,
                      practice_csv,pockets,pocket_color,wheel_svg)
from session_tracker import snapshot, state_token, validate_saved_session


class PracticeTests(unittest.TestCase):
    def spin(self,data,number):
        pending=begin_spin(data,choose=lambda legal:number)
        return finish_spin(pending,pending['pending']['id'])

    def test_wheels_and_art_include_each_legal_pocket_exactly_once(self):
        for wheel,count in [('single',37),('french',37),('double',38),('triple',39)]:
            with self.subTest(wheel=wheel):
                legal=pockets(wheel)
                self.assertEqual(len(legal),count)
                self.assertEqual(len(set(legal)),count)
                self.assertEqual(set(legal),{str(n) for n in range(37)}|({'00'} if count>=38 else set())|({'000'} if count==39 else set()))
                root=ET.fromstring(wheel_svg(wheel))
                labels=[e.text for e in root.findall('{http://www.w3.org/2000/svg}text')]
                self.assertEqual(labels,legal)
                self.assertEqual(sum(pocket_color(n)=='red' for n in legal),18)
                self.assertEqual(sum(pocket_color(n)=='black' for n in legal),18)

    def test_uniform_sampler_receives_all_pockets_and_draws_once(self):
        d=new_practice(replace(Scenario(),wheel='triple'),'martingale',5)
        with patch('practice.secrets.choice',return_value='000') as choose:
            p=begin_spin(d)
            choose.assert_called_once_with(pockets('triple'))
            self.assertEqual(p['session']['history'],[])
            resumed=validate_practice(json.loads(json.dumps(p)))
            done=finish_spin(resumed,p['pending']['id'])
            choose.assert_called_once()
        self.assertEqual(done['session']['history'][-1]['winning_number'],'000')
        self.assertEqual(done['session']['history'][-1]['net'],-5)

    def test_every_wheel_pocket_uses_the_selected_bet(self):
        for wheel in ('single','french','double','triple'):
            d=new_practice(replace(Scenario(),wheel=wheel),'martingale',10,'black')
            for number in pockets(wheel):
                with self.subTest(wheel=wheel,number=number):
                    done=self.spin(d,number)
                    expected=10 if number not in ('00','000') and int(number) in POSITIONS['black']['numbers'] else -5 if wheel=='french' and number=='0' else -10
                    self.assertEqual(done['session']['history'][-1]['net'],expected)

    def test_overlap_settlement_and_limit_stopping_match_tracker(self):
        d=new_practice(Scenario(),'research',None)
        d=self.spin(d,'36')
        self.assertEqual(d['session']['history'][-1]['net'],-25)
        d=self.spin(d,'0')
        self.assertEqual(d['session']['history'][-1]['net'],225)
        self.assertEqual(d['session']['history'][-1]['after'],[1200,278])
        with self.assertRaisesRegex(ValueError,'target'):begin_spin(d)

    def test_stale_double_or_overlapping_spins_are_rejected(self):
        d=new_practice(Scenario(),'martingale',5)
        p=begin_spin(d,choose=lambda legal:'1')
        with self.assertRaisesRegex(ValueError,'current spin'):begin_spin(p)
        with self.assertRaisesRegex(ValueError,'stale'):finish_spin(p,'wrong')
        with self.assertRaisesRegex(ValueError,'current spin'):undo_practice(p)
        done=finish_spin(p,p['pending']['id'])
        with self.assertRaisesRegex(ValueError,'already settled'):finish_spin(done,p['pending']['id'])
        altered=deepcopy(p);altered['session']['even_bet']='black'
        with self.assertRaisesRegex(ValueError,'does not match'):finish_spin(altered,p['pending']['id'])

    def test_practice_does_not_mutate_the_tracked_session(self):
        d=new_practice(Scenario(),'martingale',5)
        tracked=deepcopy(d['session']);original=deepcopy(d)
        done=self.spin(d,'2')
        self.assertEqual(d,original)
        self.assertEqual(tracked,original['session'])
        self.assertEqual(tracked['history'],[])
        self.assertEqual(done['session']['history'][-1]['after'],[995,279])

    def test_undo_restores_bankroll_progression_number_and_even_choice(self):
        d=new_practice(replace(Scenario(),wheel='french'),'martingale',10,'high')
        d=self.spin(d,'0')
        current=snapshot(Scenario(**d['session']['scenario']),'martingale',10,d['session']['history'],even_bet='high')
        self.assertEqual((current['bankroll'],current['spins_left'],current['total']),(995,279,20))
        d['session']['even_bet']='odd'
        restored=undo_practice(d)
        self.assertEqual(restored['session']['history'],[])
        self.assertEqual(restored['session']['even_bet'],'high')
        self.assertIsNone(restored['last_id'])

    def test_one_shot_spin_and_loss_limits_stop_practice(self):
        for s,key,base in [(Scenario(),'oneshot',200),(replace(Scenario(),spins=1),'flat',5)]:
            d=self.spin(new_practice(s,key,base),'2')
            with self.assertRaises(ValueError):begin_spin(d)
        d=new_practice(Scenario(),'martingale',200)
        d=self.spin(self.spin(d,'2'),'2')
        self.assertEqual(d['session']['history'][-1]['after'][0],400)
        with self.assertRaisesRegex(ValueError,'required wager'):begin_spin(d)

    def test_export_is_explicitly_simulated_with_distinct_zero_labels(self):
        d=self.spin(new_practice(replace(Scenario(),wheel='double'),'martingale',10),'00')
        rows=list(csv.DictReader(io.StringIO(practice_csv(d))))
        self.assertEqual(rows[0]['session_mode'],'Practice / virtual money')
        self.assertEqual(rows[0]['outcome_source'],'Simulated uniform random pocket')
        self.assertEqual(rows[0]['winning_pocket'],'Pocket 00')
        self.assertEqual(rows[0]['bankroll_after'],'990.00')

    def test_invalid_pockets_and_saves_are_rejected(self):
        d=new_practice(Scenario(),'martingale',5)
        with self.assertRaises(ValueError):begin_spin(d,choose=lambda legal:'000')
        with self.assertRaises(ValueError):validate_practice(dict(version=99))
        with self.assertRaises(ValueError):new_practice(Scenario(),'martingale',1)

    def test_practice_requires_the_actual_pocket_even_when_cash_replay_is_valid(self):
        d=self.spin(new_practice(Scenario(),'flat',5),'2')
        del d['session']['history'][0]['winning_number']
        # Manual result buttons are valid for tracked play, but not a simulated
        # practice history whose wheel and log must show the sampled number.
        self.assertEqual(validate_saved_session(d['session'])['history'][0]['net'],-5)
        with self.assertRaisesRegex(ValueError,'winning pocket'):validate_practice(d)

    def test_completed_practice_save_cannot_resume_a_pending_spin(self):
        scenarios=[(replace(Scenario(),target=5),'flat',5,['1']),
                   (replace(Scenario(),spins=1),'flat',5,['2']),
                   (Scenario(),'martingale',200,['2','2'])]
        for s,key,base,numbers in scenarios:
            with self.subTest(key=key,spins=s.spins,target=s.target):
                d=new_practice(s,key,base)
                for number in numbers:d=self.spin(d,number)
                d['pending']=dict(id='stale-pending',number='2',token=state_token(d['session']))
                with self.assertRaisesRegex(ValueError,'completed practice'):validate_practice(d)

    def test_empty_pending_identifier_is_rejected_without_breaking_valid_resume(self):
        d=begin_spin(new_practice(Scenario(),'flat',5),choose=lambda legal:'2')
        restored=validate_practice(json.loads(json.dumps(d)))
        done=finish_spin(restored,restored['pending']['id'])
        self.assertEqual(done['session']['history'][0]['winning_number'],'2')
        self.assertEqual(undo_practice(done)['session']['history'],[])
        d['pending']['id']=''
        with self.assertRaisesRegex(ValueError,'pending practice'):validate_practice(d)

if __name__=='__main__':unittest.main()
