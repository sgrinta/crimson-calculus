"""Startup recovery must preserve saves without trusting damaged session results."""
from copy import deepcopy
from dataclasses import asdict
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from dash import no_update
from dash.exceptions import PreventUpdate
from engine import Scenario, compare
from practice import new_practice, begin_spin, finish_spin
from freeplay import new_game, edit_bet, begin_game_spin
from session_tracker import record_number,state_token
import app


class StartupRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.scenario=Scenario(bankroll=100,target=20,loss_limit=100,minimum=5,maximum=50,chip=5,spins=8)
        self.fields=asdict(self.scenario)
        self.result=compare(self.scenario)

    def calculate(self,saved,trigger=None,fields=None):
        with patch.object(app,'ctx',SimpleNamespace(triggered_id=trigger)):
            return app.calculate(0,*(fields or self.fields).values(),saved)

    def test_bad_save_does_not_prevent_initial_comparison_or_erase_data(self):
        for saved in ({'version':2},{'version':1},['damaged save']):
            with self.subTest(saved=saved):
                original=deepcopy(saved)
                response=self.calculate(saved)
                self.assertEqual(response[1]['id'],self.result['id'])
                self.assertEqual(response[2],self.fields)
                self.assertIn('could not be resumed',response[3].children)
                self.assertIs(response[5],no_update)
                self.assertEqual(saved,original)

    def test_valid_save_still_resumes_its_original_scenario(self):
        saved=new_practice(self.scenario,'martingale',5)['session']
        saved['history']=record_number(self.scenario,'martingale',5,[],'2')
        draft={**self.fields,'target':25}
        response=self.calculate(saved,fields=draft)
        self.assertEqual(response[2],self.fields)
        self.assertEqual(response[3],'')
        self.assertEqual(len(saved['history']),1)
        # Explicit Apply uses the draft while leaving the old tracker intact.
        applied=self.calculate(saved,trigger='run',fields=draft)
        self.assertEqual(applied[2],draft)
        self.assertTrue(applied[5]['applied_at'])
        self.assertEqual(saved['scenario'],self.fields)

    def test_invalid_fields_still_leave_applied_calculation_untouched(self):
        response=self.calculate({'version':2},fields={**self.fields,'bankroll':None})
        self.assertTrue(all(response[i] is no_update for i in (0,1,2,4,5)))
        self.assertTrue(response[3].children)

    def test_bad_save_renders_a_recovery_message_instead_of_raising(self):
        for saved in ({'version':2},{'version':1},['damaged save']):
            with self.subTest(saved=saved):
                original=deepcopy(saved)
                view,undo_disabled,restart_disabled,notice=app.render_simple_session(saved,self.result)
                self.assertIn('Clear saved session',view.children)
                self.assertTrue(undo_disabled)
                self.assertTrue(restart_disabled)
                self.assertIn('kept',notice)
                self.assertEqual(saved,original)

    def test_tampered_terminal_balance_is_not_rendered_as_a_valid_game(self):
        saved=new_practice(self.scenario,'martingale',5)['session']
        saved['history']=record_number(self.scenario,'martingale',5,[],'2')
        saved['history'][0]['after'][0]=99999
        view,undo_disabled,restart_disabled,_=app.render_simple_session(saved,self.result)
        self.assertIn('could not be resumed',view.children)
        self.assertTrue(undo_disabled and restart_disabled)

    def test_cards_can_replace_malformed_saves_with_a_valid_new_tracker(self):
        for saved in (['damaged save'],{'even_bet':['invalid']},{'even_bet':'invalid'}):
            with self.subTest(saved=saved):
                cards,summary=app.system_choices(self.result,saved,None)
                self.assertTrue(cards.children)
                with patch.object(app,'ctx',SimpleNamespace(triggered_id={'type':'choose-system','key':'martingale','calculation':self.result['id']})):
                    new,_=app.update_simple_session([1],[],0,0,0,self.result,[],[],[],[],saved)
                self.assertEqual(new['even_bet'],'red')
                self.assertEqual(new['history'],[])
                self.assertEqual(new['calculation'],self.result['id'])

    def test_system_cards_identify_the_comparison_their_figures_describe(self):
        cards,_=app.system_choices(self.result,None,None)
        self.assertTrue(cards.children)
        for card in cards.children:
            self.assertEqual(card.id['calculation'],self.result['id'])

    def test_old_system_card_cannot_reset_a_tracker_or_advance_to_step_three(self):
        saved=new_practice(self.scenario,'martingale',5)['session']
        saved['history']=record_number(self.scenario,'martingale',5,[],'2')
        original=deepcopy(saved)
        newer=compare(Scenario(**{**self.fields,'wheel':'french'}))
        trigger={'type':'choose-system','key':'martingale','calculation':self.result['id']}
        with patch.object(app,'ctx',SimpleNamespace(triggered_id=trigger,triggered=[{'value':1}])):
            updated,notice=app.update_simple_session([1],[],0,0,0,newer,[],[],[],[],saved)
            self.assertIs(updated,no_update)
            self.assertIn('refreshed system cards',notice)
            with self.assertRaises(PreventUpdate):app.advance_workflow(None,[1],0,0,newer)
        self.assertEqual(saved,original)

    def test_current_system_card_starts_exactly_its_displayed_comparison(self):
        newer=compare(Scenario(**{**self.fields,'wheel':'french'}))
        row=next(r for r in newer['rows'] if r['key']=='martingale')
        trigger={'type':'choose-system','key':'martingale','calculation':newer['id']}
        with patch.object(app,'ctx',SimpleNamespace(triggered_id=trigger,triggered=[{'value':1}])):
            updated,_=app.update_simple_session([1],[],0,0,0,newer,[],[],[],[],None)
            self.assertEqual(app.advance_workflow(None,[1],0,0,newer),('track','next'))
        self.assertEqual(updated['calculation'],newer['id'])
        self.assertEqual(updated['scenario'],newer['scenario'])
        self.assertEqual(updated['base'],row['base'])

    def test_french_refund_controls_match_browser_store_and_reject_invalid_pockets(self):
        def browser_numbers(value):
            # JSON.stringify emits 95 rather than 95.0 for a whole-valued Number.
            if isinstance(value,float) and value.is_integer():return int(value)
            if isinstance(value,list):return [browser_numbers(item) for item in value]
            if isinstance(value,dict):return {k:browser_numbers(v) for k,v in value.items()}
            return value
        def control_ids(node):
            if isinstance(node,(list,tuple)):
                return [item for child in node for item in control_ids(child)]
            if not hasattr(node,'to_plotly_json'):return []
            props=node.to_plotly_json()['props'];identity=props.get('id')
            return ([identity] if isinstance(identity,dict) and 'token' in identity else [])+control_ids(props.get('children'))
        french=Scenario(**{**self.fields,'wheel':'french'})
        result=compare(french)
        for base in (5,10):
            with self.subTest(base=base):
                saved=new_practice(french,'martingale',base,'black')['session']
                original_token=state_token(saved)
                saved['history']=record_number(french,'martingale',base,[],'0',even_bet='black')
                saved=browser_numbers(saved)
                controls=control_ids(app.render_simple_session(saved,result)[0])
                self.assertTrue(controls)
                self.assertTrue(all(control['token']==state_token(saved) for control in controls))
                button=next(control for control in controls if control['type']=='record-number')
                original=deepcopy(saved)
                with patch.object(app,'ctx',SimpleNamespace(triggered_id=button)):
                    changed,notice=app.update_simple_session([],[],0,0,0,result,[1],[],[],['00'],saved)
                    self.assertIs(changed,no_update)
                    self.assertEqual(notice,'Enter 0–36.')
                    updated,_=app.update_simple_session([],[],0,0,0,result,[2],[],[],['2'],saved)
                self.assertEqual(len(updated['history']),2)
                self.assertEqual(updated['history'][-1]['after'][0],french.bankroll-base/2+2*base)
                self.assertEqual(saved,original)
                with patch.object(app,'ctx',SimpleNamespace(triggered_id={'type':'record-number','token':original_token})):
                    with self.assertRaises(PreventUpdate):app.update_simple_session([],[],0,0,0,result,[1],[],[],['2'],saved)


