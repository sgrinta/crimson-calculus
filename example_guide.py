"""Isolated calculator-only walkthrough of the original research question."""
from functools import lru_cache
from dash import html
from engine import Scenario,compare,classic_profile
from comparison_report import dollars

@lru_cache(maxsize=1)
def example_data():
    s=Scenario();comparison=compare(s)
    small=dict(classic_profile(s,'martingale',5),label='Martingale · start at $5',base=5)
    large=dict(classic_profile(s,'martingale',200),label='Martingale · start at $200',base=200)
    one=next(r for r in comparison['rows'] if r['key']=='oneshot')
    return comparison,[small,large,one]


def example_view(step):
    comparison,benchmarks=example_data();s=Scenario()
    intro=[html.P('VIVIENNE’S GUIDED EXAMPLE · FICTIONAL SETTINGS',className='eyebrow'),html.H2('Small bets or one larger wager?'),
           html.P('This separate example uses the calculator only. Your current settings, tracked game, practice and free-play logs stay as they are.',className='small-note')]
    if step==0:
        return intro+[html.P('1 / Ask a clear question',className='example-progress'),
            html.P('“With a $1,000 bankroll and a $200 profit target, should I start Martingale at $5, start at $200, or make one $200 wager?”'),
            html.Div([html.Strong('The same constraints for every plan'),html.P('$1,000 bankroll · +$200 target · $1,000 loss limit · $5 minimum / chip · $500 maximum total wager · 280 spins · European single-zero roulette.')],className='example-callout'),
            html.Ol([html.Li('Martingale doubles after a loss and resets after a win. The next prescribed wager must fit every limit.'),html.Li('One-shot means one $200 wager and then stop, even after a loss.'),html.Li('Red is only an example: the same odds apply to black, odd/even and low/high even-money bets.')]),
            html.P('Select Next to calculate the whole-session results. The wheel’s outcomes are independent; no system makes a win due.')]
    if step==1:
        head=html.Thead(html.Tr([html.Th(x) for x in ('Plan','Reach target','Average net','Max loss','Worst 5% average')]))
        body=html.Tbody([html.Tr([html.Th(r['label']),html.Td(f"{r['success']:.2%}"),html.Td(dollars(r['mean'])),html.Td(dollars(r['max_loss'])),html.Td(dollars(r['worst5']))]) for r in benchmarks])
        return intro+[html.P('2 / Compare the entire session',className='example-progress'),html.Div(html.Table([head,body]),className='table-wrap'),
            html.P('These percentages include all allowed recovery cycles until the target, spin limit, or a blocked next wager ends the session. They are not just the next-spin win rate.'),
            html.P('Starting Martingale at $200 would require $200, $400, then $800 after full losses. The $800 wager exceeds both the $500 table maximum and the $400 bankroll remaining after two losses.',className='example-callout'),
            html.P('Fewer spins alone does not determine which plan reaches the target most often. Starting amount, stopping rules, total money wagered and limits all matter.')]
    best=comparison['rows'][0];mart=next(r for r in comparison['rows'] if r['key']=='martingale')
    return intro+[html.P('3 / Read the tradeoffs',className='example-progress'),
        html.P(f"Searching every legal Martingale starting amount selects ${mart['base']}: {mart['success']:.2%} chance of reaching the target, with average net {dollars(mart['mean'])}."),
        html.P(f"Across the tested families, {best['label']} leads at {best['success']:.2%}. Its average net is {dollars(best['mean'])}, worst-5% average is {dollars(best['worst5'])}, and maximum possible loss is {dollars(best['max_loss'])}.",className='example-callout'),
        html.P('The leading percentage is only best among the plans tested. A high success rate can hide rare, large losses, and it does not remove the house edge.'),
        html.Ol([html.Li('Compare success, average net and downside together.'),html.Li('Use Step 1 to explore your own fictional constraints, then Apply settings.'),html.Li('Read Step 2 → Compare systems before choosing a plan or practicing with virtual money.')]),
        html.Button('Export this example report ↓',id='export-example-report',n_clicks=0,className='secondary'),
        html.P(f"Verified calculation {comparison['id']} · No AI tokens used.",className='small-note')]


def example_dialog():
    return html.Div(html.Div([
        html.Button('Close ×',id='example-close',n_clicks=0,className='guide-close'),
        html.Div(id='example-content'),
        html.Div([html.Button('Back',id='example-back',n_clicks=0,className='secondary',disabled=True),html.Button('Next →',id='example-next',n_clicks=0,className='primary')],className='button-row example-navigation')
    ],className='example-dialog'),id='example-modal',className='example-modal',style={'display':'none'},role='dialog',**{'aria-modal':'true','aria-label':'Guided roulette comparison example'})
