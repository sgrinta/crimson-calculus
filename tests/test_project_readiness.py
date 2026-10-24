"""Evidence, setup, undo and rolling allowance boundaries."""
from copy import deepcopy
from dataclasses import asdict
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import agent
from ai_evidence import export_run
from engine import Scenario
from host_settings import undo_settings_update, prepare_settings_update
from setup_check import key_configuration, run_checks


class UndoSettingsTests(unittest.TestCase):
    def setUp(self):
        self.s=Scenario(bankroll=100,target=20,loss_limit=100,minimum=5,maximum=50,chip=5,spins=8)
        self.before=asdict(self.s)

    def commit(self,proposal,fields,receipts=None,active=None,snapshot=None,undo=False):
        import app
        with patch.object(app,'ctx',SimpleNamespace(triggered_id='host-settings-undo' if undo else 'host-settings-request')):
            return app.commit_host_settings(proposal,1 if undo else 0,*fields.values(),receipts or [],active or self.before,snapshot)

    def test_apply_undo_restores_distinct_draft_and_applied_settings(self):
        draft={**self.before,'target':25}
        context=dict(values=draft)
        agent.tool_dispatch('apply_session_settings',dict(target=30,wheel='french'),self.s,None,context)
        result=self.commit(context['proposal'],draft)
        self.assertEqual(result[1],30)
        self.assertEqual(result[10]['wheel'],'french')
        restored=self.commit(context['proposal'],dict(zip(self.before,result[:8])),result[-1],result[10],result[13],undo=True)
        self.assertEqual(dict(zip(self.before,restored[:8])),draft)
        self.assertEqual(restored[10],self.before)
        self.assertIsNone(restored[13])
        self.assertEqual(restored[-1][0]['status'],'undone')
        # No callback output can modify any tracked/practice/free-play store.
        self.assertEqual(len(restored),16)

    def test_edit_only_undo_restores_unfinished_form_without_recalculating(self):
        from dash import no_update
        draft={**self.before,'target':None}
        context=dict(values=draft)
        prepare_settings_update(context,dict(target=30))
        result=self.commit(context['proposal'],draft)
        restored=self.commit(context['proposal'],dict(zip(self.before,result[:8])),result[-1],self.before,result[13],undo=True)
        self.assertIsNone(restored[1])
        self.assertTrue(all(x is no_update for x in restored[8:13]))

    def test_undo_refuses_newer_form_or_comparison_and_double_undo(self):
        from dash import no_update
        context=dict(values=self.before)
        prepare_settings_update(context,dict(target=30))
        result=self.commit(context['proposal'],self.before)
        after=dict(zip(self.before,result[:8]))
        for fields,active,snapshot in (({**after,'target':35},self.before,result[13]),
                                       (after,{**self.before,'wheel':'french'},result[13]),
                                       (after,self.before,None)):
            response=self.commit(context['proposal'],fields,result[-1],active,snapshot,undo=True)
            self.assertTrue(all(x is no_update for x in response[:14]))
            self.assertIs(response[-1],no_update)
            self.assertTrue(response[14])


class EvidenceExportTests(unittest.TestCase):
    def test_export_retains_evidence_and_redacts_secrets_and_extra_fields(self):
        from agent import MODEL
        secret='private-fixture-key-123456'
        reply=dict(role='assistant',content='Result '+secret,mode='AI analyst',usage=dict(input=100,cached=40,output=10),
            run=dict(id='test',question='Try '+secret,model=MODEL,applied_scenario=asdict(Scenario()),form_fields=asdict(Scenario()),session_sharing_enabled=False,hidden_secret=secret),
            trace=[dict(tool='apply_session_settings',status='complete',arguments=dict(target=300,api_key=secret),calculation_id='abc')],
            system_prompt='do not export',session_data={'secret':'private log'})
        with patch.dict(os.environ,{'PORTKEY_API_KEY':secret}):
            exported=export_run([dict(role='user',content='q'),reply],'test',[])
        encoded=json.dumps(exported)
        self.assertNotIn(secret,encoded)
        self.assertNotIn('private log',encoded)
        self.assertNotIn('do not export',encoded)
        self.assertNotIn('api_key',exported['tools'][0]['arguments'])
        self.assertEqual(exported['tools'][0]['arguments'],dict(target=300))
        self.assertEqual(exported['tokens'],dict(input=100,cached=40,output=10))
        self.assertAlmostEqual(exported['estimated_cost_usd'],.0000114)
        self.assertEqual(exported['cost_estimate']['rates']['verified_on'],'2026-10-24')
        self.assertIn('[REDACTED]',exported['question'])
        with self.assertRaises(ValueError):export_run([reply],'missing',[])

    def test_export_records_undo_receipt_and_only_matching_run(self):
        s=asdict(Scenario())
        proposal=dict(id='change',action='apply',before=s,after={**s,'target':300})
        reply=dict(role='assistant',content='Ready',turn_id='turn',settings_update=proposal)
        result=export_run([dict(role='user',content='Set target to 300'),reply],'turn',
                          [dict(id='change',status='undone',undone_at='now',before_applied=s,after_applied={**s,'target':300})])
        self.assertEqual(result['settings_transaction']['receipt']['status'],'undone')
        self.assertEqual(result['question'],'Set target to 300')


