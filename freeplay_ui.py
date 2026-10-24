"""Manual betting table and an independently saved, virtual-money roulette game."""
from dash import ALL, Input, Output, State, dcc, html, ctx, no_update
from dash.exceptions import PreventUpdate
from engine import Scenario, WHEELS, EVEN_CHOICES
from practice import pockets,pocket_color
from practice_ui import money,stat
from freeplay_advisor import SYSTEM_NAMES,choose_advisor,suggested_bets,load_suggestion
from table_targets import inside_targets
from freeplay import (positions,new_game,validate_game,status,edit_bet,begin_game_spin,finish_game_spin,undo_game,game_csv)

TYPES={'straight':'Straight · one number','split':'Split · two neighbors','street':'Street · three numbers',
       'corner':'Corner · four numbers','sixline':'Six-line · six numbers','dozen':'Dozen · twelve numbers',
       'column':'Column · twelve numbers','outside':'Even-money outside bets','zero':'Special zero-area bets'}


def display_wheel(data):
    """Keep recovery controls renderable even when a browser save is damaged."""
    config=data.get('scenario') if isinstance(data,dict) else None
    wheel=config.get('wheel') if isinstance(config,dict) else None
    return wheel if isinstance(wheel,str) and wheel in WHEELS else 'single'


def category(key):
    if key.startswith(('trio:','split:zero:')) or key in ('firstfour','basket','topline'):return 'zero'
    return key.split(':')[0] if ':' in key else 'outside'


