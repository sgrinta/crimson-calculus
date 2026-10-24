"""Plain-language instructions tied to actual calculator rules and current settings."""
from engine import LABELS, RULES, POSITIONS, inspect_policy, EVEN_CHOICES
from system_education import SYSTEMS

DESCRIPTIONS = {key:info['how'] for key,info in SYSTEMS.items()}


def position_name(numbers):
    wanted=frozenset(numbers)
    return next((p['label'] for p in POSITIONS.values() if frozenset(p['numbers'])==wanted),'Numbers '+', '.join(map(str,numbers)))


def placement_instruction(numbers):
    size=len(numbers)
    if size==1:return f"Put the entire stake on the square marked {numbers[0]}."
    if size==2:return "Put one stake on the dividing line between these two numbers."
    if size==3:return "Use the trio junction touching these three numbers." if 0 in numbers else "Put one stake on the outside end of this row of three numbers."
    if size==4:return "Use the first-four position touching 0, 1, 2 and 3." if 0 in numbers else "Put one stake on the intersection where these four number squares meet."
    if size==6:return "Put one stake on the shared outside edge between these two rows of three."
    if size==12:return "Put one stake in the matching column box at the bottom of the table." if numbers[1]-numbers[0]==3 else "Put one stake in the matching 1st 12, 2nd 12 or 3rd 12 box."
    for key in EVEN_CHOICES:
        if set(numbers)==set(POSITIONS[key]['numbers']):
            return "Put one stake in the outside box marked "+{"low":"1–18","high":"19–36"}.get(key,key.upper())+"."
    return "Place the stake on the listed position."


