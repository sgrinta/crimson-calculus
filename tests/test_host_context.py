"""AI session access must replay payouts, separate sources, and respect sharing/Undo."""
from copy import deepcopy
from dataclasses import asdict, replace
from pathlib import Path
import json
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import Scenario
from practice import new_practice, begin_spin, finish_spin, undo_practice
from session_tracker import record, record_number
from freeplay import new_game, edit_bet, begin_game_spin, finish_game_spin
from host_context import build_session_context, read_session_log
from agent import generate, tool_dispatch


class HostContextTests(unittest.TestCase):
    def setUp(self):
        self.s = Scenario(bankroll=100, target=20, loss_limit=100, minimum=5, maximum=50, chip=5, spins=8)

    def tracked(self, s=None):
        return new_practice(s or self.s, 'martingale', 5, 'black')['session']

    def spin(self, data, number):
        pending = begin_spin(data, choose=lambda legal: number)
        return finish_spin(pending, pending['pending']['id'])

    def free_spin(self, data, number):
        pending = begin_game_spin(data, choose=lambda legal: number)
        return finish_game_spin(pending, pending['pending']['id'])

    def test_three_logs_keep_own_scenario_bets_balances_and_probabilities(self):
        tracked = self.tracked()
        tracked['history'] = record_number(self.s, 'martingale', 5, [], '2', even_bet='black')
        practice = self.spin(new_practice(replace(self.s, wheel='french'), 'martingale', 5), '0')
        free = edit_bet(new_game(replace(self.s, wheel='triple')), 'straight:000', 5)
        free = self.free_spin(free, '000')
        context = build_session_context(tracked, practice, free, 'practice', 'free')
        sources = context['summary']['sources']
        self.assertEqual([sources[k]['bankroll'] for k in ('tracked', 'practice', 'free_play')], [105, 97.5, 275])
        self.assertEqual([sources[k]['scenario']['wheel'] for k in ('tracked', 'practice', 'free_play')], ['single', 'french', 'triple'])
        self.assertIsNone(sources['free_play']['remaining_session_success'])
        row = read_session_log(context, 'free_play', 1, 3, 0)['rows'][0]
        self.assertEqual((row['winning_number'], row['net'], row['profit']), ('000', 175, 175))
        row = read_session_log(context, 'tracked', 1, 3, 0)['rows'][0]
        self.assertEqual(row['bets'], [{'position': 'Black', 'amount': 5}])
        json.dumps(context, allow_nan=False)

    def test_result_button_does_not_invent_pocket_and_undo_refreshes(self):
        tracked = self.tracked()
        tracked['history'] = record(self.s, 'martingale', 5, [], 1, even_bet='black')
        row = build_session_context(tracked)['logs']['tracked'][0]
        self.assertIsNone(row['winning_number'])
        self.assertEqual(row['entry_method'], 'Result button')
        practice = self.spin(new_practice(self.s, 'martingale', 5), '2')
        before = build_session_context(practice=practice)
        after = build_session_context(practice=undo_practice(practice))
        self.assertEqual(before['summary']['sources']['practice']['bankroll'], 95)
        self.assertEqual(after['summary']['sources']['practice']['bankroll'], 100)
        self.assertEqual(after['logs']['practice'], [])
        self.assertEqual(len(before['logs']['practice']), 1)  # Previous request is an immutable snapshot.

    def test_pending_winning_numbers_and_saved_extras_never_enter_ai_context(self):
        practice = begin_spin(new_practice(self.s, 'martingale', 5), choose=lambda legal: '36')
        free = begin_game_spin(edit_bet(new_game(self.s), 'red', 5), choose=lambda legal: '35')
        tracked = self.tracked()
        tracked['instructions'] = 'LEAK_THIS_SECRET'
        context = build_session_context(tracked, practice, free)
        self.assertTrue(context['summary']['sources']['practice']['spin_in_progress'])
        self.assertTrue(context['summary']['sources']['free_play']['spin_in_progress'])
        self.assertEqual(context['logs']['practice'], [])
        self.assertEqual(context['logs']['free_play'], [])
        encoded = json.dumps(context)
        self.assertNotIn('LEAK_THIS_SECRET', encoded)
        self.assertNotIn('winning_number', encoded)
        self.assertNotIn('pending', encoded)

    def test_inconsistent_tracker_excluded_and_free_play_balances_recomputed(self):
        tracked = self.tracked()
        tracked['history'] = record_number(self.s, 'martingale', 5, [], '2', even_bet='black')
        tracked['history'][0]['after'][0] = 999999
        free = self.free_spin(edit_bet(new_game(self.s), 'red', 5), '2')
        free['history'][0].update(bankroll=999999, profit=999999, net=999999)
        context = build_session_context(tracked=tracked, free_play=free)
        self.assertEqual(context['summary']['sources']['tracked']['status'], 'invalid')
        self.assertNotIn('tracked', context['logs'])
        self.assertEqual(context['summary']['sources']['free_play']['bankroll'], 95)
        self.assertEqual(context['logs']['free_play'][0]['net'], -5)
        self.assertNotIn('999999', json.dumps(context))

    def test_every_spin_and_large_bet_slip_can_be_paged(self):
        s = replace(self.s, spins=20)
        free = new_game(s)
        for n in range(1, 9):
            free = edit_bet(free, f'straight:{n}', 5)
        for _ in range(2):
            free = self.free_spin(free, '36')
        context = build_session_context(free_play=free)
        first = read_session_log(context, 'free_play', 1, 1, 0)
        rest = read_session_log(context, 'free_play', 1, 1, 6)
        self.assertEqual(first['next_spin'], 2)
        self.assertEqual(first['rows'][0]['next_bet_offset'], 6)
        self.assertEqual(first['rows'][0]['bet_count'], 8)
        self.assertEqual(len(first['rows'][0]['bets']) + len(rest['rows'][0]['bets']), 8)
        self.assertIsNone(rest['rows'][0]['next_bet_offset'])
        self.assertEqual(read_session_log(context, 'free_play', 2, 1, 0)['rows'][0]['bankroll'], 20)
        self.assertEqual(read_session_log(context, 'free_play', 0, 1, 0)['rows'][0]['spin'], 0)

    def test_off_absent_and_invalid_tool_arguments(self):
        args = dict(source='tracked', start_spin=1, limit=3, bet_offset=0)
        self.assertEqual(tool_dispatch('get_session_log', args, self.s)['status'], 'sharing_off')
        self.assertEqual(read_session_log(build_session_context(), **args)['status'], 'not_started')
        for changed in ({'source': '../.env'}, {'limit': 4}, {'start_spin': True}, {'bet_offset': -1}):
            with self.assertRaises(ValueError):
                read_session_log(None, **dict(args, **changed))

    def test_model_round_trip_reads_verified_log_and_trace(self):
        tracked = self.tracked()
        tracked['history'] = record_number(self.s, 'martingale', 5, [], '2', even_bet='black')
        context = build_session_context(tracked)
        def message(name, args):
            call = SimpleNamespace(id=name, function=SimpleNamespace(name=name, arguments=json.dumps(args)))
            return SimpleNamespace(tool_calls=[call], model_dump=lambda **kwargs: dict(role='assistant', tool_calls=[
                dict(id=name, type='function', function=dict(name=name, arguments=json.dumps(args)))]))
        final = SimpleNamespace(tool_calls=None, content='Step 3: your black bet won $5; your bankroll is $105.')
        api = MagicMock()
        api.chat.completions.create.side_effect = [SimpleNamespace(usage=None, choices=[SimpleNamespace(message=m)]) for m in (
            message('get_current_comparison', {}),
            message('get_session_log', dict(source='tracked', start_spin=1, limit=3, bet_offset=0)), final)]
        with patch('agent.client', return_value=api), patch('agent.reserve_turn', return_value='test'), patch('agent.finish_turn'), patch('agent.db', return_value=MagicMock()):
            result = generate([dict(role='user', content='What happened on spin 1 in Step 3?')], asdict(self.s), context)
        self.assertEqual(result['mode'], 'AI analyst')
        self.assertEqual(result['trace'][1]['source'], 'tracked')
        self.assertEqual(result['trace'][1]['access'], 'available')
        self.assertEqual(result['trace'][1]['spins_returned'], 1)
        sent = api.chat.completions.create.call_args.kwargs['messages']
        tool_rows = json.loads(next(m['content'] for m in sent if m.get('tool_call_id') == 'get_session_log'))
        self.assertEqual(tool_rows['rows'][0]['bankroll'], 105)

    def test_callback_respects_off_and_uses_session_own_scenario(self):
        from app import think
        tracked = self.tracked()
        with patch('app.generate', return_value=dict(content='ok')) as model:
            think(1, [dict(role='user', content='Hello')], False, asdict(replace(self.s, bankroll=200)), tracked, [], None, None, 'track', 'system')
            self.assertIsNone(model.call_args.args[2])
            think(1, [dict(role='user', content='Hello')], False, asdict(replace(self.s, bankroll=200)), tracked, ['include'], None, None, 'track', 'system')
            self.assertEqual(model.call_args.args[2]['summary']['sources']['tracked']['scenario']['bankroll'], 100)


if __name__ == '__main__':
    unittest.main()
