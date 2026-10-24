"""Independent virtual-money roulette sessions; all payouts reuse the calculator."""
from dataclasses import asdict
from hashlib import sha256
import csv
import io
import json
import math
import secrets
import uuid

from engine import Scenario, POSITIONS
from session_tracker import snapshot, record_number, validate_saved_session, state_token, session_log_csv

EUROPEAN = '0 32 15 19 4 21 2 25 17 34 6 27 13 36 11 30 8 23 10 5 24 16 33 1 20 14 31 9 22 18 29 7 28 12 35 3 26'.split()
AMERICAN = '0 28 9 26 30 11 7 20 32 17 5 22 34 15 3 24 36 13 1 00 27 10 25 29 12 8 19 31 18 6 21 33 16 4 23 35 14 2'.split()
# An illustrative triple-zero order; physical 000 wheels need not use this layout.
TRIPLE = EUROPEAN[:13]+['00']+EUROPEAN[13:25]+['000']+EUROPEAN[25:]
WHEEL_ORDERS = {'single':EUROPEAN,'french':EUROPEAN,'double':AMERICAN,'triple':TRIPLE}


def pockets(wheel):
    if wheel not in WHEEL_ORDERS:raise ValueError('Choose a supported wheel.')
    return list(WHEEL_ORDERS[wheel])


def pocket_color(number):
    if str(number) in ('0','00','000'):return 'zero'
    return 'red' if int(number) in POSITIONS['red']['numbers'] else 'black'


def new_practice(s,key,base,even_bet='red'):
    config=asdict(s)
    session=dict(version=1,key=key,base=base,scenario=config,history=[],even_bet=even_bet,
        calculation=sha256(json.dumps(config,sort_keys=True).encode()).hexdigest()[:12])
    session=validate_saved_session(session)
    snapshot(s,key,base,[],with_stats=False,even_bet=even_bet)  # Check supported policy.
    return dict(version=1,session=session,pending=None,last_id=None)


def validate_practice(data):
    if not isinstance(data,dict) or data.get('version')!=1:raise ValueError('Unsupported practice save.')
    session=validate_saved_session(data['session'])
    # Practice spins always settle a sampled pocket. A tracked-session result
    # button has enough data for a cash replay, but cannot supply the pocket
    # required by the practice wheel, log, and export.
    if any('winning_number' not in row for row in session['history']):
        raise ValueError('Each saved practice spin must include its winning pocket.')
    pending=data.get('pending')
    if pending:
        if not isinstance(pending,dict) or not isinstance(pending.get('id'),str) or not pending['id'] or pending.get('number') not in pockets(session['scenario']['wheel']):
            raise ValueError('Invalid pending practice spin.')
        if pending.get('token')!=state_token(session):raise ValueError('The pending practice wager does not match this session.')
        s=Scenario(**session['scenario'])
        current=snapshot(s,session['key'],session['base'],session['history'],with_stats=False,even_bet=session['even_bet'])
        if current.get('stop'):raise ValueError('A completed practice session cannot have a pending spin. '+current['stop'])
    return dict(data,session=session)


def begin_spin(data,choose=None):
    data=validate_practice(data)
    if data.get('pending'):raise ValueError('Finish the current spin first.')
    session=data['session'];s=Scenario(**session['scenario'])
    current=snapshot(s,session['key'],session['base'],session['history'],with_stats=False,even_bet=session['even_bet'])
    if current.get('stop'):raise ValueError(current['stop'])
    # secrets.choice selects each pocket uniformly, independently of strategy/history.
    number=(choose or secrets.choice)(pockets(s.wheel))
    if number not in pockets(s.wheel):raise ValueError('The simulated pocket is not legal for this wheel.')
    return dict(data,pending=dict(id=uuid.uuid4().hex,number=number,token=state_token(session)))