def guide(row,s,even_bet='red'):
    key=row['key'];base=row['base']
    data=dict(title=row['label'],summary=DESCRIPTIONS[key],steps=[],example=[],placement='',glossary=[],opening=[])
    stop=f"Stop once total net profit reaches at least ${s.target:,}, after {s.spins} spins, or before a wager would exceed the ${s.maximum:,} table maximum or your ${s.loss_limit:,} loss limit. Do not shrink a prescribed wager to keep playing."
    if key in LABELS or key=='oneshot':
        data['placement']='Use an even-money outside bet, such as the box marked RED. Put the whole wager on that one box. A win earns the wager amount as net profit; a loss costs the wager. Zero loses.'
        data['opening']=[dict(label='Red · even-money outside box',amount=base,placement='Put the entire stake in the box marked RED.')]
        data['steps']=[f"Start with ${base:,} on red. This amount is your base bet: one unit."]
        instructions={
            'martingale':['After a loss, double the amount you just wagered.','After a win, return to the base bet and start a new recovery cycle.'],
            'grand_martingale':[f'After a loss, double the amount you just wagered and add another ${base:,}.','After a win, return to the base bet.'],
            'flat':[f'After either a win or loss, wager ${base:,} again if the session has not ended.'],
            'dalembert':[f'After a loss, add ${base:,} to the next wager.',f'After a win, subtract ${base:,}, but never go below ${base:,}.'],
            'reverse_dalembert':[f'After a win, add ${base:,} to the next wager.',f'After a loss, subtract ${base:,}, but never go below ${base:,}.'],
            'fibonacci':['Use the sequence 1, 1, 2, 3, 5, 8, 13… and multiply the current number by your base bet. Begin at the FIRST 1.','After a loss, move one place to the right. After a win, move two places to the left, stopping at the first 1 if necessary.'],
            'paroli':['After the first win, bet twice the base. After a second consecutive win, bet four times the base.','After the third consecutive win, return to the base. After any loss, return to the base immediately.'],
            '1326':['After consecutive wins, wager 1, then 3, then 2, then 6 base units.','After the fourth win, restart at 1 unit. After any loss, restart at 1 unit.'],
            'oneshot':['After that single spin settles, stop immediately—even if you lost. This is different from repeatedly betting the same amount.'],
        }
        data['steps']+=instructions[key]
        sequences={'martingale':([1,2,4,8],'after consecutive losses'),'grand_martingale':([1,3,7,15],'after consecutive losses'),
            'flat':([1,1,1,1],'regardless of wins or losses'),'dalembert':([1,2,3,4],'after consecutive losses'),
            'reverse_dalembert':([1,2,3,4],'after consecutive wins'),'fibonacci':([1,1,2,3,5],'after consecutive losses'),
            'paroli':([1,2,4,1],'after consecutive wins'),'1326':([1,3,2,6,1],'after consecutive wins')}
        if key in sequences:
            units,when=sequences[key]
            data['example']=[f"Example {when}: "+' → '.join(f'${base*u:,}' for u in units)+'.', 'This illustrates the rule only. Stop earlier if a required wager is blocked or any session limit is reached.']
        data['stop']='Stop after one settled spin, or do not start if its wager violates a limit.' if key=='oneshot' else stop
    else:
        lookup=inspect_policy(s,key,s.bankroll,s.spins)
        entries=lookup.get('entries',[])
        if len(entries)==1 and any(set(entries[0]['numbers'])==set(POSITIONS[c]['numbers']) for c in EVEN_CHOICES):
            lookup['entries']=[dict(entries[0],numbers=list(POSITIONS[even_bet]['numbers']))]
        data['opening']=[dict(label=position_name(e['numbers']),amount=e['amount'],placement=placement_instruction(e['numbers'])) for e in lookup.get('entries',[])]
        data['placement']={
            'sixline':'A six-line bet covers two adjacent rows of three numbers—for example 1, 2, 3 and 4, 5, 6. Place ONE wager on the shared outside edge between those rows. Do not put the displayed amount on each individual number. It pays 5:1 net profit when any of the six numbers wins.',
            'dozen':'Use a box marked 1st 12 (1–12), 2nd 12 (13–24), or 3rd 12 (25–36). A column bet also covers 12 numbers and has the same probability and 2:1 net payout. Put one wager on the selected box.',
            'even':'Use an even-money outside box such as RED. A win earns the stake as net profit; a loss costs the stake. Zero loses.',
            'groups':'Place the displayed amount on EACH listed position. A position can cover multiple numbers with a single wager; do not repeat that stake on each covered number. All listed stakes together form one spin’s portfolio.',
            'research':'Place the displayed amount on EACH listed position. Some positions overlap: a number can win more than one bet. Add all returns, then subtract the total wager to get the spin’s net result.',
        }[key]
        data['steps']=['Use the starting wager or wagers shown above for the current scenario.',
            'After the spin settles, use the result buttons in “Follow the next step”. Choose the actual net payout; the tracker updates bankroll and subtracts one remaining spin.',
            'Select this system in the system list and follow its newly displayed bets after each recorded result. Use Undo to correct a mistaken result.',
            'Repeat the lookup after EVERY spin, including wins. Do not automatically double, reset, or reuse the old amount.']
        data['glossary']=[('Adaptive','The next stake—and for mixed portfolios, the bet type—depends on your remaining bankroll and spins.'),('Policy','The calculator’s lookup plan: which wagers to use in each situation.')]
        data['stop']=stop.replace('Do not shrink a prescribed wager to keep playing.','End the session if the policy lookup says no legal wager remains.')
        if key=='research':data['example'].append('This stored research plan is available only for the original $1,000 / $200 / $5-chip scenario and its original limits. It is the best tested plan, not a proven global optimum.')
        else:data['example'].append('The calculator searches this permitted bet family. It does not claim that this family is best among every possible roulette layout.')
    data['example'].append('A higher chance of reaching the target does not remove the possibility of large losses. Average results remain negative on standard roulette.')
    if key in LABELS or key in ('oneshot','even'):
        selected=EVEN_CHOICES[even_bet]
        data['placement']='Choose any ONE even-money bet: red, black, odd, even, low (1–18), or high (19–36). Your selected bet is '+selected+'. A win earns the stake as profit; a full loss loses the stake. Zero loses.'
        if data['opening']:
            data['opening'][0]['label']=selected+' · even-money bet'
            data['opening'][0]['placement']=placement_instruction(POSITIONS[even_bet]['numbers'])
        if key in LABELS or key=='oneshot':
            data['steps'][0]=f"Start with ${base:,} on {selected}. This is your base bet: one unit."
    if s.wheel=='french':
        if key in LABELS or key in ('oneshot','even'):
            data['placement']=data['placement'].replace('Zero loses.','On zero, half the stake is returned and half is lost.')
            data['placement']=data['placement'].replace('a loss costs the wager. Zero loses.','a nonzero loss costs the wager. On zero, half the stake is returned and half is lost.').replace('A loss costs the wager. Zero loses.','A nonzero loss costs the wager. On zero, half the stake is returned and half is lost.').replace('a loss costs the stake. Zero loses.','a nonzero loss costs the stake. On zero, half the stake is returned and half is lost.')
        data['example'].insert(0,'French rule: La Partage applies only to even-money positions. Zero is a half-loss and advances a named progression as a loss. Wagers still use whole chips; fractional refunds remain in your cash balance. En Prison is not modeled.')
    elif s.wheel=='triple':
        data['example'].insert(0,'Triple-zero rule: the wheel has 39 pockets. 0, 00 and 000 all fully lose even-money wagers; standard payouts do not increase.')
    return data
