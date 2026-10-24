"""Independent finite-session oracles and stopping-boundary regressions."""
from collections import defaultdict
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import Scenario, LABELS, adaptive, classic_profile, classic_value, custom_portfolio
from session_tracker import record_number, snapshot


def progression_oracle(s, name, base):
    """Enumerate short sessions from the written progression rules, using rationals."""
    def stake(index):
        if name == 'flat':return base
        if name == 'martingale':return base * 2 ** index
        if name == 'grand_martingale':return base * (2 ** (index + 1) - 1)
        if name in ('dalembert', 'reverse_dalembert'):return base * (index + 1)
        if name == 'paroli':return base * [1, 2, 4][index]
        if name == '1326':return base * [1, 3, 2, 6][index]
        first, second = 1, 1
        for _ in range(index):first, second = second, first + second
        return base * first

    def next_index(index, win):
        if name == 'flat':return 0
        if name in ('martingale', 'grand_martingale'):return 0 if win else index + 1
        if name == 'dalembert':return max(0, index - 1) if win else index + 1
        if name == 'reverse_dalembert':return index + 1 if win else max(0, index - 1)
        if name == 'fibonacci':return max(0, index - 2) if win else index + 1
        return (index + 1) % (3 if name == 'paroli' else 4) if win else 0

    outcomes = [(Fraction(1), Fraction(18, s.pockets), True),
                (Fraction(-1), Fraction(18 if s.wheel == 'french' else s.pockets - 18, s.pockets), False)]
    if s.wheel == 'french':outcomes.append((Fraction(-1, 2), Fraction(1, 37), False))
    active = {(Fraction(0), 0):Fraction(1)}
    terminal = defaultdict(Fraction)
    expected_spins = turnover = blocked = horizon = Fraction(0)
    for _ in range(s.spins):
        following = defaultdict(Fraction)
        for (profit, index), probability in active.items():
            wager = stake(index)
            if profit >= s.target:terminal[profit] += probability
            elif wager > s.maximum or wager > s.loss_limit + profit:
                terminal[profit] += probability
                blocked += probability
            else:
                expected_spins += probability
                turnover += probability * wager
                for multiplier, chance, win in outcomes:
                    following[profit + multiplier * wager, next_index(index, win)] += probability * chance
        active = following
    for (profit, _), probability in active.items():
        terminal[profit] += probability
        if profit < s.target:horizon += probability
    return dict(distribution=terminal,
                success=sum(p for net, p in terminal.items() if net >= s.target),
                mean=sum(net * p for net, p in terminal.items()),
                expected_spins=expected_spins, expected_turnover=turnover,
                blocked=blocked, horizon=horizon)


class IndependentEngineAuditTests(unittest.TestCase):
    def test_named_progressions_match_independent_rational_enumeration(self):
        cases = [Scenario(bankroll=25, target=15, loss_limit=25, maximum=20, spins=6),
                 Scenario(bankroll=60, target=20, loss_limit=35, maximum=30, spins=7)]
        for original in cases:
            for wheel in ('single', 'double', 'triple', 'french'):
                s = replace(original, wheel=wheel)
                for name in LABELS:
                    for base in (5, 10, 20):
                        with self.subTest(scenario=s, name=name, base=base):
                            oracle = progression_oracle(s, name, base)
                            actual = classic_profile(s, name, base)
                            for field in ('success', 'mean', 'expected_spins', 'expected_turnover', 'blocked', 'horizon'):
                                self.assertAlmostEqual(actual[field], float(oracle[field]), places=11, msg=field)
                            success, mean = classic_value(s, name, base)
                            self.assertAlmostEqual(success, float(oracle['success']), places=12)
                            self.assertAlmostEqual(mean, float(oracle['mean']), places=11)
                            actual_pmf = {row['net']:row['probability'] for row in actual['distribution']}
                            self.assertEqual(set(actual_pmf), set(oracle['distribution']))
                            for net, probability in oracle['distribution'].items():
                                self.assertAlmostEqual(actual_pmf[net], float(probability), places=12)

    def test_final_spin_is_horizon_even_when_next_wager_would_be_blocked(self):
        s = Scenario(bankroll=100, target=10, loss_limit=10, minimum=10, maximum=10, spins=1)
        profiles = [classic_profile(s, 'flat', 10), adaptive(s, 'even')[0],
                    custom_portfolio(s, [dict(position='red', amount=10)])['profile']]
        for profile in profiles:
            self.assertAlmostEqual(profile['success'], 18/37)
            self.assertAlmostEqual(profile['horizon'], 19/37)
            self.assertEqual(profile['blocked'], 0)
        history = record_number(s, 'flat', 10, [], '2')
        self.assertIn('Spin limit', snapshot(s, 'flat', 10, history, with_stats=False)['stop'])

    def test_depleted_loss_allowance_is_blocked_before_horizon_with_cash_remaining(self):
        s = Scenario(bankroll=100, target=10, loss_limit=10, minimum=10, maximum=10, spins=2)
        profiles = [classic_profile(s, 'flat', 10), adaptive(s, 'even')[0],
                    custom_portfolio(s, [dict(position='red', amount=10)])['profile']]
        for profile in profiles:
            self.assertAlmostEqual(profile['blocked'], 19/37)
            self.assertEqual(profile['horizon'], 0)
            self.assertEqual(profile['ruin'], 0)
            self.assertAlmostEqual(profile['success'] + profile['blocked'] + profile['horizon'], 1)

    def test_zero_cash_ruin_is_separate_from_reason_for_stopping(self):
        for spins in (1, 2):
            s = Scenario(bankroll=10, target=10, loss_limit=10, minimum=10, maximum=10, spins=spins)
            for profile in (classic_profile(s, 'flat', 10), adaptive(s, 'even')[0]):
                self.assertAlmostEqual(profile['ruin'], 19/37)
                self.assertAlmostEqual(profile['horizon' if spins == 1 else 'blocked'], 19/37)

    def test_fractional_french_cash_is_classified_without_an_extra_spin(self):
        for spins in (1, 2):
            s = Scenario(bankroll=100, target=10, loss_limit=10, minimum=10, maximum=10,
                         spins=spins, wheel='french')
            for profile in (classic_profile(s, 'flat', 10), adaptive(s, 'even')[0]):
                self.assertAlmostEqual(profile['horizon' if spins == 1 else 'blocked'], 19/37)
                self.assertEqual(profile['expected_spins'], 1)
                self.assertAlmostEqual(profile['mean'], -10/74)


if __name__ == '__main__':unittest.main()
