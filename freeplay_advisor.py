"""Optional system guidance for manual wagers, using the actual free-play cash."""
from engine import Scenario, LABELS, EVEN_CHOICES, structure, inspect_policy
from session_tracker import apply_even_choice
from freeplay import positions, bets, check_wager, status, validate_game

SYSTEM_NAMES={**LABELS,'oneshot':'One-shot even-money','even':'Adaptive even-money',
    'dozen':'Adaptive dozen / column','sixline':'Adaptive six-line',
    'groups':'Adaptive equal-group portfolios','research':'Custom optimized betting plan'}


def validate_advisor(value,s,count):
    if value is None:return None
    if not isinstance(value,dict) or value.get('key') not in SYSTEM_NAMES:raise ValueError('Choose a supported suggestion system.')
    key=value['key'];base=value.get('base');start=value.get('start',0);even=value.get('even_bet','red')
    if isinstance(start,bool) or not isinstance(start,int) or not 0<=start<=count:raise ValueError('Invalid suggestion starting spin.')
    if even not in EVEN_CHOICES:raise ValueError('Choose an even-money box.')
    if key in LABELS or key=='oneshot':
        if isinstance(base,bool) or not isinstance(base,(int,float)) or not s.minimum<=base<=s.maximum or base%s.chip:raise ValueError('Invalid system base bet.')
        base=int(base)
    else:base=None
    return dict(key=key,base=base,start=start,even_bet=even)


def choose_advisor(data,key,base=None,even_bet='red'):
    data=validate_game(data)
    if data['pending']:raise ValueError('Wait for the current spin to finish.')
    previous=data.get('advisor')
    start=previous['start'] if previous and previous['key']==key and previous['base']==base else len(data['history'])
    advisor=validate_advisor(dict(key=key,base=base,start=start,even_bet=even_bet),Scenario(**data['scenario']),len(data['history'])) if key else None
    return dict(data,advisor=advisor)


def suggested_bets(data):
    s=Scenario(**data['scenario']);guide=data.get('advisor');current=status(data)
    if not guide:return dict(entries=[],note='Choose a system to see an optional suggestion.',stop=None)
    key=guide['key'];base=guide['base'];even=guide['even_bet'];note=''
    if current['stop']:return dict(entries=[],stop=current['stop'],note='')
    if key in LABELS or key=='oneshot':
        stakes,wi,li=structure('flat' if key=='oneshot' else key,base,s);index=0;matched=0;reset=False
        for row in data['history'][guide['start']:]:
            expected=int(stakes[index])*base
            # Any single even-money box has the same progression and zero rule.
            follows=len(row['bets'])==1 and row['bets'][0]['position'] in EVEN_CHOICES and row['bets'][0]['amount']==expected
            if follows and not (key=='oneshot' and matched):
                index=int(wi[index] if row['net']>0 else li[index]);matched+=1;reset=False
            else:index=0;matched=0;reset=True
        if key=='oneshot' and matched:return dict(entries=[],stop='One-shot complete. Choose another system or start a new game for more suggestions.',note='')
        entries=[dict(position=even,amount=int(stakes[index])*base)]
        note=('Your last manual wager differed from this system. Its progression restarted at the base bet. ' if reset else '')+f'Base bet ${base:,}. Only matching single even-money wagers advance this progression; French half-losses count as losses.'
    else:
        decision=apply_even_choice(inspect_policy(s,key,current['bankroll'],current['left']),even)
        if decision.get('stop'):return dict(entries=[],stop=decision['stop'],note='')
        available=positions(s.wheel);entries=[]
        for entry in decision['entries']:
            numbers={str(n) for n in entry['numbers']}
            position=next((p for p,v in available.items() if set(v['numbers'])==numbers),None)
            if position is None:raise ValueError('This system suggests a position unavailable on this wheel layout.')
            entries.append(dict(position=position,amount=entry['amount']))
        note='Recalculated from your actual free-play bankroll and spins left. This is the best within this system’s tested bets, not a prediction of the next pocket.'
    entries=bets(s,entries)
    try:check_wager(s,entries,current['bankroll'],len(data['history']))
    except ValueError as exc:return dict(entries=[],stop=f'System suggestion stopped: {exc}',note=note)
    return dict(entries=entries,stop=None,note=note)


def load_suggestion(data):
    data=validate_game(data)
    if data['pending']:raise ValueError('Wait for the current spin to finish.')
    suggestion=suggested_bets(data)
    if suggestion['stop'] or not suggestion['entries']:raise ValueError(suggestion['stop'] or suggestion['note'])
    return dict(data,bets=suggestion['entries'])
