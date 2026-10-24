"""Read-only, replay-validated session snapshots for Vivienne's current request."""
from dataclasses import asdict
from datetime import datetime, timezone

from engine import Scenario
from freeplay import validate_game, status, positions
from freeplay_advisor import SYSTEM_NAMES
from guides import position_name
from practice import validate_practice
from session_tracker import validate_saved_session, snapshot, session_log

SOURCES = ('tracked', 'practice', 'free_play')
SOURCE_LABELS = {'tracked': 'Step 3 session log', 'practice': 'System practice / virtual money',
                 'free_play': 'Free play / virtual money'}


def _results(rows, starting_bankroll):
    peak = starting_bankroll
    drawdown = 0
    streak = 0
    for row in rows:
        peak = max(peak, row['bankroll'])
        drawdown = max(drawdown, peak - row['bankroll'])
        streak = streak + 1 if row['net'] < 0 else 0
    return dict(wins=sum(r['net'] > 0 for r in rows), losses=sum(r['net'] < 0 for r in rows),
                break_even=sum(r['net'] == 0 for r in rows), current_losing_streak=streak,
                maximum_drawdown=drawdown)


def _system_session(data):
    s = Scenario(**data['scenario'])
    current = snapshot(s, data['key'], data['base'], data['history'], even_bet=data['even_bet'])
    rows = session_log(s, data['key'], data['base'], data['history'])
    next_bets = [dict(position=position_name(b['numbers']), amount=b['amount']) for b in current.get('entries', [])]
    summary = dict(system=SYSTEM_NAMES[data['key']], base_bet=data['base'],
                   even_money_choice=data['even_bet'], bankroll=current['bankroll'],
                   profit=current['net_profit'], spins_left=current['spins_left'], stop=current.get('stop'),
                   remaining_session_success=current['stats']['success'], next_total_wager=current.get('total', 0))
    # Only explicitly selected fields enter the model context; saved extras never do.
    rows = [{k: row[k] for k in ('spin', 'bets', 'total_wager', 'entry_method', 'winning_number',
                                 'result', 'net', 'bankroll', 'profit', 'spins_left')} for row in rows]
    for row in rows:
        row['bets'] = [{k: b[k] for k in ('position', 'amount')} for b in row['bets']]
    return s, summary, rows, next_bets


def _free_session(data):
    s = Scenario(**data['scenario'])
    current = status(data)
    available = positions(s.wheel)
    def named(entries):
        return [dict(position=available[b['position']]['label'], amount=b['amount']) for b in entries]
    rows = [dict(spin=i, bets=named(row['bets']), total_wager=sum(b['amount'] for b in row['bets']),
                 entry_method='Simulated winning number', winning_number=row['number'],
                 result='Win' if row['net'] > 0 else 'Loss' if row['net'] < 0 else 'Break even',
                 net=row['net'], bankroll=row['bankroll'], profit=row['profit'], spins_left=s.spins-i)
            for i, row in enumerate(data['history'], 1)]
    advisor = data.get('advisor')
    summary = dict(system='Manual bets', optional_suggestion_system=SYSTEM_NAMES[advisor['key']] if advisor else None,
                   bankroll=current['bankroll'], profit=current['profit'], spins_left=current['left'],
                   stop=current['stop'], current_bet_problem=current['problem'],
                   remaining_session_success=None,
                   probability_note='Session success is not calculated for freely changing future bets.',
                   next_total_wager=current['total'], next_spin_profit_probability=current['profit_chance'])
    return s, summary, rows, named(data['bets'])


def build_session_context(tracked=None, practice=None, free_play=None, view=None, practice_mode=None):
    """Capture settled results using each save's own scenario; never include pending pockets."""
    result = dict(summary=dict(captured_at=datetime.now(timezone.utc).isoformat(),
                               active_view=view if view in ('settings', 'systems', 'track', 'practice', 'tools') else None,
                               practice_mode=practice_mode if practice_mode in ('system', 'free') else None,
                               sources={}), logs={}, next_bets={})
    for source, raw in zip(SOURCES, (tracked, practice, free_play)):
        summary = dict(label=SOURCE_LABELS[source], status='not_started')
        result['summary']['sources'][source] = summary
        if raw is None:
            continue
        try:
            if source == 'free_play':
                data = validate_game(raw)
                s, details, rows, next_bets = _free_session(data)
            else:
                data = validate_saved_session(raw) if source == 'tracked' else validate_practice(raw)['session']
                s, details, rows, next_bets = _system_session(data)
            summary.update(status='available', scenario=asdict(s), recorded_spins=len(rows), **details,
                           results=_results(rows, s.bankroll), next_bet_positions=len(next_bets),
                           spin_in_progress=bool(raw.get('pending')) if source != 'tracked' else False)
            result['logs'][source] = rows
            result['next_bets'][source] = next_bets
        except (ValueError, TypeError, KeyError, IndexError, ArithmeticError, OverflowError):
            summary.update(status='invalid', note='Saved session could not be validated and was excluded.')
    return result


def read_session_log(context, source, start_spin, limit, bet_offset):
    """Bounded pages expose every settled spin and bet without flooding the model context."""
    if source not in SOURCES:
        raise ValueError('Choose tracked, practice, or free_play.')
    for value, low, high in ((start_spin, 0, 500), (limit, 1, 3), (bet_offset, 0, 500)):
        if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
            raise ValueError('Use start_spin 0–500, limit 1–3, and bet_offset 0–500.')
    if context is None:
        return dict(source=source, status='sharing_off', note='Session sharing is off. No logs are available.')
    summary = context['summary']['sources'][source]
    if summary['status'] != 'available':
        return dict(source=source, **summary)
    rows = context['logs'][source]
    selected = ([dict(spin=0, status='Current wager, not a settled spin', bets=context['next_bets'][source])]
                if start_spin == 0 else rows[start_spin-1:start_spin-1+limit])
    page = []
    for row in selected:
        entries = row['bets']
        page.append(dict(row, bets=entries[bet_offset:bet_offset+6], bet_count=len(entries),
                         next_bet_offset=bet_offset+6 if bet_offset+6 < len(entries) else None))
    return dict(source=source, status='available', total_spins=len(rows), rows=page,
                next_spin=start_spin+len(selected) if start_spin > 0 and start_spin+len(selected) <= len(rows) else None,
                note='Read-only snapshot captured when this AI request began. Spin 0 is the current wager; pending outcomes are hidden.')
