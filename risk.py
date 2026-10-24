"""Plain-language system risks, grounded in the selected scenario's calculations."""
from engine import LABELS, structure
from session_tracker import snapshot

PROFILES = {
 'martingale':('Recovery escalation',
    'Completed recovery cycles often produce small gains, while a failed cycle can lose much more. This does not mean most individual spins win.',
    'The next wager doubles after a loss. A short losing run can make the required wager exceed the table maximum or your remaining loss allowance.'),
 'grand_martingale':('Faster recovery escalation',
    'Many completed recovery cycles can be followed by one much larger failed cycle. Individual spins still have the wheel’s normal odds.',
    'After a loss, the next wager doubles and adds another base unit, so it grows faster than ordinary Martingale. It can become unaffordable quickly.'),
 'flat':('Fixed stake',
    'The wager stays the same. Small stakes may need many spins to reach the target; larger stakes create larger bankroll swings. Losing runs still occur.',
    'There is no stake escalation, but play stops if the fixed wager cannot fit your remaining loss allowance or if a session limit is reached.'),
 'dalembert':('Gradual loss escalation',
    'Wagers rise gradually after losses and fall after wins. Recovery may take several wins; a win does not necessarily recover earlier losses.',
    'Adding one base unit after each loss can eventually make the next wager exceed the table maximum or remaining loss allowance.'),
 'reverse_dalembert':('Win escalation',
    'Wagers rise after wins and fall after losses. A loss at a raised stake can give back earlier gains; smaller later bets may take time to recover it.',
    'A stake increased after wins must still fit the table maximum and remaining loss allowance. The app stops rather than capping it.'),
 'fibonacci':('Growing recovery sequence',
    'Losses move the plan up the 1, 1, 2, 3, 5… sequence. One win moves back two steps and may still leave a session loss.',
    'The early increases look modest, but later Fibonacci wagers grow large. A required step may be blocked while cash remains.'),
 'paroli':('Win progression',
    'The plan seeks three consecutive wins and raises the stake during that run. A loss can give back earlier wins in the sequence; repeated failed cycles reduce the bankroll.',
    'It resets after a loss, but a doubled or quadrupled wager after wins must still fit the table maximum and remaining loss allowance.'),
 '1326':('Four-step win progression',
    'The 1–3–2–6 sequence tries to build on consecutive wins. A loss can erase earlier gains or end a cycle at a loss; completing the sequence is not guaranteed.',
    'The larger steps after wins may be blocked by the table maximum or remaining loss allowance. A loss resets the sequence.'),
 'oneshot':('One spin only',
    'There is one even-money wager. A losing result is common, and the full stake is at risk except for an eligible French zero half-refund.',
    'This system intentionally stops after one settled spin, even with most of the bankroll left. It does not retry after a loss.'),
 'even':('Changing even-money stakes',
    'Each wager covers 18 numbers, but the amount changes with bankroll and spins left. Several losses in a row remain possible; stakes may be large.',
    'The plan seeks the target within its allowed bets. It stops when no legal wager remains, or when the target or spin limit ends the session.'),
 'dozen':('Less frequent, larger payouts',
    'One dozen or column covers 12 numbers and pays 2:1 net. A loss is more likely than a win on each spin, so losing runs can be common.',
    'The stake changes after results. A remaining balance can be too small to fund a legal wager without touching the protected reserve.'),
 'sixline':('Long losing runs possible',
    'One six-line covers only six numbers and pays 5:1 net. Most spins miss it, so repeated losses can be normal even when the session target probability is high.',
    'The stake changes with the session state. Play stops if no legal wager fits the remaining loss allowance, or a session limit is reached.'),
 'groups':('Variable coverage and payouts',
    'The plan can switch between broad coverage and less frequent larger payouts. Losing-run risk changes with the actual combination; it does not aim for steady wins.',
    'Each position must meet the minimum and chip rules, and the combined wager must fit the table maximum and remaining loss allowance.'),
 'research':('Variable combinations; longshots possible',
    'This app-generated plan can choose low-probability bets or overlapping combinations. Many losing spins can precede an occasional larger payout.',
    'It maximizes target-reaching probability among tested combinations, not frequent wins or bankroll preservation. It stops if no legal prescribed wager remains.'),
}


def full_loss_example(s,key,base):
    """One possible full-loss path, not all paths or a streak-frequency estimate."""
    if key not in LABELS and key!='oneshot':return None
    name='flat' if key=='oneshot' else key
    stakes,_,lose=structure(name,base,s)
    bank=s.bankroll
    reserve=s.bankroll-s.loss_limit
    index=0
    count=0
    while count<s.spins:
        wager=int(stakes[index])*base
        available=bank-reserve
        reasons=[]
        if wager>s.maximum:reasons.append('table maximum')
        if wager>available:reasons.append('remaining loss allowance')
        if reasons:
            return dict(losses=count,bankroll=bank,available=available,reserve=reserve,
                        required=wager,reasons=reasons,stop='blocked')
        bank-=wager
        count+=1
        index=int(lose[index])
        if key=='oneshot':
            return dict(losses=count,bankroll=bank,stop='one-shot')
    return dict(losses=count,bankroll=bank,stop='spin limit')


def risk_profile(s,row):
    kind,pattern,stakes=PROFILES[row['key']]
    opening=snapshot(s,row['key'],row['base'],[],with_stats=False)
    outcomes=opening.get('outcomes',[])
    return dict(kind=kind,pattern=pattern,stakes=stakes,
        opening_win=sum(o['probability'] for o in outcomes if o['net']>0),
        opening_loss=sum(o['probability'] for o in outcomes if o['net']<0),
        opening_even=sum(o['probability'] for o in outcomes if o['net']==0),
        example=full_loss_example(s,row['key'],row['base']))