def freeplay_layout(tabs):
    play=html.Div([
        html.Div([
            html.Div([html.Img(id='free-disc',src='/assets/practice-wheel-single.svg',alt='Free-play roulette wheel'),
                html.Div(html.Span(className='practice-ball'),id='free-ball-track',className='practice-ball-track'),html.Span(className='practice-pointer')],id='free-wheel',className='practice-wheel'),
            html.Div('Ready for free play',id='free-pocket',className='practice-pocket',role='status'),
            html.P('Virtual money · independent random pockets · wagers lock while spinning',className='small-note'),
            html.Div(id='free-recent',className='practice-recent')],className='practice-wheel-column'),
        html.Div([html.Div(id='free-stats',className='practice-stats'),
            html.Div([html.H3('1. Choose how much to add'),
                html.Label(['Amount per click ($)',dcc.Input(id='free-amount',type='number',value=5,min=5,step=1)],htmlFor='free-amount',className='field'),
                html.P('Click a number for a straight bet, a line between two numbers for a split, or an intersection for a corner. Street bets sit along the bottom edge. Hover or focus to preview coverage.',className='small-note')],className='free-instructions'),
            html.Div([html.Div([html.Small('Chance of net profit this spin'),html.Strong('—',id='free-win-chance')],className='free-win-main'),
                html.Div(id='free-spin-details'),html.Small('Net profit means all returns minus ALL wagers. A winning individual bet can still leave the combined spin at a loss.')],className='free-spin-odds'),
            ],className='practice-action-column'),
        html.Div(id='free-table',className='free-table-stage'),
        html.Div([html.Div([
            html.Div([html.Div(id='free-suggestion'),html.Button('Use suggested bets',id='free-load-suggestion',n_clicks=0,disabled=True,className='secondary')],className='free-suggestion'),
            html.Details([html.Summary('More bets: splits, streets, corners & zero-area bets'),
                html.Div([html.Label(['Bet type',dcc.Dropdown(id='free-type',options=[{'label':v,'value':k} for k,v in TYPES.items()],value='split',clearable=False)],className='field'),
                    html.Label(['Position',dcc.Dropdown(id='free-position',options=[],clearable=False)],className='field'),
                    html.Button('Add this bet',id='free-add-position',n_clicks=0,className='secondary')],className='free-advanced'),
                html.Div(id='free-position-help',className='small-note')],className='free-more')]),
            html.Div([html.H3('2. Review your bets, then spin'),html.Div(id='free-slip'),
                html.Div([html.Button('Spin with my bets',id='free-spin',n_clicks=0,disabled=True,className='primary practice-spin'),
                    html.Button('Clear all bets',id='free-clear',n_clicks=0,className='secondary')],className='button-row'),
                html.Div(id='free-odds',className='free-odds')],className='practice-bets')],className='free-betting-footer')
    ],className='practice-play-grid free-play-grid')
    return html.Section([
        html.P('FREE PLAY / VIRTUAL MONEY',className='eyebrow'),html.H2('Your bets. Your next move.'),
        html.P('Build your own wagers instead of following a system. Free play has its own bankroll, autosave, and log.',className='beginner-intro'),
        html.Div(id='free-applied',className='settings-summary'),
        html.Div([html.Button('Start new free play',id='free-start',n_clicks=0,className='primary'),
            html.Button('Restart free play',id='free-reset',n_clicks=0,disabled=True,className='secondary'),
            html.Button('Undo free-play spin',id='free-undo',n_clicks=0,disabled=True,className='secondary')],className='practice-controls'),
        html.Div(id='free-notice',role='status',className='practice-notice'),
        html.Details([html.Summary('Optional: choose a system for suggested bets'),
            html.Div([html.Label(['Suggestion system',dcc.Dropdown(id='free-system',options=[],clearable=False)],className='field'),
                html.Label(['Even-money box',dcc.Dropdown(id='free-system-even',options=[{'label':v,'value':k} for k,v in EVEN_CHOICES.items()],value='red',clearable=False)],className='field'),
                html.Button('Use selected system',id='free-system-use',n_clicks=0,className='secondary')],className='free-advisor-controls'),
            html.P('Starts a new progression when you choose a different system. Matching even-money wagers advance a named system; a different manual wager restarts its cycle. Adaptive systems use the actual bankroll and spins. No prediction or guarantee.',className='small-note')],className='free-system-picker'),
        tabs('free-view',[
            ('play','Betting table',play),
            ('log','Free-play log & export',html.Div([html.Button('Export free-play CSV',id='free-export',n_clicks=0,disabled=True,className='secondary'),html.Div(id='free-log')],className='practice-log-panel')),
            ('help','Rules & payouts',html.Div([
                html.H3('Choose any combination of the available bets'),
                html.Ol([html.Li('Apply the desired wheel and limits in Session settings. Start new free play copies them into a separate game. Restart uses your current free-play settings.'),
                    html.Li('Set an amount and click a number or outside box. Click the dividing line between two numbers for a split, the diamond at a four-number intersection for a corner, or a bottom-edge label for a street. Hover or focus to preview the covered numbers. More bets remains available for six-lines and zero-area choices.'),
                    html.Li('Review the itemized bet slip. Each position must meet the minimum and chip increment. The combined wager must fit the table maximum, available cash and remaining loss allowance.'),
                    html.Li('Press Spin with my bets. All winning positions pay together. The net result subtracts all stakes. Your bets stay on the slip for the next spin; remove or change them as you like.')]),
                html.P('Net payouts: straight 35:1; split 17:1; street or trio 11:1; corner / first four 8:1; six-line 5:1; dozen / column 2:1; even-money 1:1. Winning stakes are also returned. The American five-number top line pays 6:1 and has a higher house edge. The illustrative triple-zero six-number top line pays 5:1.'),
                html.P('Zero, double zero and triple zero are distinct pockets. They are never red, black, odd, even, low or high. French La Partage refunds half of each even-money stake on zero, for any stake size. Other bets settle normally. En Prison is not modeled.'),
                html.P('All pockets are equally likely and independent. Free play stops at your profit target, spin limit or when no minimum bet fits the loss allowance. After a loss, your previous slip may need smaller bets before another spin.'),
                html.P('Optional system suggestions use your actual free-play bankroll and spins. Named progressions advance only after a matching prescribed even-money wager; a manual deviation restarts the cycle at its base. Changing systems starts a fresh progression, and Undo reconstructs it. Use suggested bets replaces the slip; it does not spin automatically.'),
                html.P('The odds shown describe the current spin only. A whole-session target probability is not calculated because you can choose different future bets. Roulette retains a house edge; changing bets cannot remove it.'),
                html.P('The zero-area choices follow this demo’s listed layouts; physical tables vary. Triple-zero layout is illustrative. Autosave and Undo are separate from system practice and your tracked session. Pending draws resume once after a reload; CSV exports are labeled simulated. No real money or AI tokens are used.')
            ],className='practice-help'))]),
        dcc.Store(id='free-data',storage_type='local'),dcc.Store(id='free-animation'),dcc.Store(id='free-animation-done'),dcc.Store(id='free-animation-ack'),dcc.Download(id='free-download')
    ])