class ReadinessTests(unittest.TestCase):
    def test_parent_env_precedence_without_exposing_keys(self):
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,{},clear=True):
            parent=Path(directory);root=parent/'app';root.mkdir()
            (parent/'.env').write_text('PORTKEY_API_KEY=parent-private-123\n')
            result=key_configuration(root)
            self.assertEqual(result['source'],'parent .env')
            self.assertNotIn('parent-private',json.dumps(result))
            (root/'.env').write_text('PORTKEY_API_KEY=project-private-123\n')
            self.assertEqual(key_configuration(root)['source'],'project .env')
            os.environ['PORTKEY_API_KEY']='environment-private-123'
            self.assertEqual(key_configuration(root)['source'],'process environment')

    def test_local_check_never_calls_ai_and_missing_artwork_is_reported(self):
        with tempfile.TemporaryDirectory() as directory,patch('agent.generate') as generate:
            result=run_checks(False,Path(directory))
            generate.assert_not_called()
            self.assertFalse(result['ready'])
            self.assertEqual(next(c for c in result['checks'] if c['name']=='Bundled data & artwork')['status'],'fail')

    def test_incompatible_dependency_version_is_reported(self):
        import setup_check
        actual=setup_check.version
        with patch('setup_check.version',side_effect=lambda package:'2.9.0' if package=='dash' else actual(package)):
            result=run_checks(False)
        self.assertFalse(result['ready'])
        dependencies=next(r for r in result['checks'] if r['name']=='Dependencies')
        self.assertEqual(dependencies['status'],'fail')
        self.assertIn('dash',dependencies['detail'])

    def test_optional_connection_uses_only_fictional_scenario(self):
        with patch('setup_check.key_configuration',return_value=dict(configured=True,key_name='PORTKEY_API_KEY',source='process environment')),patch('agent.generate',return_value=dict(mode='AI analyst',usage=dict(input=10,cached=0,output=2),turn_id='check')) as generate:
            result=run_checks(True)
        self.assertTrue(result['ready'])
        self.assertEqual(generate.call_args.args[1]['bankroll'],100)
        self.assertEqual(len(generate.call_args.args),2)
        self.assertEqual(result['checks'][-1]['status'],'pass')


class RollingUsageTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.root=patch.object(agent,'ROOT',Path(self.directory.name));self.root.start();self.addCleanup(self.root.stop)
        self.now=1000000.

    def rows(self,rows):
        with agent.db() as c:
            c.executemany('INSERT INTO turns VALUES (?,?,?,?)',[(str(i),stamp,status,tokens) for i,(stamp,tokens,status) in enumerate(rows)])

    def test_pending_reservations_and_cached_input_are_not_double_counted(self):
        self.rows([(self.now-120,100000,'complete'),(self.now-100,0,'pending')])
        with agent.db() as c:c.execute('INSERT INTO calls VALUES (?,?,?,?,?,?,?)',('0',self.now-120,'test',100,80,10,1))
        u=agent.usage_summary(self.now)
        self.assertEqual(u['used_tokens'],100000)
        self.assertEqual(u['reserved_tokens'],70000)
        self.assertEqual(u['remaining_tokens'],830000)
        self.assertEqual((u['input'],u['cached'],u['output']),(100,80,10))
        self.assertTrue(u['available']);self.assertIsNone(u['next_available_at'])

    def test_rate_limited_request_becomes_available_at_first_expiry(self):
        self.rows([(self.now-30+i,0,'complete') for i in range(4)])
        u=agent.usage_summary(self.now)
        self.assertFalse(u['available'])
        self.assertEqual(u['next_available_at'],self.now+30)
        self.assertTrue(agent.usage_summary(self.now+30)['available'])

    def test_token_cap_uses_rolling_expiry_not_midnight(self):
        self.rows([(self.now-86300,950000,'complete')])
        u=agent.usage_summary(self.now)
        self.assertFalse(u['available'])
        self.assertEqual(u['next_available_at'],self.now+100)
        self.assertTrue(agent.usage_summary(self.now+100)['available'])


if __name__=='__main__':unittest.main()