def finish_spin(data,spin_id):
    data=validate_practice(data)
    pending=data.get('pending')
    if not pending or pending['id']!=spin_id:raise ValueError('This practice spin has already settled or is stale.')
    session=data['session'];s=Scenario(**session['scenario'])
    history=record_number(s,session['key'],session['base'],session['history'],pending['number'],even_bet=session['even_bet'])
    return dict(data,session=dict(session,history=history),pending=None,last_id=pending['id'])


def undo_practice(data):
    data=validate_practice(data)
    if data.get('pending'):raise ValueError('Finish the current spin before using Undo.')
    session=data['session']
    if not session['history']:raise ValueError('No practice spin to undo.')
    history=list(session['history']);removed=history.pop()
    return dict(data,session=dict(session,history=history,even_bet=removed.get('even_bet','red')),last_id=None)


def practice_csv(data):
    data=validate_practice(data)
    reader=csv.DictReader(io.StringIO(session_log_csv(data['session'])))
    output=io.StringIO(newline='')
    writer=csv.DictWriter(output,fieldnames=['session_mode','outcome_source']+reader.fieldnames,lineterminator='\n')
    writer.writeheader()
    for row in reader:
        writer.writerow(dict(row,session_mode='Practice / virtual money',outcome_source='Simulated uniform random pocket'))
    return output.getvalue()


def wheel_svg(wheel):
    """Code-native wheel art, with pocket 0 centered under the fixed top pointer."""
    order=pockets(wheel);step=360/len(order)
    def point(radius,angle):
        rad=math.radians(angle-90)
        return (300+radius*math.cos(rad),300+radius*math.sin(rad))
    parts=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 600" role="img" aria-label="Roulette wheel">',
           '<defs><radialGradient id="felt"><stop stop-color="#151515"/><stop offset="1" stop-color="#020202"/></radialGradient></defs>',
           '<circle cx="300" cy="300" r="296" fill="#030303" stroke="#ded2be" stroke-width="8"/>',
           '<circle cx="300" cy="300" r="280" fill="#ded2be"/>']
    for i,number in enumerate(order):
        a,b=i*step-step/2,i*step+step/2
        p1,p2,p3,p4=point(273,a),point(273,b),point(197,b),point(197,a)
        color=pocket_color(number);fill={'red':'#a12433','black':'#030303','zero':'#efe5d6'}[color]
        path=f'M {p1[0]:.3f} {p1[1]:.3f} A 273 273 0 0 1 {p2[0]:.3f} {p2[1]:.3f} L {p3[0]:.3f} {p3[1]:.3f} A 197 197 0 0 0 {p4[0]:.3f} {p4[1]:.3f} Z'
        x,y=point(242,i*step)
        parts.append(f'<path d="{path}" fill="{fill}" stroke="#d8cbbb" stroke-width="1"/>')
        parts.append(f'<text x="{x:.3f}" y="{y:.3f}" text-anchor="middle" dominant-baseline="central" fill="{"#030303" if color=="zero" else "#f5ecde"}" font-family="Arial,sans-serif" font-size="{15 if number=="000" else 19}" font-weight="700" transform="rotate({i*step} {x:.3f} {y:.3f})">{number}</text>')
    parts.extend(['<circle cx="300" cy="300" r="193" fill="url(#felt)" stroke="#ded2be" stroke-width="4"/>',
                  '<circle cx="300" cy="300" r="181" fill="none" stroke="#74615e" stroke-width="1"/><circle cx="300" cy="300" r="165" fill="none" stroke="#b8a99b" stroke-width="1"/>',
                  '<path d="M300 161V439 M161 300H439" stroke="#b8a99b" stroke-width="2"/>',
                  '<circle cx="300" cy="300" r="47" fill="#8f2039" stroke="#ded2be" stroke-width="3"/>',
                  '<circle cx="300" cy="300" r="17" fill="#ded2be" stroke="#030303" stroke-width="3"/>','</svg>'])
    return ''.join(parts)