def betting_table(s,entries,busy):
    stakes={e['position']:e['amount'] for e in entries};available=positions(s.wheel)
    def button(key,label,color='',target=None):
        amount=stakes.get(key,0);p=available[key]
        name=f"{p['label']} · pays {p['gross']-1}:1"+(f" · {money(amount)} placed" if amount else '')
        style={'left':f"{target['x']}%",'top':f"{target['y']}%"} if target else None
        marker=target is not None
        return html.Button([html.Span(label),html.Small(money(amount)) if amount else None],id={'type':'free-table-bet','position':key},n_clicks=0,disabled=busy,
            className=('free-inside-target '+target['kind'] if marker else 'free-table-cell '+color)+(' has-bet' if amount else ''),title=name,style=style,
            **{'aria-label':name if marker else label+(' '+money(amount) if amount else ''),'data-free-bet':key,'data-bet-numbers':','.join(p['numbers']),
               'data-bet-label':p['label'],'data-bet-payout':str(p['gross']-1),'data-pocket':key.split(':')[1] if key.startswith('straight:') else ''})
    zeros=[n for n in pockets(s.wheel) if n in ('0','00','000')]
    return html.Div([
        html.Div([html.Span('♠',**{'aria-hidden':'true'}),html.Strong('THE ROULETTE ROOM'),html.Span('Place your chips')],className='free-table-masthead'),
        html.Div([
        html.Div([button('straight:'+n,n,'zero') for n in zeros],className='free-zeros'),
        html.Div([html.Div([
            *[button('straight:'+str(n),str(n),pocket_color(str(n))) for row in (3,2,1) for n in range(row,37,3)],
            *[button(t['key'],'',target=t) for t in inside_targets()]],className='free-numbers'),
            html.Div([button('street:'+str(n),f'{3*n+1}–{3*n+3}',color='street-edge') for n in range(12)],className='free-streets')],className='free-number-board'),
        html.Div([button('column:'+str(n),'Col '+str(n+1)) for n in (2,1,0)],className='free-columns')],className='free-table-main'),
        html.Div([button('dozen:'+str(n),['1st 12','2nd 12','3rd 12'][n]) for n in range(3)],className='free-dozens'),
        html.Div([button(key,label,color) for key,label,color in [('low','1–18',''),('even','EVEN',''),('red','RED','red'),('black','BLACK','black'),('odd','ODD',''),('high','19–36','')]],className='free-outside'),
        html.Div('Hover over a number, dividing line, intersection or street edge to preview the bet.',id='free-table-preview',className='free-table-preview',role='status'),
        html.Small('Dots mark clickable splits; diamonds mark corners. Bottom-edge labels place one street bet covering all three numbers. Zero-area combinations remain in More bets.')],className='free-table-wrap')


