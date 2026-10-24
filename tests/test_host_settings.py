"""Chat settings edits are scoped, validated, non-destructive and race checked."""
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dash import no_update
from dash.exceptions import PreventUpdate
from engine import Scenario
from agent import generate, tool_dispatch
from host_settings import prepare_settings_update, commit_settings_update, FIELDS


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.s=Scenario(bankroll=100,target=20,loss_limit=100,minimum=5,maximum=50,chip=5,spins=8)
        self.values=asdict(self.s)

    def test_sparse_edit_preserves_current_drafts_without_writing_them(self):
        draft={**self.values,'target':30}
        context=dict(values=draft)
        result=tool_dispatch('update_session_settings',{'bankroll':200,'wheel':'french'},self.s,None,context)
        self.assertEqual(result['status'],'ready_for_ui')
        self.assertEqual(context['proposal']['after']['target'],30)
        self.assertEqual(context['proposal']['after']['bankroll'],200)
        self.assertEqual(draft,{**self.values,'target':30})
        updated,receipt=commit_settings_update(context['proposal'],draft)
        self.assertEqual(receipt['status'],'updated')
        self.assertEqual(updated,context['proposal']['after'])

    def test_all_eight_fields_and_requested_8000_example(self):
        context=dict(values=asdict(Scenario()))
        prepare_settings_update(context,dict(bankroll=8000,target=500,loss_limit=7000,
            minimum=10,maximum=8000,chip=10,spins=200,wheel='triple'))
        updated,receipt=commit_settings_update(context['proposal'],context['values'])
        self.assertEqual(set(updated),set(FIELDS))
        self.assertEqual(updated['maximum'],8000)
        self.assertEqual(len(receipt['changes']),8)

    def test_invalid_settings_do_not_create_actions_or_fix_other_fields(self):
        for changes in ({'bankroll':50},{'spins':501},{'maximum':4},{'target':21},
                        {'chip':True},{'wheel':'unknown'},{'target':'30'},
                        {'target':float('nan')},{'api_key':'x'},{}):
            context=dict(values=deepcopy(self.values))
            with self.subTest(changes=changes),self.assertRaises((ValueError,TypeError)):
                prepare_settings_update(context,changes)
            self.assertNotIn('proposal',context)
            self.assertEqual(context['values'],self.values)

    def test_no_settings_tool_outside_app_and_what_if_is_read_only(self):
        with self.assertRaises(ValueError):
            tool_dispatch('update_session_settings',{'target':30},self.s)
        context=dict(values=deepcopy(self.values))
        tool_dispatch('compare_scenario',{'target':30},self.s,None,context)
        self.assertNotIn('proposal',context)
        self.assertEqual(context['values'],self.values)

    def test_no_op_and_duplicate_edit_tool_calls(self):
        context=dict(values=self.values)
        self.assertEqual(prepare_settings_update(context,{'target':20})['status'],'no_changes')
        prepare_settings_update(context,{'target':30})
        with self.assertRaises(ValueError):prepare_settings_update(context,{'spins':10})

    def test_commit_rechecks_limits_and_concurrent_form_edits(self):
        context=dict(values=self.values)
        prepare_settings_update(context,{'target':30})
        with self.assertRaisesRegex(ValueError,'changed while'):
            commit_settings_update(context['proposal'],{**self.values,'minimum':10})
        request=deepcopy(context['proposal']);request['after']['spins']=900
        with self.assertRaises(ValueError):commit_settings_update(request,self.values)
        request=deepcopy(context['proposal']);request['after']['session-data']={}
        with self.assertRaises(ValueError):commit_settings_update(request,self.values)

    def test_ui_commit_is_idempotent_and_reports_rejection(self):
        from app import commit_host_settings
        context=dict(values=self.values)
        prepare_settings_update(context,{'target':30})
        request=context['proposal']
        response=commit_host_settings(request,0,*self.values.values(),[],self.values,None)
        self.assertEqual(response[1],30)
        receipts=response[-1]
        with self.assertRaises(PreventUpdate):
            commit_host_settings(request,0,*response[:8],receipts,self.values,None)
        changed={**self.values,'spins':10}
        rejection=commit_host_settings(request,0,*changed.values(),[],self.values,None)
        self.assertTrue(all(v is no_update for v in rejection[:14]))
        self.assertEqual(rejection[-1][0]['status'],'rejected')

    def test_model_tool_round_trip_carries_validated_edit_to_ui(self):
        def tool(name,args):
            call=SimpleNamespace(id=name,function=SimpleNamespace(name=name,arguments=json.dumps(args)))
            return SimpleNamespace(tool_calls=[call],model_dump=lambda **kwargs:dict(role='assistant',tool_calls=[dict(id=name,type='function',function=dict(name=name,arguments=json.dumps(args)))]))
        final=SimpleNamespace(tool_calls=None,content='Your Step 1 changes are ready. Apply them when you want to recalculate.')
        api=MagicMock()
        api.chat.completions.create.side_effect=[SimpleNamespace(usage=None,choices=[SimpleNamespace(message=m)]) for m in (
            tool('get_current_comparison',{}),tool('update_session_settings',{'target':30}),final)]
        context=dict(values=deepcopy(self.values))
        with patch('agent.client',return_value=api),patch('agent.reserve_turn',return_value='test'),patch('agent.finish_turn'),patch('agent.db',return_value=MagicMock()):
            reply=generate([dict(role='user',content='Set my profit target to $30.')],self.values,None,context)
        self.assertEqual(reply['mode'],'AI analyst')
        self.assertEqual(reply['settings_update']['after']['target'],30)
        self.assertEqual(reply['trace'][1]['status'],'complete')
        self.assertEqual(context['values'],self.values)

    def test_default_edit_fits_context_with_all_three_shared_sessions(self):
        from host_context import build_session_context
        from practice import new_practice
        from freeplay import new_game
        from agent import MAX_CONTEXT_BYTES
        s=Scenario()
        session=new_practice(s,'martingale',30)
        shared=build_session_context(session['session'],session,new_game(s),'practice','free')
        def tool(name,args):
            call=SimpleNamespace(id=name,function=SimpleNamespace(name=name,arguments=json.dumps(args)))
            return SimpleNamespace(tool_calls=[call],model_dump=lambda **kwargs:dict(role='assistant',tool_calls=[dict(id=name,type='function',function=dict(name=name,arguments=json.dumps(args)))]))
        responses=iter([tool('get_current_comparison',{}),tool('update_session_settings',{'bankroll':8000,'maximum':8000}),SimpleNamespace(tool_calls=None,content='Your Step 1 edits are ready.')])
        sizes=[]
        def respond(**kwargs):
            sizes.append(len(json.dumps({'messages':kwargs['messages'],'tools':kwargs['tools']}).encode()))
            return SimpleNamespace(usage=None,choices=[SimpleNamespace(message=next(responses))])
        api=MagicMock();api.chat.completions.create.side_effect=respond
        with patch('agent.client',return_value=api),patch('agent.reserve_turn',return_value='test'),patch('agent.finish_turn'),patch('agent.db',return_value=MagicMock()):
            reply=generate([dict(role='user',content='Set bankroll and maximum wager to $8,000.')],asdict(s),shared,dict(values=asdict(s)))
        self.assertEqual(reply['mode'],'AI analyst')
        self.assertEqual(reply['settings_update']['after']['bankroll'],8000)
        self.assertEqual(len(sizes),3)
        self.assertTrue(all(size<=MAX_CONTEXT_BYTES for size in sizes))


