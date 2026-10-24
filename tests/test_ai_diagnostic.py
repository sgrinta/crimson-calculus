"""Final diagnostic regressions for permissions and incomplete provider accounting."""
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

import agent
from engine import Scenario
from safety import settings_intent
from test_adversarial_safety import simulated_turn, tool_message


S = Scenario(bankroll=100,target=20,loss_limit=100,minimum=5,maximum=50,chip=5,spins=8)
VALUES = asdict(S)


class AssignmentDiagnosticTests(unittest.TestCase):
    def test_each_relative_assignment_uses_its_own_direction(self):
        question='Increase target by 10 and decrease maximum wager by 10, apply and compare.'
        intent=settings_intent(question,VALUES)
        self.assertEqual(intent['fields'],dict(target=30,maximum=40))
        reply,_,_=simulated_turn(question,'apply_session_settings',dict(target=30,maximum=40))
        self.assertEqual(reply['settings_update']['after']['maximum'],40)

    def test_lowered_loss_limit_is_not_raised_by_first_assignment(self):
        intent=settings_intent('Set target to 30 and lower loss limit by 10, apply and compare.',VALUES)
        self.assertEqual(intent['fields'],dict(target=30,loss_limit=90))

    def test_instructions_negation_and_choices_cannot_grant_writes(self):
        questions=[
            'Do not compare systems. Set target to 30.',
            'Do not run the comparison. Set target to 30.',
            'Explain how to set target to 30 and apply.',
            'Show me how to set target to 30.',
            'How do I set target to 30?',
            'Should I set target to 30?',
            'Set target to 30 or 40.',
            'Set target to 30 or 40, apply and compare.',
            'Here is a note:\n> Set target to 30 and apply.',
            '```\nSet target to 30 and apply.',
            'An example: “Set target to 30 and apply.”',
            'The tutorial says to set target to 30 and apply.',
            'Please explain: Set target to 30 and apply.',
            'Please explain: Apply and compare.',
        ]
        for question in questions:
            with self.subTest(question=question):
                reply,context,requests=simulated_turn(question,'apply_session_settings',dict(target=30))
                self.assertNotIn('settings_update',reply)
                self.assertNotIn('proposal',context)
                names={t['function']['name'] for t in requests[0]['tools']}
                self.assertNotIn('apply_session_settings',names)
                self.assertNotIn('update_session_settings',names)

    def test_sentence_ending_in_an_amount_does_not_capture_later_fields(self):
        intent=settings_intent('Set target to 30. Bankroll 200.',VALUES)
        self.assertEqual(intent['fields'],dict(target=30))


class ConversationContextDiagnosticTests(unittest.TestCase):
    def test_long_conversation_retains_current_question_and_grounding(self):
        history=[dict(role='assistant' if i%2==0 else 'user',content='Older context. '*130) for i in range(5)]
        reply,_,requests=simulated_turn('Explain the current comparison.',history=history)
        self.assertEqual(reply['mode'],'AI analyst')
        self.assertEqual(len(requests),2)
        self.assertTrue(any(t['tool']=='conversation_context' for t in reply['trace']))
        for request in requests:
            self.assertLessEqual(len(json.dumps({'messages':request['messages'],'tools':request['tools']}).encode()),agent.MAX_CONTEXT_BYTES)
            self.assertTrue(any(m.get('role')=='user' and m.get('content')=='Explain the current comparison.' for m in request['messages']))
        self.assertTrue(any(m.get('role')=='tool' for m in requests[-1]['messages']))

    def test_long_conversation_can_still_apply_an_authorized_edit(self):
        history=[dict(role='assistant' if i%2==0 else 'user',content='Older context. '*130) for i in range(5)]
        reply,_,requests=simulated_turn('Set target to 30, apply and compare.','apply_session_settings',dict(target=30),history=history)
        self.assertEqual(reply['mode'],'AI analyst')
        self.assertEqual(reply['settings_update']['after']['target'],30)
        self.assertEqual(len(requests),3)