class CallbackCollector:
    """Exercise real UI callbacks without a server or browser storage."""
    def __init__(self):self.callbacks={}
    def callback(self,*args,**kwargs):
        def capture(fn):
            self.callbacks[fn.__name__]=fn
            return fn
        return capture
    def clientside_callback(self,*args,**kwargs):pass


class VirtualSaveRecoveryTests(unittest.TestCase):
    def setUp(self):
        import practice_ui,freeplay_ui
        self.scenario=Scenario(bankroll=100,target=20,loss_limit=100,minimum=5,maximum=50,chip=5,spins=8)
        self.result=compare(self.scenario)
        practice_callbacks=CallbackCollector();practice_ui.register_practice(practice_callbacks)
        free_callbacks=CallbackCollector();freeplay_ui.register_freeplay(free_callbacks)
        self.practice=practice_callbacks.callbacks
        self.free=free_callbacks.callbacks

    def practice_start(self,saved):
        with patch('practice_ui.ctx',SimpleNamespace(triggered_id='practice-start')):
            return self.practice['update'](1,0,0,0,'red',None,self.result,'martingale',saved)

    def free_start(self,saved):
        with patch('freeplay_ui.ctx',SimpleNamespace(triggered_id='free-start')):
            return self.free['update'](start=1,reset=0,undo=0,clear=0,spin=0,add=0,table_clicks=[],remove_clicks=[],done=None,
                config=asdict(self.scenario),use_system=0,load=0,key='red',amount=5,data=saved,system='none',even='red',result=self.result)

    def test_practice_render_replays_saved_results_before_displaying_stats(self):
        valid=new_practice(self.scenario,'martingale',5)
        pending=begin_spin(valid,choose=lambda _: '2')
        valid=finish_spin(pending,pending['pending']['id'])
        forged=deepcopy(valid);forged['session']['history'][0]['after'][0]=99999
        for saved in (['broken'],{'version':1},forged):
            with self.subTest(saved=saved):
                original=deepcopy(saved)
                rendered=self.practice['render'](saved,self.result)
                self.assertEqual(rendered[2],'Practice unavailable')
                self.assertEqual(rendered[0],[])
                self.assertTrue(rendered[6])  # no spin from an unreadable save
                self.assertFalse(rendered[7])  # explicit new-session recovery works
                self.assertEqual(saved,original)

    def test_practice_selector_and_new_session_recover_bad_save_shapes(self):
        invalid_pending=dict(new_practice(self.scenario,'martingale',5),pending={'id':'bad'})
        for saved in (['broken'],{'session':None},invalid_pending):
            with self.subTest(saved=saved):
                options,key,_=self.practice['configure'](self.result,None,saved)
                self.assertIn(key,[o['value'] for o in options])
                original=deepcopy(saved)
                fresh,notice,even=self.practice_start(saved)
                self.assertEqual(fresh['session']['history'],[])
                self.assertIsNone(fresh['pending'])
                self.assertEqual(saved,original)

    def test_start_new_practice_keeps_a_valid_pending_draw_locked(self):
        pending=begin_spin(new_practice(self.scenario,'martingale',5),choose=lambda _: '2')
        response=self.practice_start(pending)
        self.assertIs(response[0],no_update)
        self.assertIn('Wait',response[1])

    def test_free_play_recovery_controls_handle_corrupt_save_shapes(self):
        for saved in (['broken'],{'scenario':[]},{'advisor':{'key':'invalid'},'pending':{'id':'bad'}}):
            with self.subTest(saved=saved):
                original=deepcopy(saved)
                options,key,even=self.free['system_choices'](self.result,saved,['broken'],['broken'],None)
                self.assertIn(key,[o['value'] for o in options])
                self.assertEqual(even,'red')
                self.free['choices']('straight',saved,None)
                self.free['position_help']('red',saved)
                self.assertTrue(self.free['guide_and_odds'](saved)[1])
                rendered=self.free['render'](saved,asdict(self.scenario))
                self.assertEqual(rendered[4],'Save unavailable')
                self.assertTrue(rendered[9])
                self.assertFalse(rendered[10])
                fresh,_,_=self.free_start(saved)
                self.assertEqual(fresh['history'],[])
                self.assertEqual(saved,original)

    def test_start_new_free_play_replaces_invalid_pending_but_locks_valid_draw(self):
        game=edit_bet(new_game(self.scenario),'red',5)
        invalid=dict(game,pending={'id':'bad'})
        fresh,_,_=self.free_start(invalid)
        self.assertIsNone(fresh['pending'])
        pending=begin_game_spin(game,choose=lambda _: '2')
        response=self.free_start(pending)
        self.assertIs(response[0],no_update)
        self.assertIn('Wait',response[1])


if __name__=='__main__':unittest.main()
