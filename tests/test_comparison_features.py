"""Reports, isolated examples and published-rate token estimates."""
from copy import deepcopy
from dataclasses import asdict
from html.parser import HTMLParser
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from dash import no_update
from engine import Scenario,compare
from comparison_report import comparison_report
from example_guide import example_data
from pricing import estimate_cost,message_cost

S=Scenario(bankroll=100,target=20,loss_limit=100,minimum=5,maximum=50,chip=5,spins=8)

class PricingTests(unittest.TestCase):
    def test_cached_input_is_subtracted_not_double_charged(self):
        c=estimate_cost(dict(input=1000,cached=400,output=100))
        self.assertAlmostEqual(c['estimated_cost_usd'],.000114)
        self.assertEqual(c['measured_tokens']['uncached_input'],600)
        self.assertEqual(c['rates']['verified_on'],'2026-10-24')

    def test_no_ai_request_is_zero_but_missing_measurements_are_unknown(self):
        for mode in ('blocked','budget guard','calculator only'):
            self.assertEqual(estimate_cost({},mode=mode)['estimated_cost_usd'],0)
        for u in (None,{},dict(input=0,cached=0,output=0)):
            self.assertIsNone(estimate_cost(u,mode='connection error')['estimated_cost_usd'])

    def test_invalid_counts_and_unknown_models_are_unpriced(self):
        for u in (dict(input=100,cached=101,output=1),dict(input=-1,cached=0,output=1),dict(input=True,cached=0,output=1),dict(input=float('nan'),cached=0,output=1),dict(input=300000,cached=0,output=1)):
            self.assertIsNone(estimate_cost(u)['estimated_cost_usd'])
        self.assertIsNone(estimate_cost(dict(input=100,cached=0,output=10),'other-model')['estimated_cost_usd'])

    def test_partial_usage_and_exported_rate_provenance(self):
        from ai_evidence import export_run
        message=dict(role='assistant',content='A bounded response',mode='connection error',turn_id='cost-test',usage=dict(input=1000,cached=400,output=100,unreported_calls=1))
        result=export_run([message],'cost-test',[])
        self.assertAlmostEqual(result['estimated_cost_usd'],.000114)
        self.assertEqual(result['cost_estimate']['status'],'partial')
        self.assertIn('reported tokens only',result['cost_note'])
        self.assertTrue(result['cost_estimate']['rates']['source'].startswith('https://developers.openai.com/'))

    def test_new_reply_and_json_export_show_the_same_estimate(self):
        import app
        message=dict(role='assistant',content='Result',usage=dict(input=1000,cached=0,output=50),run=dict(id='same',model='gpt-6-luna'))
        tree=app.render_thread([message],True)
        serialized=json.dumps(tree,default=lambda n:n.to_plotly_json())
        self.assertIn('Estimated AI token cost: $0.000125',serialized)
        self.assertAlmostEqual(message_cost(message)['estimated_cost_usd'],.000125)

class ReportTests(unittest.TestCase):
    def test_report_has_applied_limits_ranking_embedded_chart_and_scope(self):
        r=compare(S);page=comparison_report(r,'martingale')
        self.assertIn(r['id'],page)
        self.assertIn('Maximum total wager per spin',page)
        self.assertIn('$100.00',page)
        self.assertIn('Final results: Martingale',page)
        self.assertIn('<svg',page)
        self.assertNotIn('<script',page)
        self.assertNotIn('<link',page)
        self.assertNotIn('src=',page)
        for row in r['rows']:self.assertIn(f"{row['success']:.4%}",page)
        self.assertIn('not a guarantee or a global optimum',page)
        self.assertIn('not unapplied field edits',page)

    def test_regenerates_client_numbers_without_exporting_extra_secrets(self):
        snapshot=deepcopy(compare(S));snapshot['rows'][0]['label']='<script>untrusted</script>'
        snapshot['rows'][0]['success']=1;snapshot['chat']='private transcript'
        page=comparison_report(snapshot)
        self.assertNotIn('untrusted',page);self.assertNotIn('private transcript',page)
        self.assertNotIn('100.0000%',page)
        self.assertEqual(snapshot['rows'][0]['label'],'<script>untrusted</script>')
        snapshot['id']='wrong'
        with self.assertRaises(ValueError):comparison_report(snapshot)

    def test_download_callback_uses_applied_snapshot_not_draft(self):
        import app
        r=compare(S);download=app.download_comparison_report(1,r,'martingale')
        self.assertEqual(download['type'],'text/html')
        self.assertTrue(download['filename'].endswith(r['id']+'.html'))
        self.assertIn('Final results: Martingale',download['content'])

class ExampleTests(unittest.TestCase):
    def test_fixed_examples_have_correct_starting_stakes_and_target(self):
        r,bench=example_data()
        self.assertEqual(r['scenario'],asdict(Scenario()))
        self.assertEqual([b['base'] for b in bench],[5,200,200])
        self.assertAlmostEqual(bench[1]['success'],1-(19/37)**2)
        self.assertAlmostEqual(bench[2]['success'],18/37)
        self.assertIn('fixed starting amounts',comparison_report(r,benchmarks=bench))

    def test_navigation_has_no_settings_or_game_outputs(self):
        import app
        step=0
        for trigger,expected in [('try-example',0),('example-next',1),('example-next',2),('example-back',1)]:
            with patch.object(app,'ctx',SimpleNamespace(triggered_id=trigger)):
                reply=app.navigate_example(1,0,0,1,step)
            self.assertEqual(len(reply),5)
            self.assertEqual(reply[2],expected);self.assertEqual(reply[1],dict(display='flex'));step=reply[2]
        with patch.object(app,'ctx',SimpleNamespace(triggered_id='example-close')):
            closed=app.navigate_example(1,1,0,0,step)
        self.assertIs(closed[0],no_update);self.assertEqual(closed[1],dict(display='none'))


class UsageBookkeepingTests(unittest.TestCase):
    def exercise(self,fail_second=False):
        from unittest.mock import MagicMock
        from test_adversarial_safety import tool_message
        import agent
        usage=SimpleNamespace(prompt_tokens=100,completion_tokens=10,prompt_tokens_details=SimpleNamespace(cached_tokens=40))
        first=SimpleNamespace(usage=usage,choices=[SimpleNamespace(message=tool_message('get_current_comparison',{}))])
        final=RuntimeError('test provider failure') if fail_second else SimpleNamespace(usage=usage,choices=[SimpleNamespace(message=SimpleNamespace(tool_calls=None,content='Verified results are available.'))])
        api=MagicMock();api.chat.completions.create.side_effect=[first,final]
        with patch('agent.client',return_value=api),patch('agent.reserve_turn',return_value='pricing-test'),patch('agent.finish_turn'),patch('agent.db',return_value=MagicMock()):
            return agent.generate([dict(role='user',content='Explain the current comparison.')],asdict(S))

    def test_measured_provider_calls_are_counted_once(self):
        reply=self.exercise()
        self.assertEqual(reply['usage'],dict(input=200,cached=80,output=20,reported_calls=2,unreported_calls=0))
        self.assertAlmostEqual(message_cost(reply)['estimated_cost_usd'],.0000228)

    def test_provider_failure_keeps_reported_cost_partial(self):
        reply=self.exercise(True)
        self.assertEqual(reply['usage']['reported_calls'],1)
        self.assertEqual(reply['usage']['unreported_calls'],1)
        self.assertEqual(message_cost(reply)['status'],'partial')
        self.assertAlmostEqual(message_cost(reply)['estimated_cost_usd'],.0000114)

if __name__=='__main__':unittest.main()
