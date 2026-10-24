"""One selected system, one explicit recorded payout per spin."""
from engine import (LABELS, Scenario, classic_profile, structure, policy_snapshot,
                    inspect_policy, summarize, policy_loss_stats, POSITIONS, EVEN_CHOICES)

def state_token(data):
    import json
    from hashlib import sha256
    return sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def supports_even_choice(key,decision=None):
    if key in LABELS or key in ('oneshot','even'):return True
    entries=(decision or {}).get('entries',[])
    return len(entries)==1 and any(set(entries[0]['numbers'])==set(POSITIONS[c]['numbers']) for c in EVEN_CHOICES)


def apply_even_choice(decision,choice):
    if choice not in EVEN_CHOICES:raise ValueError('Choose red, black, odd, even, low, or high.')
    if not decision.get('stop') and supports_even_choice('',decision):
        return dict(decision,entries=[dict(decision['entries'][0],numbers=list(POSITIONS[choice]['numbers']))],
                    even_choice_applied=True)
    return dict(decision,even_choice_applied=False)


def snapshot(s,key,base,history,with_stats=True,even_bet='red'):
    if even_bet not in EVEN_CHOICES:raise ValueError('Choose a valid even-money bet.')
    bank=s.bankroll if not history else history[-1]['after'][0]
    left=s.spins if not history else history[-1]['after'][1]
    if key not in LABELS and key!='oneshot':
        if with_stats:return apply_even_choice(policy_snapshot(s,key,bank,left),even_bet)
        return apply_even_choice(dict(**inspect_policy(s,key,bank,left),bankroll=bank,spins_left=left,net_profit=bank-s.bankroll),even_bet)
    index=history[-1]['next_index'] if history else 0
    profit=bank-s.bankroll
    stop=None
    if profit>=s.target:stop='Profit target reached. Session complete.'
    elif left==0:stop='Spin limit reached. Session complete.'
    elif key=='oneshot' and history:stop='One-shot complete. This system ends after one spin.'
    if key=='oneshot':
        stakes,wi,li=structure('flat',base,s)
    else:stakes,wi,li=structure(key,base,s)
    bet=int(stakes[index])*base
    if not stop and (bet>s.maximum or bet>bank-(s.bankroll-s.loss_limit)):
        stop='The next required wager exceeds your table or loss limit. Session complete.'
    if stop:
        return dict(stop=stop,bankroll=bank,spins_left=left,net_profit=profit,
                    stats=summarize({profit:1.},s,0,0,expected_loss=-profit) if with_stats else None)
    outcomes=[dict(net=bet,probability=s.p,bankroll=bank+bet,next_index=int(wi[index])),
              dict(net=-bet,probability=18/37 if s.wheel=='french' else 1-s.p,bankroll=bank-bet,next_index=int(li[index]))]
    if s.wheel=='french':
        outcomes.append(dict(net=-bet/2,probability=1/37,bankroll=bank-bet/2,next_index=int(li[index]),label='Zero · half-loss'))
    if not with_stats:stats=None
    elif key=='oneshot':
        stats=summarize({profit+o['net']:o['probability'] for o in outcomes},s,1,bet,expected_loss=s.even_edge*bet-profit)
    else:stats=classic_profile(s,key,base,start_profit=profit,start_index=index,spins_left=left)
    return dict(bankroll=bank,spins_left=left,net_profit=profit,total=bet,
                entries=[dict(numbers=list(POSITIONS[even_bet]['numbers']),amount=bet)],outcomes=outcomes,stats=stats,even_choice_applied=True)

def record(s,key,base,history,index,even_bet='red'):
    current=snapshot(s,key,base,history,with_stats=False,even_bet=even_bet)
    if current.get('stop'):raise ValueError(current['stop'])
    if isinstance(index,bool) or not isinstance(index,int) or not 0<=index<len(current['outcomes']):
        raise ValueError('Choose a displayed result.')
    outcome=current['outcomes'][index]
    return list(history)+[dict(before=[current['bankroll'],current['spins_left']],
          after=[outcome['bankroll'],current['spins_left']-1],net=outcome['net'],
          next_index=outcome.get('next_index',0),outcome_index=index,even_bet=even_bet,
          bets=[dict(numbers=list(b['numbers']),amount=b['amount']) for b in current['entries']],total_wager=current['total'],
          loss_probability=sum(o['probability'] for o in current['outcomes'] if o['net']<0))]

