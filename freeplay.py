"""Manual virtual roulette: legal positions, exact payouts, replay and pending draws."""
from dataclasses import asdict
from hashlib import sha256
import csv
import io
import json
import math
import secrets
import uuid

from engine import Scenario, POSITIONS, EVEN_CHOICES
from practice import pockets


def positions(wheel):
    legal=pockets(wheel)
    result={key:dict(value,numbers=[str(n) for n in value['numbers']],gross=value['multiplier'])
            for key,value in POSITIONS.items() if key not in ('firstfour','trio:012','trio:023') and not key.startswith('split:zero:')}
    def add(key,label,nums,gross):result[key]=dict(label=label,numbers=nums,gross=gross)
    for n in legal:
        if n in ('00','000'):add('straight:'+n,'Straight · '+n,[n],36)
    if wheel in ('single','french'):
        for n in ('1','2','3'):add('split:zero:'+n,'Split · 0/'+n,['0',n],18)
        add('trio:012','Trio · 0/1/2',['0','1','2'],12)
        add('trio:023','Trio · 0/2/3',['0','2','3'],12)
        add('firstfour','First four · 0/1/2/3',['0','1','2','3'],9)
    else:
        # Conventional double-zero area; triple-zero adds a separate zero box.
        for a,b in [('0','00'),('0','1'),('0','2'),('00','2'),('00','3')]:
            add(f'split:zero:{a}:{b}',f'Split · {a}/{b}',[a,b],18)
        for nums in [('0','1','2'),('0','00','2'),('00','2','3')]:
            add('trio:'+':'.join(nums),'Trio · '+'/'.join(nums),list(nums),12)
        if wheel=='double':add('basket','Top line · 0/00/1/2/3',['0','00','1','2','3'],7)
        else:
            add('trio:zeros','Three zeros · 0/00/000',['0','00','000'],12)
            add('topline','Top line · 0/00/000/1/2/3',['0','00','000','1','2','3'],6)
    return result


def bets(s,entries):
    if not isinstance(entries,list):raise ValueError('Invalid wager list.')
    available=positions(s.wheel);totals={}
    for entry in entries:
        key=entry['position'];amount=entry['amount']
        if key not in available:raise ValueError('That betting position is not available on this wheel.')
        if isinstance(amount,bool) or not isinstance(amount,(int,float)) or not math.isfinite(amount) or amount!=int(amount) or amount<s.minimum or amount%s.chip:
            raise ValueError(f'Each position needs at least ${s.minimum:,}, in ${s.chip:,} increments.')
        totals[key]=totals.get(key,0)+int(amount)
    return [dict(position=k,amount=v) for k,v in totals.items()]


def net_result(s,entries,number):
    if number not in pockets(s.wheel):raise ValueError('Invalid winning pocket.')
    available=positions(s.wheel);net=-sum(e['amount'] for e in entries)
    for entry in entries:
        position=available[entry['position']]
        if number in position['numbers']:net+=entry['amount']*position['gross']
        elif s.wheel=='french' and number=='0' and entry['position'] in EVEN_CHOICES:net+=entry['amount']/2
    return net


def stop_reason(s,bank,count):
    if bank>=s.bankroll+s.target:return 'Profit target reached. Start a new free-play session to play again.'
    if count>=s.spins:return 'Spin limit reached.'
    if bank-(s.bankroll-s.loss_limit)<s.minimum:return 'No minimum wager fits the remaining loss allowance.'
    return None


def check_wager(s,entries,bank,count):
    stop=stop_reason(s,bank,count)
    if stop:raise ValueError(stop)
    if not entries:raise ValueError('Add at least one bet before spinning.')
    total=sum(e['amount'] for e in entries)
    if total>s.maximum:raise ValueError(f'Total wager exceeds the ${s.maximum:,} table maximum.')
    if total>bank-(s.bankroll-s.loss_limit):raise ValueError('Reduce the bets: this wager would cross your bankroll or loss limit.')


def token(data):
    return sha256(json.dumps({k:data[k] for k in ('scenario','history','bets')},sort_keys=True).encode()).hexdigest()


def new_game(s):return dict(version=1,scenario=asdict(s),history=[],bets=[],pending=None,last_id=None)


def validate_game(data):
    from freeplay_advisor import validate_advisor
    if not isinstance(data,dict) or data.get('version')!=1:raise ValueError('Unsupported free-play save.')
    s=Scenario(**data['scenario']);history=[];bank=s.bankroll
    if not isinstance(data.get('history'),list) or len(data['history'])>s.spins:raise ValueError('Invalid free-play history.')
    for row in data['history']:
        wager=bets(s,row['bets']);check_wager(s,wager,bank,len(history))
        net=net_result(s,wager,row['number']);bank+=net
        history.append(dict(bets=wager,number=row['number'],net=net,bankroll=bank,profit=bank-s.bankroll))
    cleaned=dict(version=1,scenario=asdict(s),history=history,bets=bets(s,data['bets']),pending=data.get('pending'),last_id=data.get('last_id'))
    cleaned['advisor']=validate_advisor(data.get('advisor'),s,len(history))
    pending=cleaned['pending']
    if pending:
        if not isinstance(pending,dict) or not isinstance(pending.get('id'),str) or pending.get('number') not in pockets(s.wheel) or pending.get('token')!=token(cleaned):raise ValueError('The pending free-play spin does not match its frozen wager.')
        check_wager(s,cleaned['bets'],bank,len(history))
    return cleaned