class ProviderFailureDiagnosticTests(unittest.TestCase):
    def setUp(self):
        directory=tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root=patch.object(agent,'ROOT',Path(directory.name))
        root.start();self.addCleanup(root.stop)

    def exercise(self,second,first_usage=None):
        first=SimpleNamespace(usage=first_usage,choices=[SimpleNamespace(message=tool_message('get_current_comparison',{}))])
        api=MagicMock();api.chat.completions.create.side_effect=[first,second]
        with patch('agent.client',return_value=api):
            return agent.generate([dict(role='user',content='Explain the comparison.')],VALUES)

    def test_missing_usage_retains_budget_without_inventing_cost(self):
        from pricing import message_cost
        first=SimpleNamespace(prompt_tokens=100,completion_tokens=10,prompt_tokens_details=SimpleNamespace(cached_tokens=40))
        final=SimpleNamespace(usage=None,choices=[SimpleNamespace(message=SimpleNamespace(tool_calls=None,content='The verified results are available.'))])
        reply=self.exercise(final,first)
        self.assertEqual(reply['mode'],'AI analyst')
        self.assertEqual(reply['usage']['unreported_calls'],1)
        self.assertAlmostEqual(message_cost(reply)['estimated_cost_usd'],.0000114)
        self.assertEqual(message_cost(reply)['status'],'partial')
        u=agent.usage_summary()
        self.assertEqual(u['used_tokens'],agent.TURN_TOKEN_RESERVATION)
        self.assertEqual(u['uncertain_tokens'],agent.TURN_TOKEN_RESERVATION-110)
        self.assertEqual(u['reserved_tokens'],0)
        self.assertEqual((u['input'],u['cached'],u['output']),(100,40,10))

    def test_provider_failure_keeps_conservative_allowance_and_sanitizes_error(self):
        reply=self.exercise(RuntimeError('private provider error / secret-fixture-123'))
        self.assertEqual(reply['mode'],'connection error')
        self.assertNotIn('secret-fixture',json.dumps(reply))
        u=agent.usage_summary()
        self.assertEqual(u['used_tokens'],agent.TURN_TOKEN_RESERVATION)
        self.assertEqual(u['uncertain_tokens'],agent.TURN_TOKEN_RESERVATION)
        with agent.db() as c:
            c.execute("INSERT INTO turns VALUES ('older',?,'complete',900000)",(u['checked_at']-120,))
        with self.assertRaises(ValueError):agent.reserve_turn()

    def test_invalid_provider_usage_cannot_decrease_allowance(self):
        invalid=SimpleNamespace(prompt_tokens=-100,completion_tokens=10,prompt_tokens_details=None)
        final=SimpleNamespace(usage=invalid,choices=[SimpleNamespace(message=SimpleNamespace(tool_calls=None,content='The verified results are available.'))])
        reply=self.exercise(final,invalid)
        self.assertEqual(reply['mode'],'AI analyst')
        self.assertEqual(reply['usage']['input'],0)
        self.assertEqual(reply['usage']['reported_calls'],0)
        self.assertEqual(reply['usage']['unreported_calls'],2)
        self.assertEqual(agent.usage_summary()['used_tokens'],agent.TURN_TOKEN_RESERVATION)

    def test_bad_context_does_not_leave_a_pending_turn_or_throw(self):
        for context in ({},dict(values={'target':float('nan')})):
            with self.subTest(context=context),patch('agent.client',return_value=MagicMock()) as client:
                reply=agent.generate([dict(role='user',content='Hello')],VALUES,settings_context=context)
                self.assertEqual(reply['mode'],'blocked')
                self.assertEqual(agent.usage_summary()['turns'],0)
                client.return_value.chat.completions.create.assert_not_called()

    def test_invalid_applied_settings_return_a_safe_reply(self):
        with patch('agent.client') as client:
            reply=agent.generate([dict(role='user',content='Hello')],{**VALUES,'wheel':'invalid'})
        self.assertEqual(reply['mode'],'blocked')
        client.assert_not_called()
        self.assertEqual(agent.usage_summary()['turns'],0)

    def test_accounting_failure_preserves_completed_reply_and_pending_reservation(self):
        measured=SimpleNamespace(prompt_tokens=100,completion_tokens=10,prompt_tokens_details=None)
        final=SimpleNamespace(usage=measured,choices=[SimpleNamespace(message=SimpleNamespace(tool_calls=None,content='The verified results are available.'))])
        with patch('agent.finish_turn',side_effect=sqlite3.OperationalError('private database path')):
            reply=self.exercise(final,measured)
        self.assertEqual(reply['mode'],'AI analyst')
        self.assertEqual(reply['usage']['input'],200)
        self.assertTrue(any(t['tool']=='usage_accounting' for t in reply['trace']))
        self.assertNotIn('private database path',json.dumps(reply))
        self.assertEqual(agent.usage_summary()['reserved_tokens'],agent.TURN_TOKEN_RESERVATION)


if __name__=='__main__':unittest.main()