def record_number(s,key,base,history,number,even_bet='red'):
    """Settle the displayed numbered positions, including all overlapping returns."""
    number=str(number).strip()
    legal=[str(n) for n in range(37)]
    if s.wheel in ('double','triple'):legal.append('00')
    if s.wheel=='triple':legal.append('000')
    if number not in legal:
        raise ValueError('Enter 0–36'+(', 00, or 000.' if s.wheel=='triple' else ', or 00.' if s.wheel=='double' else '.'))
    current=snapshot(s,key,base,history,with_stats=False,even_bet=even_bet)
    if current.get('stop'):raise ValueError(current['stop'])
    net=-current['total']
    for entry in current['entries']:
        numbers=entry['numbers'];amount=entry['amount']
        if number not in ('00','000') and int(number) in numbers:
            net+=amount*(36//len(numbers))
        if s.wheel=='french' and number=='0' and len(numbers)==18:
            net+=amount/2
    index=next((i for i,o in enumerate(current['outcomes']) if abs(o['net']-net)<1e-9),None)
    if index is None:raise ArithmeticError('The numbered payout does not match the policy outcomes.')
    result=record(s,key,base,history,index,even_bet=even_bet)
    result[-1]['winning_number']=number
    return result


def validate_saved_session(data):
    """Replay saved results before resuming; reject malformed or inconsistent data."""
    from dataclasses import asdict
    from hashlib import sha256
    import json
    if not isinstance(data,dict) or data.get('version')!=1:
        raise ValueError('Saved session format is not supported.')
    s=Scenario(**data['scenario']);key=data['key'];base=data['base']
    if data.get('even_bet','red') not in EVEN_CHOICES:raise ValueError('Saved even-money choice is invalid.')
    if key not in set(LABELS)|{'oneshot','research','even','dozen','sixline','groups'}:
        raise ValueError('Saved system is not supported.')
    expected=sha256(json.dumps(asdict(s),sort_keys=True).encode()).hexdigest()[:12]
    if data.get('calculation')!=expected:raise ValueError('Saved settings do not match the session.')
    if key in LABELS or key=='oneshot':
        if isinstance(base,bool) or not isinstance(base,(int,float)) or not s.minimum<=base<=s.maximum or base%s.chip:
            raise ValueError('Saved base bet is invalid.')
    history=data.get('history')
    if not isinstance(history,list) or len(history)>s.spins:
        raise ValueError('Saved history exceeds the spin limit.')
    replay=[]
    for entry in history:
        if 'winning_number' in entry:
            replay=record_number(s,key,base,replay,entry['winning_number'],even_bet=entry.get('even_bet','red'))
        else:replay=record(s,key,base,replay,entry['outcome_index'],even_bet=entry.get('even_bet','red'))
        for field in ('before','after','net','next_index','loss_probability','bets','total_wager','even_bet'):
            if field in ('bets','total_wager','even_bet') and field not in entry:continue
            if entry.get(field)!=replay[-1][field]:
                raise ValueError('Saved results are inconsistent; this session cannot be resumed.')
    return dict(data,history=replay,even_bet=data.get('even_bet','red'))


def session_log(s,key,base,history):
    """Reconstruct the exact suggested wagers before each recorded result."""
    from guides import position_name
    rows=[]
    prefix=[]
    for spin,entry in enumerate(history,1):
        decision=snapshot(s,key,base,prefix,with_stats=False,even_bet=entry.get('even_bet','red'))
        if decision.get('stop'):
            raise ValueError('Session history contains a spin after its stopping point.')
        bets=[dict(position=position_name(bet['numbers']),amount=bet['amount'],
                   numbers=list(bet['numbers'])) for bet in entry.get('bets',decision['entries'])]
        number=entry.get('winning_number')
        rows.append(dict(spin=spin,bets=bets,total_wager=entry.get('total_wager',decision['total']),
            entry_method='Winning number' if number is not None else 'Result button',
            even_money_choice=EVEN_CHOICES[entry.get('even_bet','red')] if decision.get('even_choice_applied') else '',
            winning_number=number,result='Win' if entry['net']>0 else 'Loss' if entry['net']<0 else 'Break even',
            net=entry['net'],bankroll=entry['after'][0],
            profit=entry['after'][0]-s.bankroll,spins_left=entry['after'][1]))
        prefix.append(entry)
    return rows


def session_log_csv(data):
    """Self-contained CSV with numeric money columns and explicit zero-pocket labels."""
    import csv
    import io
    from engine import WHEELS
    data=validate_saved_session(data)
    s=Scenario(**data['scenario'])
    names={**LABELS,'oneshot':'One-shot even-money','even':'Adaptive even-money',
           'dozen':'Adaptive dozen / column','sixline':'Adaptive six-line',
           'groups':'Adaptive equal-group portfolios','research':'Custom optimized betting plan'}
    fields=['spin','system','wheel','even_money_choice','bets','total_wager','entry_method','winning_pocket','result',
            'spin_net','bankroll_after','session_profit','spins_remaining','starting_bankroll',
            'profit_target','loss_limit','minimum_bet','maximum_total_wager','chip_size','spin_limit',
            'base_bet','calculation_id']
    output=io.StringIO(newline='')
    writer=csv.DictWriter(output,fieldnames=fields,lineterminator='\n')
    writer.writeheader()
    for row in session_log(s,data['key'],data['base'],data['history']):
        writer.writerow(dict(spin=row['spin'],system=names[data['key']],wheel=WHEELS[s.wheel],even_money_choice=row['even_money_choice'],
            bets='; '.join(f"{bet['position']}: USD {bet['amount']:.2f}" for bet in row['bets']),
            total_wager=f"{row['total_wager']:.2f}",entry_method=row['entry_method'],
            winning_pocket='Not entered' if row['winning_number'] is None else 'Pocket '+row['winning_number'],
            result=row['result'],spin_net=f"{row['net']:.2f}",bankroll_after=f"{row['bankroll']:.2f}",
            session_profit=f"{row['profit']:.2f}",spins_remaining=row['spins_left'],
            starting_bankroll=s.bankroll,profit_target=s.target,loss_limit=s.loss_limit,
            minimum_bet=s.minimum,maximum_total_wager=s.maximum,chip_size=s.chip,spin_limit=s.spins,
            base_bet='' if data['base'] is None else data['base'],calculation_id=data['calculation']))
    return output.getvalue()