def register_freeplay(app):
    @app.callback(Output('free-system','options'),Output('free-system','value'),Output('free-system-even','value'),
        Input('calculation','data'),Input('free-data','data'),Input('session-data','data'),
        State('practice-data','data'),State('free-system','value'))
    def system_choices(result,data,tracked,practice,selected):
        try:data=validate_game(data) if data else None
        except (ValueError,TypeError,KeyError,ArithmeticError):data=None
        tracked=tracked if isinstance(tracked,dict) else None
        practice=practice if isinstance(practice,dict) else None
        config=(data or {}).get('scenario') or (result or {}).get('scenario')
        rows=result['rows'] if result and result['scenario']==config else []
        options=[{'label':'No system · manual bets only','value':'none'}]+[{'label':r['label'],'value':r['key']} for r in rows]
        guide=(data or {}).get('advisor')
        if guide and not any(o['value']==guide['key'] for o in options):options.append({'label':SYSTEM_NAMES[guide['key']],'value':guide['key']})
        keys={o['value'] for o in options}
        if not result and not guide:return options,no_update,no_update
        if not isinstance(selected,str) or selected not in keys:
            candidates=[guide,tracked,(practice or {}).get('session')]
            selected=next((c['key'] for c in candidates if isinstance(c,dict) and isinstance(c.get('key'),str) and c['key'] in keys and (c is guide or c.get('scenario')==config)),'none')
        even=(guide or {}).get('even_bet',(tracked or {}).get('even_bet','red'))
        return options,selected,even if isinstance(even,str) and even in EVEN_CHOICES else 'red'

    @app.callback(Output('free-suggestion','children'),Output('free-load-suggestion','disabled'),Output('free-win-chance','children'),Output('free-spin-details','children'),
        Output('free-system','disabled'),Output('free-system-even','disabled'),Output('free-system-use','disabled'),Input('free-data','data'))
    def guide_and_odds(data):
        if not data:return html.P('Start free play to enable optional system suggestions.'),True,'—',html.P('Add bets to calculate this spin’s odds.'),False,False,True
        try:
            data=validate_game(data);current=status(data);suggestion=suggested_bets(data);guide=data.get('advisor');available=positions(data['scenario']['wheel'])
            busy=bool(data.get('pending'))
            title='Suggested next bet · '+SYSTEM_NAMES[guide['key']] if guide else 'Optional system suggestion'
            content=[html.H4(title)]
            if suggestion.get('stop'):content.append(html.P(suggestion['stop'],className='stop-note'))
            elif suggestion['entries']:
                content.append(html.Ul([html.Li(f"{money(e['amount'])} on {available[e['position']]['label']}") for e in suggestion['entries']]))
                content.append(html.P('Use suggested bets replaces the entire current slip. You can edit it before spinning.',className='small-note'))
            content.append(html.Small(suggestion['note']))
            details=html.P(f"Net loss {current['loss_chance']:.2%} · break even {current['break_even_chance']:.2%} · average net {money(current['mean'])}.") if data['bets'] else html.P('Add bets to calculate this spin’s odds.')
            return content,busy or not bool(suggestion['entries']),f"{current['profit_chance']:.2%}" if data['bets'] else '—',details,busy,busy,busy
        except (ValueError,TypeError,KeyError,ArithmeticError) as exc:
            return html.P('Suggestion unavailable: '+str(exc)),True,'—',html.P('Start new free play to replace the unreadable save.'),False,False,True

    @app.callback(Output('free-position','options'),Output('free-position','value'),Input('free-type','value'),Input('free-data','data'),State('free-position','value'))
    def choices(kind,data,selected):
        wheel=display_wheel(data);available=positions(wheel)
        options=[{'label':v['label'],'value':k} for k,v in available.items() if category(k)==kind]
        keys={o['value'] for o in options}
        return options,selected if selected in keys else options[0]['value'] if options else None

    @app.callback(Output('free-position-help','children'),Input('free-position','value'),Input('free-data','data'))
    def position_help(key,data):
        wheel=display_wheel(data);position=positions(wheel).get(key)
        if not position:return ''
        return f"Covers {', '.join(position['numbers'])}. Pays {position['gross']-1}:1 net profit plus the winning stake back."

    @app.callback(Output('free-data','data'),Output('free-notice','children'),Output('free-amount','value'),
        Input('free-start','n_clicks'),Input('free-reset','n_clicks'),Input('free-undo','n_clicks'),Input('free-clear','n_clicks'),Input('free-spin','n_clicks'),
        Input('free-add-position','n_clicks'),Input({'type':'free-table-bet','position':ALL},'n_clicks'),Input({'type':'free-remove-bet','position':ALL},'n_clicks'),
        Input('free-animation-done','data'),Input('active-scenario','data'),Input('free-system-use','n_clicks'),Input('free-load-suggestion','n_clicks'),
        State('free-position','value'),State('free-amount','value'),State('free-data','data'),State('free-system','value'),State('free-system-even','value'),State('calculation','data'),prevent_initial_call=True)
    def update(start,reset,undo,clear,spin,add,table_clicks,remove_clicks,done,config,use_system,load,key,amount,data,system,even,result):
        trigger=ctx.triggered_id
        def selected_guide(game):
            if not system or system=='none':return choose_advisor(game,None)
            if result and result['scenario']==game['scenario']:
                row=next((r for r in result['rows'] if r['key']==system),None)
            else:row=game.get('advisor') if (game.get('advisor') or {}).get('key')==system else None
            if not row:raise ValueError('Apply matching settings or start new free play before choosing this system.')
            return choose_advisor(game,system,row['base'],even)
        try:
            if trigger=='active-scenario':
                if not data:raise PreventUpdate
                return validate_game(data),'Free play resumed from its separate autosave.',no_update
            if trigger=='free-start':
                try:existing=validate_game(data) if data else None
                except (ValueError,TypeError,KeyError,ArithmeticError):existing=None
                if existing and existing.get('pending'):raise ValueError('Wait for the current spin to finish.')
                s=Scenario(**config)
                return selected_guide(new_game(s)),'New free-play session started. Add your bets or load the system suggestion.',s.minimum
            if not data:raise ValueError('Press Start new free play first.')
            data=validate_game(data)
            if trigger=='free-animation-done':
                if not done or not data.get('pending') or done.get('id')!=data['pending']['id']:raise PreventUpdate
                updated=finish_game_spin(data,done['id']);last=updated['history'][-1]
                return updated,f"Pocket {last['number']} · {money(last['net'])} net. Bets remain on the slip; change them or spin again.",no_update
            if isinstance(trigger,dict):
                if not ctx.triggered[0].get('value'):raise PreventUpdate
                updated=edit_bet(data,trigger['position'],amount,remove=trigger['type']=='free-remove-bet')
                return updated,'Bet slip updated.',no_update
            if trigger=='free-system-use':return selected_guide(data),'Suggestion system updated. Your bet slip stays as entered until you press Use suggested bets.',no_update
            if trigger=='free-load-suggestion':return load_suggestion(data),'Suggested wagers loaded onto the table. Review them before spinning.',no_update
            if trigger=='free-add-position':return edit_bet(data,key,amount),'Bet added to the slip.',no_update
            if trigger=='free-clear':return edit_bet(data,clear=True),'All bets cleared.',no_update
            if trigger=='free-spin':return begin_game_spin(data),'Spinning… your custom wagers are locked.',no_update
            if trigger=='free-undo':return undo_game(data),'Last spin undone; its original bet slip and bankroll restored.',no_update
            if trigger=='free-reset':
                if data.get('pending'):raise ValueError('Wait for the current spin to finish.')
                game=new_game(Scenario(**data['scenario']));guide=data.get('advisor')
                if guide:game=choose_advisor(game,guide['key'],guide['base'],guide['even_bet'])
                return game,'Free play restarted with the same limits and suggestion system.',no_update
            raise PreventUpdate
        except (ValueError,TypeError,KeyError,ArithmeticError) as exc:return no_update,str(exc),no_update

    @app.callback(Output('free-stats','children'),Output('free-table','children'),Output('free-slip','children'),Output('free-odds','children'),
        Output('free-pocket','children'),Output('free-recent','children'),Output('free-log','children'),Output('free-animation','data'),Output('free-applied','children'),
        Output('free-spin','disabled'),Output('free-start','disabled'),Output('free-reset','disabled'),Output('free-undo','disabled'),Output('free-clear','disabled'),
        Output('free-add-position','disabled'),Output('free-amount','disabled'),Output('free-type','disabled'),Output('free-position','disabled'),Output('free-export','disabled'),Output('free-amount','min'),Output('free-amount','step'),
        Input('free-data','data'),Input('active-scenario','data'))
    def render(data,config):
        applied=Scenario(**config)
        label=f"New free play uses applied settings: {WHEELS[applied.wheel]} · {money(applied.bankroll)} bankroll · +{money(applied.target)} target · {applied.spins} spins."
        if not data:
            return [],[],html.P('Start new free play to open the betting table.'),[],'Ready for free play',[],html.P('No free-play spins yet.'),None,label,True,False,True,True,True,True,True,True,True,True,applied.minimum,1
        try:data=validate_game(data)
        except (ValueError,TypeError,KeyError,ArithmeticError):
            return [],[],html.P('This save could not be read. It is kept until you choose Start new free play to replace it.'),[],'Save unavailable',[],[],None,label,True,False,True,True,True,True,True,True,True,True,applied.minimum,1
        s=Scenario(**data['scenario']);current=status(data);busy=bool(data['pending']);history=data['history'];available=positions(s.wheel);last=history[-1] if history else None
        stats=[stat('Free-play bankroll',money(current['bankroll'])),stat('Free-play profit',money(current['profit'])),stat('Spins left',str(current['left'])),stat('Total next wager',money(current['total']))]
        slip=html.Ul([html.Li([html.Span(f"{money(e['amount'])} on {available[e['position']]['label']}"),html.Button('Remove',id={'type':'free-remove-bet','position':e['position']},n_clicks=0,disabled=busy,className='free-remove')]) for e in data['bets']],className='free-slip') if data['bets'] else html.P('No bets yet. Click a number or an outside box to begin.')
        odds=html.Div([html.Strong(current['problem'] or 'Ready to spin'),html.P(f"This spin: {current['profit_chance']:.2%} chance of net profit · average net {money(current['mean'])} · worst net {money(current['worst'])}.") if data['bets'] else None,
            html.Small('These are current-spin odds. Future bets are your choice, so no whole-session target probability is estimated.')])
        result='Spinning…' if busy else html.Div([html.Strong(last['number'],className='pocket-badge '+pocket_color(last['number'])),html.Span(f"Net {money(last['net'])}")]) if last else 'Ready for your first spin'
        recent=[html.Span(r['number'],className='pocket-chip '+pocket_color(r['number'])) for r in reversed(history[-12:])]
        log=html.Div([html.H3(f"{len(history)} simulated {'spin' if len(history)==1 else 'spins'}"),html.Div(html.Table([html.Thead(html.Tr([html.Th(t) for t in ['Spin','Virtual bets','Pocket','Net','Bankroll','Profit']])),
            html.Tbody([html.Tr([html.Td(i),html.Td('; '.join(f"{money(e['amount'])} {available[e['position']]['label']}" for e in r['bets'])),html.Td(r['number']),html.Td(money(r['net'])),html.Td(money(r['bankroll'])),html.Td(money(r['profit']))]) for i,r in enumerate(history,1)])]),className='table-wrap')])
        pending=data['pending'];command=dict(prefix='free',wheel=s.wheel,order=pockets(s.wheel),number=pending['number'] if busy else last['number'] if last else '0',id=pending['id'] if busy else data['last_id'],active=busy)
        label+=f" Current game: {WHEELS[s.wheel]} · start {money(s.bankroll)} · target +{money(s.target)} · minimum {money(s.minimum)} per position · chip {money(s.chip)} · maximum {money(s.maximum)} total · loss limit {money(s.loss_limit)}."
        locked=busy or bool(current['stop'])
        return stats,betting_table(s,data['bets'],locked),slip,odds,result,recent,log,command,label,busy or bool(current['problem']),busy,busy,busy or not bool(history),busy or not bool(data['bets']),locked,busy,locked,locked,busy or not bool(history),s.minimum,1

    app.clientside_callback('function(command) {return window.dash_clientside.practice.animate(command);}',Output('free-animation-ack','data'),Input('free-animation','data'))

    @app.callback(Output('free-download','data'),Input('free-export','n_clicks'),State('free-data','data'),prevent_initial_call=True)
    def export(n,data):
        if not n or not data or not data.get('history') or data.get('pending'):raise PreventUpdate
        return dict(content='\ufeff'+game_csv(data),filename='crimson-calculus-free-play-simulated.csv',type='text/csv;charset=utf-8')