def status(data):
    s=Scenario(**data['scenario']);history=data['history'];bank=history[-1]['bankroll'] if history else s.bankroll
    problem=None
    try:check_wager(s,data['bets'],bank,len(history))
    except ValueError as exc:problem=str(exc)
    nets=[net_result(s,data['bets'],n) for n in pockets(s.wheel)]
    return dict(bankroll=bank,profit=bank-s.bankroll,left=s.spins-len(history),total=sum(e['amount'] for e in data['bets']),
        problem=problem,stop=stop_reason(s,bank,len(history)),profit_chance=sum(n>0 for n in nets)/len(nets),
        loss_chance=sum(n<0 for n in nets)/len(nets),break_even_chance=sum(n==0 for n in nets)/len(nets),
        payout_chance=sum(n+sum(e['amount'] for e in data['bets'])>0 for n in nets)/len(nets),mean=sum(nets)/len(nets),worst=min(nets))


def edit_bet(data,key=None,amount=None,remove=False,clear=False):
    data=validate_game(data)
    if data['pending']:raise ValueError('Wait for the current spin to finish.')
    entries=list(data['bets'])
    if clear:entries=[]
    elif remove:entries=[e for e in entries if e['position']!=key]
    else:
        s=Scenario(**data['scenario']);addition=bets(s,[dict(position=key,amount=amount)])[0]
        entries=bets(s,entries+[addition]);current=status(data)
        check_wager(s,entries,current['bankroll'],len(data['history']))
    return dict(data,bets=entries)


def begin_game_spin(data,choose=None):
    data=validate_game(data)
    if data['pending']:raise ValueError('Wait for the current spin to finish.')
    s=Scenario(**data['scenario']);current=status(data)
    check_wager(s,data['bets'],current['bankroll'],len(data['history']))
    number=(choose or secrets.choice)(pockets(s.wheel))
    if number not in pockets(s.wheel):raise ValueError('Invalid simulated pocket.')
    return dict(data,pending=dict(id=uuid.uuid4().hex,number=number,token=token(data)))


def finish_game_spin(data,spin_id):
    data=validate_game(data);pending=data['pending']
    if not pending or pending['id']!=spin_id:raise ValueError('This spin is stale or already settled.')
    s=Scenario(**data['scenario']);current=status(data);net=net_result(s,data['bets'],pending['number']);bank=current['bankroll']+net
    row=dict(bets=data['bets'],number=pending['number'],net=net,bankroll=bank,profit=bank-s.bankroll)
    return dict(data,history=data['history']+[row],pending=None,last_id=spin_id)


def undo_game(data):
    data=validate_game(data)
    if data['pending']:raise ValueError('Wait for the current spin to finish.')
    if not data['history']:raise ValueError('No free-play spin to undo.')
    advisor=data.get('advisor')
    if advisor:advisor=dict(advisor,start=min(advisor['start'],len(data['history'])-1))
    return dict(data,history=data['history'][:-1],bets=data['history'][-1]['bets'],last_id=None,advisor=advisor)


def game_csv(data):
    data=validate_game(data);s=Scenario(**data['scenario']);available=positions(s.wheel);output=io.StringIO(newline='')
    fields=['session_mode','outcome_source','wheel','starting_bankroll','target','loss_limit','table_maximum','minimum','chip','spin_limit','spin','bets','total_wager','winning_pocket','net','bankroll','profit']
    writer=csv.DictWriter(output,fieldnames=fields,lineterminator='\n');writer.writeheader()
    for i,row in enumerate(data['history'],1):
        writer.writerow(dict(session_mode='Free play / virtual money',outcome_source='Simulated uniform random pocket',wheel=s.wheel,starting_bankroll=s.bankroll,target=s.target,loss_limit=s.loss_limit,table_maximum=s.maximum,minimum=s.minimum,chip=s.chip,spin_limit=s.spins,spin=i,
            bets='; '.join(f"{e['amount']:.2f} USD on {available[e['position']]['label']}" for e in row['bets']),total_wager=sum(e['amount'] for e in row['bets']),winning_pocket='Pocket '+row['number'],net=f"{row['net']:.2f}",bankroll=f"{row['bankroll']:.2f}",profit=f"{row['profit']:.2f}"))
    return output.getvalue()