class ApplySettingsTests(unittest.TestCase):
    setUp = SettingsTests.setUp
    def test_apply_current_form_and_combined_edits_return_real_comparison(self):
        from engine import compare
        for changes in ({},{'target':30,'wheel':'french'}):
            context=dict(values=deepcopy(self.values))
            result=tool_dispatch('apply_session_settings',changes,self.s,None,context)
            expected=compare(Scenario(**{**self.values,**changes}))
            self.assertEqual(result['calculation_id'],expected['id'])
            self.assertEqual(result['best']['success'],expected['rows'][0]['success'])
            self.assertEqual(context['proposal']['action'],'apply')
            self.assertEqual(context['values'],self.values)
            updated,receipt=commit_settings_update(context['proposal'],self.values)
            self.assertEqual(updated,expected['scenario'])
            self.assertEqual(receipt['action'],'apply')

    def test_apply_rejected_errors_leave_every_ui_output_unchanged(self):
        from app import commit_host_settings
        for changes in ({'bankroll':50},{'spins':501},{'wheel':'invalid'}):
            context=dict(values=deepcopy(self.values))
            with self.assertRaises(ValueError):
                tool_dispatch('apply_session_settings',changes,self.s,None,context)
            self.assertNotIn('proposal',context)
        context=dict(values=deepcopy(self.values))
        tool_dispatch('apply_session_settings',{},self.s,None,context)
        for current,proposal in (({**self.values,'target':30},context['proposal']),
                                  (self.values,{**context['proposal'],'calculation_id':'bad'})):
            reply=commit_host_settings(proposal,0,*current.values(),[],self.values,None)
            self.assertTrue(all(v is no_update for v in reply[:14]))
            self.assertEqual(reply[-1][0]['status'],'rejected')
        with self.assertRaises(ValueError):tool_dispatch('apply_session_settings',{},self.s)
        context=dict(values=deepcopy(self.values))
        with patch('agent.compare',side_effect=ValueError('calculator unavailable')):
            with self.assertRaises(ValueError):tool_dispatch('apply_session_settings',{},self.s,None,context)
        self.assertNotIn('proposal',context)

    def test_apply_updates_comparison_and_is_idempotent(self):
        from app import commit_host_settings
        from engine import compare
        context=dict(values=deepcopy(self.values))
        tool_dispatch('apply_session_settings',{'target':30},self.s,None,context)
        proposal=context['proposal']
        result=commit_host_settings(proposal,0,*self.values.values(),[],self.values,None)
        self.assertEqual(result[1],30)
        self.assertEqual(result[9]['id'],compare(Scenario(**proposal['after']))['id'])
        self.assertEqual(result[10],proposal['after'])
        self.assertEqual(result[-1][0]['status'],'applied')
        with self.assertRaises(PreventUpdate):commit_host_settings(proposal,0,*result[:8],result[-1],self.values,None)

    def test_new_comparison_preserves_tracker_and_records_with_original_rules(self):
        import app
        from engine import compare
        from practice import new_practice
        from session_tracker import record_number, state_token
        original=new_practice(self.s,'martingale',5)['session']
        original['history']=record_number(self.s,'martingale',5,[],'1')
        new=compare(Scenario(**{**self.values,'bankroll':200,'wheel':'french'}))
        def invoke(trigger,data,results=()):
            with patch.object(app,'ctx',SimpleNamespace(triggered_id=trigger)):
                return app.update_simple_session([],results,0,0,0,new,[],[],[],[],data)
        preserved,notice=invoke('calculation',deepcopy(original))
        self.assertEqual(preserved,original)
        self.assertIn('original settings',notice)
        self.assertIn('original',str(app.render_simple_session(preserved,new)))
        after,_=invoke(dict(type='record-spin',index=1,token=state_token(preserved)),preserved,[1])
        self.assertEqual(after['history'][-1]['net'],-5)
        self.assertEqual(after['history'][-1]['after'],[100,6])
        self.assertEqual(after['scenario'],original['scenario'])
        undone,_=invoke('session-undo',after)
        self.assertEqual(undone['history'],original['history'])
        row=new['rows'][0]
        with patch.object(app,'ctx',SimpleNamespace(triggered_id={'type':'choose-system','key':row['key'],'calculation':new['id']})):
            fresh,_=app.update_simple_session([1],[],0,0,0,new,[],[],[],[],original)
        self.assertEqual(fresh['scenario'],new['scenario'])
        self.assertEqual(fresh['history'],[])

    def test_apply_model_roundtrip_fits_context_with_shared_sessions(self):
        from host_context import build_session_context
        from practice import new_practice
        from freeplay import new_game
        from agent import MAX_CONTEXT_BYTES
        s=Scenario()
        session=new_practice(s,'martingale',30)
        shared=build_session_context(session['session'],session,new_game(s),'practice','free')
        def tool(name,args):
            call=SimpleNamespace(id=name,function=SimpleNamespace(name=name,arguments=json.dumps(args)))
            return SimpleNamespace(tool_calls=[call],model_dump=lambda **kwargs:dict(role='assistant',tool_calls=[dict(id=name,type='function',function=dict(name=name,arguments=json.dumps(args)))]))
        responses=iter([tool('get_current_comparison',{}),tool('apply_session_settings',{'target':300}),SimpleNamespace(tool_calls=None,content='The comparison is ready.')])
        sizes=[]
        def respond(**kwargs):
            sizes.append(len(json.dumps({'messages':kwargs['messages'],'tools':kwargs['tools']}).encode()))
            return SimpleNamespace(usage=None,choices=[SimpleNamespace(message=next(responses))])
        api=MagicMock();api.chat.completions.create.side_effect=respond
        with patch('agent.client',return_value=api),patch('agent.reserve_turn',return_value='test'),patch('agent.finish_turn'),patch('agent.db',return_value=MagicMock()):
            reply=generate([dict(role='user',content='Set my target to $300, apply and compare.')],asdict(s),shared,dict(values=asdict(s)))
        self.assertEqual(reply['mode'],'AI analyst',str(reply))
        self.assertEqual(reply['settings_update']['action'],'apply')
        self.assertEqual(len(sizes),3)
        self.assertTrue(all(size<=MAX_CONTEXT_BYTES for size in sizes),sizes)


if __name__=='__main__':unittest.main()
