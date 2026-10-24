"""Dash UI for the separate practice wheel, with no model or real-betting tools."""
from dash import Input, Output, State, dcc, html, ctx, no_update
from dash.exceptions import PreventUpdate
from engine import Scenario, WHEELS, EVEN_CHOICES, LABELS, policy_loss_stats
from guides import position_name, placement_instruction
from system_education import SYSTEMS
from session_tracker import snapshot, supports_even_choice, session_log
from practice import (new_practice,validate_practice,begin_spin,finish_spin,undo_practice,
                      practice_csv,pockets,pocket_color)


def money(value):return f'−${abs(value):,.2f}' if value<0 else f'${value:,.2f}'

def stat(label,value):return html.Div([html.Small(label),html.Strong(value)],className='practice-stat')


def practice_layout(tabs):
    from freeplay_ui import freeplay_layout
    return tabs('practice-mode',[
        ('system','Practice a system',system_practice_layout(tabs)),
        ('free','Free play · choose my own bets',freeplay_layout(tabs))
    ])


def system_practice_layout(tabs):
    play=html.Div([
        html.Div([
            html.Div([html.Img(id='practice-disc',src='/assets/practice-wheel-single.svg',alt='Illustrated roulette wheel'),
                      html.Div(html.Span(className='practice-ball'),id='practice-ball-track',className='practice-ball-track'),
                      html.Span(className='practice-pointer')],id='practice-wheel',className='practice-wheel',**{'aria-label':'Animated practice roulette wheel'}),
            html.Div('Ready to practice',id='practice-pocket',className='practice-pocket',role='status'),
            html.Button('Spin wheel',id='practice-spin',n_clicks=0,disabled=True,className='primary practice-spin'),
            html.P('A random pocket is drawn for each spin. Zero pockets are white. The 000 layout is illustrative.',className='small-note'),
            html.Div(id='practice-recent',className='practice-recent',**{'aria-label':'Recent simulated pockets'})
        ],className='practice-wheel-column'),
        html.Div([html.Div(id='practice-stats',className='practice-stats'),
                  html.Fieldset([html.Legend('Even-money box for the next spin'),
                      dcc.RadioItems(id='practice-even',options=[{'label':v,'value':k} for k,v in EVEN_CHOICES.items()],value='red',inline=True,className='even-choice-options')],id='practice-choice-wrap',className='even-choice-picker',style={'display':'none'}),
                  html.Div(id='practice-bets'),html.Div(id='practice-coverage')],className='practice-action-column')
    ],className='practice-play-grid')
    return html.Section([
        html.P('PRACTICE / VIRTUAL MONEY',className='eyebrow'),html.H2('Take your system for a spin.'),
        html.P('Watch the wheel, try the suggested bets, and see how the session changes. Practice has its own bankroll and history; your tracked session stays separate.',className='beginner-intro'),
        html.Div(id='practice-applied',className='settings-summary'),
        html.Div([html.Label(['System to practice',dcc.Dropdown(id='practice-system',options=[],clearable=False)],className='field'),
                  html.Button('Start new practice',id='practice-start',n_clicks=0,className='primary'),
                  html.Button('Restart practice',id='practice-reset',n_clicks=0,disabled=True,className='secondary'),
                  html.Button('Undo practice spin',id='practice-undo',n_clicks=0,disabled=True,className='secondary')],className='practice-controls'),
        html.Div(id='practice-notice',role='status',className='practice-notice'),
        tabs('practice-view',[
            ('play','Wheel & play',play),
            ('log','Practice log & export',html.Div([html.Button('Export practice CSV',id='practice-export',n_clicks=0,disabled=True,className='secondary'),html.Div(id='practice-log')],className='practice-log-panel')),
            ('help','How practice works',html.Div([
                html.H3('Practice the selected system'),
                html.Ol([html.Li('Apply your wheel and limits in step 1. Choose a system here and start a new practice session.'),
                         html.Li('The listed wagers are placed together for one simulated spin. Covered squares show which numbers can win a wager; use the written instructions for exact chip placement.'),
                         html.Li('Press Spin wheel. The wheel and ball animate, then all wagers settle automatically. The next bet and full remaining-session probability update.'),
                         html.Li('Use Undo for a teaching example, Restart to replay the same scenario, or export the practice log for your report.')]),
                html.P('All four wheel types use their modeled pocket counts. French mode applies La Partage to eligible even-money bets. Zero pockets never count as even, odd, high, or low.'),
                html.P('Each pocket is equally likely on every spin, independently of the betting system and earlier results. The animation is illustrative, not a physical wheel predictor. The ball finishes above the winning pocket.'),
                html.P('Practice stops at your target, spin limit, or when the next prescribed wager cannot fit your limits. A high modeled chance of reaching the target can still involve severe losses. A short demo run does not establish a system’s true odds.'),
                html.P('Practice autosaves separately in this browser. Reloading during a spin replays the same pending draw before settling it once. Practice exports are explicitly labeled as simulated. This feature uses no AI tokens or real money.')
            ],className='practice-help'))
        ]),
        dcc.Store(id='practice-data',storage_type='local'),dcc.Store(id='practice-animation'),
        dcc.Store(id='practice-animation-done'),dcc.Store(id='practice-animation-ack'),dcc.Download(id='practice-download')
    ],className='practice-section panel')


def coverage_map(entries,wheel):
    from engine import POSITIONS
    covered={str(number) for entry in entries for number in entry['numbers']}
    def cell(number):
        return html.Span(number,className='practice-number '+pocket_color(number)+(' covered' if number in covered else ''),
                         **{'aria-label':f'{number}'+(' covered by a wager' if number in covered else ' not covered')})
    numbers=[str(n) for row in (3,2,1) for n in range(row,37,3)]
    zeros=[n for n in pockets(wheel) if n in ('0','00','000')]
    return html.Div([html.H4('Numbers covered by the next wagers'),html.Div([
        html.Div([cell(n) for n in zeros],className='practice-zeros'),
        html.Div([cell(n) for n in numbers],className='practice-number-grid')],className='practice-table'),
        html.Small('Outlined squares are covered. This map shows coverage; the instructions above show where to place each stake.')],className='practice-coverage')


def register_practice(app):
    @app.callback(Output('practice-system','options'),Output('practice-system','value'),Output('practice-applied','children'),
                  Input('calculation','data'),State('practice-system','value'),State('practice-data','data'))
    def configure(result,selected,data):
        if not result:raise PreventUpdate
        rows=result['rows'];config=result['scenario']
        keys={r['key'] for r in rows}
        saved_session=data.get('session') if isinstance(data,dict) else None
        if not isinstance(selected,str) or selected not in keys:selected=saved_session.get('key') if isinstance(saved_session,dict) else None
        return ([{'label':r['label'],'value':r['key']} for r in rows],selected if isinstance(selected,str) and selected in keys else rows[0]['key'],
                f"New practice uses applied settings: {money(config['bankroll'])} bankroll · +{money(config['target'])} target · {config['spins']} spins · {WHEELS[config['wheel']]}. Changing these settings does not alter an existing practice session.")

    def change_practice(start,spin,reset,undo,even,done,result,key,data):
        trigger=ctx.triggered_id
        try:
            if trigger=='calculation':
                if data:return validate_practice(data),'Practice session resumed separately from your tracked session.'
                raise PreventUpdate
            if trigger=='practice-start':
                if not start or not result:raise PreventUpdate
                try:existing=validate_practice(data) if data else None
                except (ValueError,TypeError,KeyError,ArithmeticError):existing=None
                if existing and existing.get('pending'):raise ValueError('Wait for the current practice spin to finish.')
                row=next((r for r in result['rows'] if r['key']==key),None)
                if not row:raise ValueError('Choose a system from the applied comparison.')
                return new_practice(Scenario(**result['scenario']),key,row['base'],even),'New virtual-money practice session started. Review the bets, then spin.'
            if not data:raise PreventUpdate
            data=validate_practice(data)
            if trigger=='practice-spin' and spin:
                return begin_spin(data),'Spinning… the displayed wagers are locked for this simulated spin.'
            if trigger=='practice-animation-done':
                if not done or not data.get('pending') or done.get('id')!=data['pending']['id']:raise PreventUpdate
                updated=finish_spin(data,done['id']);last=updated['session']['history'][-1]
                return updated,f"Simulated pocket {last['winning_number']}: {money(last['net'])}. Practice bankroll and next bet updated."
            if trigger=='practice-undo' and undo:
                return undo_practice(data),'Practice spin undone. The previous bankroll, spin count, and bet are restored.'
            session=data['session'];s=Scenario(**session['scenario'])
            if trigger=='practice-even' and even==session.get('even_bet','red'):raise PreventUpdate
            if data.get('pending'):raise ValueError('Wait for the current practice spin to finish.')
            if trigger=='practice-reset' and reset:
                return new_practice(s,session['key'],session['base'],session.get('even_bet','red')),'Practice restarted with the same system and limits.'
            if trigger=='practice-even':
                if even==session.get('even_bet','red'):raise PreventUpdate
                current=snapshot(s,session['key'],session['base'],session['history'],with_stats=False,even_bet=session.get('even_bet','red'))
                if even not in EVEN_CHOICES or current.get('stop') or not supports_even_choice(session['key'],current):raise PreventUpdate
                return dict(data,session=dict(session,even_bet=even)),f'Next practice wager uses {EVEN_CHOICES[even]}.'
            raise PreventUpdate
        except (ValueError,TypeError,KeyError,ArithmeticError) as exc:
            return no_update,str(exc)

    @app.callback(Output('practice-data','data'),Output('practice-notice','children'),Output('practice-even','value'),
        Input('practice-start','n_clicks'),Input('practice-spin','n_clicks'),Input('practice-reset','n_clicks'),Input('practice-undo','n_clicks'),
        Input('practice-even','value'),Input('practice-animation-done','data'),Input('calculation','data'),
        State('practice-system','value'),State('practice-data','data'),prevent_initial_call=True)
    def update(start,spin,reset,undo,even,done,result,key,data):
        updated,message=change_practice(start,spin,reset,undo,even,done,result,key,data)
        return updated,message,updated['session'].get('even_bet','red') if isinstance(updated,dict) else no_update

    @app.callback(Output('practice-stats','children'),Output('practice-bets','children'),Output('practice-pocket','children'),
        Output('practice-recent','children'),Output('practice-coverage','children'),Output('practice-log','children'),
        Output('practice-spin','disabled'),Output('practice-start','disabled'),Output('practice-reset','disabled'),Output('practice-undo','disabled'),
        Output('practice-system','disabled'),Output('practice-even','options'),Output('practice-choice-wrap','style'),
        Output('practice-export','disabled'),Output('practice-animation','data'),
        Input('practice-data','data'),Input('calculation','data'))
    def render(data,result):
        enabled=[{'label':v,'value':k} for k,v in EVEN_CHOICES.items()]
        if not data:
            return ([],html.P('Choose a system and press Start new practice.',className='empty-state'),'Ready to practice',[],[],html.P('No practice spins yet.'),
                    True,not bool(result),True,True,False,enabled,{'display':'none'},True,None)
        try:
            data=validate_practice(data)
            session=data['session'];s=Scenario(**session['scenario']);history=session['history'];even=session.get('even_bet','red')
            current=snapshot(s,session['key'],session['base'],history,even_bet=even)
        except (ValueError,TypeError,KeyError,ArithmeticError):
            return ([],html.P('This practice save could not be read. It is kept until you choose Start new practice to replace it.',className='error'),'Practice unavailable',[],[],[],
                    True,not bool(result),True,True,False,enabled,{'display':'none'},True,None)
        pending=data.get('pending');busy=bool(pending);stop=current.get('stop');last=history[-1] if history else None
        stats=[stat('Practice bankroll',money(current['bankroll'])),stat('Practice profit',money(current['net_profit'])),stat('Spins left',str(current['spins_left'])),
               stat('Reach target · remaining session',f"{current['stats']['success']:.4%}")]
        names={**LABELS,'oneshot':'One-shot even-money','even':'Adaptive even-money','dozen':'Adaptive dozen / column','sixline':'Adaptive six-line','groups':'Adaptive equal-group portfolios','research':'Custom optimized betting plan'}
        info=SYSTEMS[session['key']]
        explanation=html.Details([html.Summary('System rule · pros & risks'),html.P(info['how']),
            html.Div([html.Div([html.H4('Pros'),html.Ul([html.Li(t) for t in info['pros']])]),html.Div([html.H4('Cons / risks'),html.Ul([html.Li(t) for t in info['cons']])])],className='pros-cons'),
            html.P(f"Projected final-session average: {money(current['stats']['mean'])}. Worst-five-percent average: {money(current['stats']['worst5'])}. A high target probability can still involve severe losses.")],className='practice-system-help')
        intro=html.Div([html.Strong(names[session['key']]),html.P(info['subtitle']),html.P(f"{WHEELS[s.wheel]} · start {money(s.bankroll)} · target +{money(s.target)}"),
                        html.Small('Virtual money. Same limits and payouts as the calculator.'),explanation],className='practice-system-intro')
        if stop:bets=html.Div([intro,html.H3('Practice session complete'),html.P(stop)],className='practice-bets stop-action')
        else:bets=html.Div([intro,html.P('WAGERS LOCKED FOR THIS SPIN' if busy else 'NEXT PRACTICE BET',className='eyebrow'),
                    html.H3(f"{money(current['total'])} total"),html.Ul([html.Li([html.Strong(f"{money(e['amount'])} on {position_name(e['numbers'])}"),html.Small(placement_instruction(e['numbers']))]) for e in current['entries']],className='bet-instructions'),
                    html.Small('Press Spin wheel to place these virtual wagers together. The app settles the outcome automatically.')],className='practice-bets')
        result_view='Spinning…' if busy else (html.Div([html.Strong(last['winning_number'],className='pocket-badge '+pocket_color(last['winning_number'])),html.Span(f"{'Win' if last['net']>0 else 'Loss' if last['net']<0 else 'Break even'} · {money(last['net'])}")]) if last else 'Ready for your first spin')
        recent=[html.Span(e['winning_number'],className='pocket-chip '+pocket_color(e['winning_number']),title=f"Practice spin {len(history)-i}: {money(e['net'])}") for i,e in enumerate(reversed(history[-12:]))]
        rows=session_log(s,session['key'],session['base'],history)
        log=html.Div([html.H3(f"{len(rows)} simulated {('spin' if len(rows)==1 else 'spins')}"),html.Div(html.Table([
            html.Thead(html.Tr([html.Th(t) for t in ['Spin','Virtual bets','Pocket','Net','Bankroll','Profit']])),
            html.Tbody([html.Tr([html.Td(r['spin']),html.Td('; '.join(f"{money(b['amount'])} {b['position']}" for b in r['bets'])),html.Td(r['winning_number']),html.Td(money(r['net'])),html.Td(money(r['bankroll'])),html.Td(money(r['profit']))]) for r in rows])
        ]),className='table-wrap') if rows else html.P('Spin the wheel to add a simulated result. This is separate from your tracked session log.')])
        command=dict(wheel=s.wheel,order=pockets(s.wheel),number=pending['number'] if busy else last['winning_number'] if last else '0',
                     id=pending['id'] if busy else data.get('last_id'),active=busy)
        options=[dict(o,disabled=busy) for o in enabled]
        return (stats,bets,result_view,recent,coverage_map(current.get('entries',[]),s.wheel),log,
                bool(stop) or busy,busy or not bool(result),busy,busy or not bool(history),busy,options,
                {'display':'block' if not stop and supports_even_choice(session['key'],current) else 'none'},busy or not bool(history),command)

    app.clientside_callback('function(command) {return window.dash_clientside.practice.animate(command);}',Output('practice-animation-ack','data'),Input('practice-animation','data'))

    @app.callback(Output('practice-download','data'),Input('practice-export','n_clicks'),State('practice-data','data'),prevent_initial_call=True)
    def export(n,data):
        if not n or not data or not data['session']['history']:raise PreventUpdate
        return dict(content='\ufeff'+practice_csv(data),filename='crimson-calculus-practice-simulated.csv',type='text/csv;charset=utf-8')
