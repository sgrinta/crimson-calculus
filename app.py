"""Crimson Calculus — MGT 409 final-project working application."""
from dataclasses import asdict
from datetime import datetime, timezone
from uuid import uuid4
import json
import os
import time

from dash import ALL, Dash, Input, Output, State, callback, ctx, dcc, html, no_update
from dash.exceptions import PreventUpdate
import plotly.graph_objects as go

from engine import Scenario, WHEELS, EVEN_CHOICES, compare, cycle, classic_profile, LABELS, RULES, POSITIONS, custom_portfolio, inspect_policy, policy_snapshot, settle_policy, record_policy_step, undo_policy_step, can_undo_policy, policy_loss_stats
from agent import generate, usage_summary, MODEL
from guides import DESCRIPTIONS, guide, position_name, placement_instruction
from risk import risk_profile, PROFILES
from system_education import SYSTEMS, EXAMPLE_NOTE
from practice_ui import practice_layout, register_practice
from practice import WHEEL_ORDERS
from freeplay_ui import register_freeplay
from host_ui import PORTRAIT, portrait, host_launcher, host_panel, host_tour, host_hub
from host_context import build_session_context
from host_settings import commit_settings_update, undo_settings_update, LABELS as SETTING_LABELS
from setup_check import run_checks
from ai_evidence import export_run
from safety import redact_secrets
from pricing import message_cost, cost_label, RATE_CARD, COST_NOTE
from hosting import HOSTED_DEMO
from comparison_report import comparison_report
from example_guide import example_dialog, example_view, example_data
from tutorial_ui import tutorial_button, tutorial_dialog
from session_tracker import snapshot as session_snapshot, record as session_record, state_token, record_number, validate_saved_session, session_log, session_log_csv, supports_even_choice

APP_TITLE = "Crimson Calculus"
APP_SUBTITLE = "Roulette Odds, Strategy & Risk"
PORT = int(os.getenv("PORT", "8069"))
app = Dash(__name__, title=f"{APP_TITLE} · {APP_SUBTITLE}", update_title="Calculating…", suppress_callback_exceptions=True)
server = app.server
RED = "#C95268"


def money(x):
    return f"−${abs(x):,.2f}" if x < 0 else f"${x:,.2f}"


def metric(label, value, detail=""):
    return html.Div([html.Span(label,className="metric-label"),html.Strong(value),html.Small(detail)],className="metric")


def plot_style(fig, title=""):
    fig.update_layout(title=dict(text=title,font=dict(size=15)),font=dict(family="Arial, sans-serif",color="#EDE5D8"),
        paper_bgcolor="#171619",plot_bgcolor="#171619",margin=dict(l=45,r=20,t=45,b=45),height=340,
        xaxis=dict(showgrid=False,zerolinecolor="#625258",linecolor="#625258"),yaxis=dict(gridcolor="rgba(237,229,216,.10)",zerolinecolor="#625258"),
        legend=dict(orientation="h",y=-.23),hoverlabel=dict(bgcolor="#EDE5D8",font_color="#171619"))
    return fig


def table(head, rows, class_name=""):
    return html.Div(html.Table([html.Thead(html.Tr([html.Th(x) for x in head])),html.Tbody([html.Tr([html.Td(x) for x in row]) for row in rows])]),className="table-wrap "+class_name)


def numeric(label, key, value, hint="", minimum=1, maximum=None,step=1):
    return html.Label([html.Span(label),dcc.Input(id=key,type="number",value=value,min=minimum,max=maximum,step=step,debounce=True,persistence=True,persistence_type="local"),html.Small(hint)],className="field")


def badge(text):
    return html.Span(text,className="badge")


def guide_button(row,location):
    return html.Button("How to use this strategy ↗",id={"type":"strategy-guide","key":row['key'],"location":location},n_clicks=0,className="guide-button")


def guide_view(row,s,even_bet='red'):
    info=guide(row,s,even_bet)
    return html.Div([
        html.P("STRATEGY GUIDE · YOUR CURRENT SCENARIO",className="eyebrow"),html.H2(info['title']),html.P(info['summary'],className="guide-intro"),
        html.P(f"Last compared: bankroll ${s.bankroll:,} · target +${s.target:,} · loss limit ${s.loss_limit:,} · {s.spins} spins · ${s.chip} chips.",className="small-note"),
        html.H3("Where to put the chips"),html.P(info['placement']),
        html.H3("Your starting wager"),
        table(["Place one wager on","Amount","Where it goes"],[[e['label'],money(e['amount']),e['placement']] for e in info['opening']],"guide-wagers"),
        html.P("These starting amounts use the last scenario you compared. Change the constraints and click Compare strategies to update them.",className="small-note"),
        html.H3("What to do, step by step"),html.Ol([html.Li(step) for step in info['steps']]),
        html.Div([html.Div([html.Strong(term),html.P(definition)]) for term,definition in info['glossary']],className="guide-glossary"),
        html.H3("When to stop"),html.P(info['stop'],className="stop-note"),
        html.Div([html.P(x) for x in info['example']],className="guide-examples"),
        html.P("Useful terms: a spin is one wheel result. A base bet is your starting wager. Net profit includes earlier wins and losses, not just the latest payout.",className="small-note"),
    ])


FIELDS = ["bankroll","target","loss_limit","minimum","maximum","chip","spins","wheel"]
app.layout = html.Div([
    html.Header([html.A([html.Span(html.Span("CC"),className="logo-mark"),html.Span([html.Strong(APP_TITLE),html.Small(APP_SUBTITLE)],className="brand-lockup")],href="#",className="wordmark"),
        html.Nav([html.A("Decision lab",href="#lab"),html.A("Portfolio builder",href="#portfolio"),html.A("AI host",href="#ai-host",**{"data-host-open":"true","aria-controls":"host-panel"})]),
        badge("MGT 409 / ROULETTE DECISION LAB")],className="topbar"),
    html.Main([
        html.Section([
            html.Div([
                html.P('Free online demo · The first visit after idle may take about a minute. Sessions save in this browser; large searches have smaller limits here.',className='small-note',role='note') if HOSTED_DEMO else None,
                html.P("VINTAGE ROULETTE CLUB",className="eyebrow"),
                html.H1(["Crimson",html.Span("Calculus")]),
                html.P(APP_SUBTITLE,className="hero-copy brand-subtitle"),
                html.Div([
                    html.Button(["Open practice room ",html.Span("↗",**{"aria-hidden":"true"})],id="hero-practice",n_clicks=0,className="hero-cta"),
                    html.Button("Set your limits →",id="hero-settings",n_clicks=0,className="hero-link"),
                    tutorial_button(),
                    html.Button("Try an example",id="try-example",n_clicks=0,className="secondary example-open",type="button"),
                ],className="hero-actions"),
                html.Div([html.Div([html.Span("1"),html.Span("5"),html.Span("25")],className="club-chips",**{"aria-hidden":"true"}),html.Span("STRATEGY · PROBABILITY · PRACTICE",className="club-signature")],className="hero-club-details")
            ],className="hero-text"),
            html.Div([
                html.Div([
                    html.Img(src="/assets/vivienne-dealer-original.png",alt="",className="hero-dealer-rest",draggable="false"),
                    html.Canvas(className="hero-dealer-eyelid",width=1024,height=1536,**{"aria-hidden":"true","data-eye":"viewer-right"}),
                ],id="hero-dealer",className="hero-dealer",**{"aria-hidden":"true"}),
                html.Img(src="/assets/casino-roulette-seal.svg",alt="",className="hero-club-seal",**{"aria-hidden":"true"}),
                html.Button([html.Img(id="hero-wheel-image",src="/assets/practice-wheel-single.svg",alt="",className="hero-wheel-disc",**{"aria-hidden":"true"}),
                    html.Span(html.Span(className="hero-ball"),className="hero-ball-orbit",**{"aria-hidden":"true"})],
                    id="hero-wheel-spin",type="button",className="hero-wheel",title="Click to spin · display only",
                    **{"aria-label":"Spin the display roulette wheel at least three full turns","aria-describedby":"hero-wheel-status",
                      "data-wheel-orders":json.dumps(WHEEL_ORDERS),"data-red-numbers":json.dumps(sorted(POSITIONS["red"]["numbers"]))}),
                html.Span("Click the wheel to spin it. Display only; no session result is recorded.",id="hero-wheel-status",className="hero-wheel-status",role="status"),
                html.Div([html.Div("18 / 37",id="wheel-odds",className="wheel-number"),
                    html.P("A single-zero even-money win",id="wheel-caption"),
                    html.Small("Same wheel. Different tradeoffs.")],className="wheel-card")
            ],className="hero-art")
        ],className="hero"),
        html.Section(id="roulette-glossary", **{"aria-label":"Roulette glossary"}),
        html.Section([
            html.Aside([html.P("01 / SET THE SCENARIO",className="eyebrow"),html.H2("Set your session limits"),
                html.Div([
                    numeric("Bankroll ($)","bankroll",1000),numeric("Profit target ($)","target",200),
                    numeric("Loss limit ($)","loss_limit",1000,"Maximum net loss allowed"),numeric("Minimum bet ($)","minimum",5,"Per occupied position"),
                    numeric("Maximum wager ($)","maximum",500,"Total across the whole spin"),numeric("Chip size ($)","chip",5),
                    numeric("Spin limit","spins",280,maximum=500),
                    html.Label([html.Span("Wheel / rules"),dcc.Dropdown(id="wheel",options=[{"label":"European · single zero","value":"single"},{"label":"French · La Partage","value":"french"},{"label":"American · double zero","value":"double"},{"label":"Triple zero · 000","value":"triple"}],value="single",clearable=False,persistence=True,persistence_type="local")],className="field")
                ],className="input-grid"),
                html.Div(id="wheel-rules",className="wheel-rules"),
                html.Button(["Apply settings & continue",html.Span("→")],id="run",n_clicks=0,className="primary full"),
                html.Div([
                    html.Span([
                        html.Img(src="/assets/practice-wheel-single.svg",alt="",className="calculation-wheel-disc"),
                        html.Span(className="calculation-ball-orbit")
                    ],className="calculation-wheel",**{"aria-hidden":"true"}),
                    html.Div([
                        html.Strong("Comparing systems…"),
                        html.Span("Checking legal starting bets and supported strategies."),
                        html.Small("Larger comparisons may take a minute or more. Local calculation · no AI tokens.")
                    ],className="calculation-progress-copy")
                ],id="settings-progress",role="status",className="settings-progress calculation-progress",
                    style={"display":"none"},**{"aria-live":"polite","aria-hidden":"true"}),
                html.P("Success = at least the target, before any limit ends the session. A blocked progression stops; it never silently caps its next bet.",className="small-note"),
                html.Div(id="scenario-error",role="alert"),
            ],className="scenario-panel"),
            html.Div([dcc.Loading(html.Div(id="results"),type="dot",color=RED),html.Div(id="search-notices")],className="results-panel")
        ],id="lab",className="lab-grid"),
        html.Section([html.Div([html.P("RECOVERY CALCULATOR",className="eyebrow"),html.H2("Inspect the recovery")],className="section-heading"),
            html.Div([
                html.Div([html.Label("Progression"),dcc.Dropdown(id="cycle-strategy",options=[{"label":v,"value":k} for k,v in LABELS.items()],value="martingale",clearable=False)],className="field"),
                numeric("Base bet ($)","cycle-base",30),
                html.P("Each row shows consecutive full losses. ‘Profit if win’ includes those losses. French zero half-loss branches are included in the probabilities, but not this ladder.",className="small-note")
            ],className="cycle-controls"),dcc.Graph(id="base-chart",config={"displayModeBar":False}),html.Div(id="cycle-result")],className="panel recovery-section"),
        html.Section([html.P("POLICY EXPLORER",className="eyebrow"),html.H2("What changes after a loss?"),
            html.P("Follow a plan one spin at a time. Record the actual net result below to update your bankroll, spins remaining, chance of success, and next wagers. This is a local tracker; it does not place bets.",className="small-note"),
            html.Div([html.Div([html.Label("Adaptive policy"),dcc.Dropdown(id="policy-kind",value="research",clearable=False)],className="field"),numeric("Remaining bankroll ($)","policy-bank",1000,"French half refunds can leave fractional cash.",step=.5),numeric("Spins remaining","policy-spins",280,minimum=0)],className="cycle-controls"),
            html.Div([html.Button("Undo last result",id="policy-undo",n_clicks=0,className="secondary",disabled=True),html.Button("Restart from scenario",id="policy-reset",n_clicks=0,className="secondary")],className="button-row"),html.Div(id="policy-record-status",role="status"),
            html.Div(id="policy-result")],className="panel"),
        html.Section([html.Div([html.P("PORTFOLIO BUILDER",className="eyebrow"),html.H2("One spin. Every possible outcome."),html.P("Combine inside and outside positions, including unequal wagers. Then test repeating that exact portfolio for the full session.")],className="section-heading"),
            html.Div([html.Div([
                html.Label("Betting position"),dcc.Dropdown(id="position",options=[{"label":v["label"],"value":k} for k,v in POSITIONS.items()],value="straight:1",clearable=False),
                numeric("Stake ($)","position-amount",30),
                html.Div([html.Button("Add position",id="add-position",n_clicks=0,className="secondary"),html.Button("Clear",id="clear-positions",n_clicks=0,className="text-button")],className="button-row"),
                html.Div(id="portfolio-list"),html.Div(id="portfolio-error",role="alert"),
                html.Button("Evaluate portfolio",id="evaluate-portfolio",n_clicks=0,className="primary full"),
                html.P("Builder supports European and French layouts, including La Partage refunds. Custom 00/000 layouts are not modeled. Minimum applies to every position; maximum applies to the combined wager.",className="small-note")
            ],className="portfolio-controls"),html.Div(id="portfolio-result",className="portfolio-results")],className="portfolio-grid")
        ],id="portfolio",className="panel"),
        html.Section([
            host_tour(),
            html.Details([html.Summary("Session sharing & AI details"),html.Div([
                dcc.Checklist(id="share-session",options=[{"label":"Share Step 3, system practice, and free-play logs with Vivienne","value":"include"}],value=['include'],persistence=True,persistence_type='local',className="share-session"),
                html.P("When you send a message, your question, current settings fields, applied limits, and enabled session details go to the configured AI provider. Vivienne can read settled spins, bets, outcomes, and balances. Switch sharing off to exclude session logs from new requests; earlier chat messages may still mention them.",className="small-note"),
                badge(MODEL),html.Div(id="usage-summary",className="small-note"),
            ],className="host-options-body")],className="host-options"),
            html.P(id='host-context-status',className='host-context-status',role='status'),
            html.Div([html.Span(id='host-usage-status',role='status'),html.Button('Undo settings',id='host-settings-undo',n_clicks=0,disabled=True,type='button',className='secondary',title='Undo Vivienne’s latest settings change and comparison; game histories stay intact.')],className='host-control-row'),
            html.Div(id='host-settings-notice',role='status',className='host-settings-notice'),
            html.Div(id="thread",className="thread",role="log",**{"aria-live":"polite","aria-relevant":"additions"}),
            html.Div([html.Label("Message Vivienne, your AI host",htmlFor="prompt",className="host-sr-only"),dcc.Textarea(id="prompt",placeholder="Ask about the app, the odds, or a settings change…",maxLength=2000),html.Button("Send ↗",id="send",n_clicks=0,type="button",className="primary")],className="composer"),
            html.P("Enter sends · Shift+Enter adds a line. AI can make mistakes; review tool details under “See the calculations.”",className="host-composer-hint")
        ],id="analyst",className="analyst-section"),
        html.Section([html.Details([html.Summary("Method, assumptions & research limits"),html.Div([
            html.P("Named progressions: every legal base wager is evaluated. A separate forward distribution verifies each winner. Adaptive policies: finite-horizon dynamic programming maximizes success within a declared candidate set."),
            html.P("The 82.4353% extended research result is tied to the original single-zero, $1,000 bankroll, $200 target, $1,000 loss limit, $5 chips, $5 minimum, $500 total maximum, and 280 spins. It is not a global optimum over every possible roulette layout."),
            html.P("All spins are independent. French mode uses La Partage: zero loses half of eligible even-money stakes; half-losses advance named progressions as losses. Other bets get no refund. En Prison is not modeled. Other wheels fully lose even-money bets on every zero pocket. A reserve protected by the loss limit is never wagered. Worst 5% means the average net result in the worst five percent of sessions."),
            html.A("Payout reference: Wizard of Odds",href="https://wizardofodds.com/games/roulette/basics/",target="_blank",rel="noopener noreferrer"),
            html.P("This is a decision-analysis simulator. It does not predict results, connect to a casino, or place wagers.")],className="method-body")])],className="method-section"),
        html.Footer([html.Strong(APP_TITLE),html.Span("MGT 409 · AI Foundations for Managers · Working prototype")]),
    ],className="page"),
    dcc.Store(id="policy-history",data=[]),dcc.Store(id="calculation"),dcc.Store(id="active-scenario",data=asdict(Scenario())),
    dcc.Store(id="portfolio-data",data=[{"position":"straight:1","amount":30},{"position":"street:0","amount":10}]),
    dcc.Store(id="messages",data=[]),dcc.Interval(id="think-tick",interval=200,disabled=True,n_intervals=0),
    dcc.Download(id="download-comparison"),dcc.Download(id="download-comparison-report"),dcc.Download(id="download-example-report"),dcc.Store(id="example-step",data=0),example_dialog(),dcc.Download(id="download-session-log"),dcc.Download(id="download-ai-run"),dcc.Interval(id="usage-tick",interval=30000,n_intervals=0),
    html.Div([html.Div([html.Button("Close ×",id="close-strategy-guide",n_clicks=0,className="guide-close"),html.Div(id="strategy-guide-content")],className="strategy-dialog")],id="strategy-guide-modal",className="strategy-modal",style={"display":"none"},role="dialog",**{"aria-modal":"true","aria-label":"Strategy instructions"}),
])


def tabbed_panels(component_id, items, primary=False):
    """Keep panels mounted so tabs preserve form drafts, chat, and tracker controls."""
    first=items[0][0]
    app.clientside_callback(
        """function(value) {
            const keys="""+json.dumps([key for key,_,_ in items])+""";
            const primary="""+json.dumps(primary)+""";
            requestAnimationFrame(() => requestAnimationFrame(() => {
                window.dispatchEvent(new Event('resize'));
                const tabs=document.getElementById('workflow-tabs');
                if(primary && tabs && tabs.getBoundingClientRect().top<0) tabs.scrollIntoView({block:'start',behavior:'instant'});
            }));
            return keys.map(key => ({display:key===value ? 'block' : 'none'}));
        }""",
        [Output(component_id+'-panel-'+key,'style') for key,_,_ in items],
        Input(component_id,'value'))
    return html.Div([
        dcc.Tabs(id=component_id,value=first,children=[
            dcc.Tab(id=component_id+'-tab-'+key,label=label,value=key,
                    className='workflow-tab',selected_className='workflow-tab-selected') for key,label,_ in items],
            className='workflow-tab-list',parent_className='workflow-tab-shell'),
        *[html.Div(content,id=component_id+'-panel-'+key,role='tabpanel',
                   style={'display':'block' if key==first else 'none'},
                   **{'aria-labelledby':component_id+'-tab-'+key}) for key,_,content in items]
    ],className='tabbed-workflow' if primary else 'tabbed-subsections')


# Numbered workflow, with optional research and learning tools in their own tab.
_page=app.layout.children[1]
_hero,_glossary,_lab,_recovery,_old_tracker,_portfolio,_analyst,_method,_footer=_page.children
_settings=_lab.children[0]
_comparison=_lab.children[1]
_search_notices=_comparison.children.pop()
_settings_view=html.Section([
    html.P('Set the wheel, budget, and stopping limits first. Apply your settings to compare systems. An existing saved session keeps its original settings and log in Step 3. Choosing a system starts a new tracker with the applied settings.',className='beginner-intro'),
    html.P('Session settings',id='session-settings-label',className='settings-summary'),_settings
],className='settings-step')
_systems_view=html.Section([
    html.P('STEP 2 / CHOOSE A SYSTEM',className='eyebrow'),html.H2('Which system do you want to follow?'),
    html.P('New to roulette? Each spin produces one winning number. Your bet wins if it covers that number. A system chooses wagers; it cannot predict the wheel. Hover over a system name for an example, pros, and cons.',className='beginner-intro'),
    html.P('Choosing a system opens step 3 with its next bet. Starting bets use the best tested amount for your applied settings. Choosing another system starts a fresh tracker.',className='small-note'),
    _search_notices,
    tabbed_panels('systems-view',[
        ('list','Choose a system',dcc.Loading(html.Div(id='system-list'),type='dot',color=RED)),
        ('compare','Compare systems',_comparison)
    ])
],id='lab',className='system-picker panel')
_track_view=html.Section([
    html.P('STEP 3 / FOLLOW THE SYSTEM',className='eyebrow'),
    html.Div([html.Button('Undo last result',id='session-undo',n_clicks=0,disabled=True,className='secondary'),
              html.Button('Restart this system',id='session-reset',n_clicks=0,disabled=True,className='text-button'),
              html.Button('Clear saved session',id='session-clear',n_clicks=0,className='text-button')],className='button-row'),
    html.Div(id='session-notice',role='status'),html.Small(id='session-save-status'),
    dcc.Tabs(id='session-view',value='next',children=[
        dcc.Tab(id='session-view-tab-next',label='Next bet',value='next',className='workflow-tab',selected_className='workflow-tab-selected'),
        dcc.Tab(id='session-view-tab-log',label='Session log & export',value='log',className='workflow-tab',selected_className='workflow-tab-selected'),
        dcc.Tab(id='session-view-tab-risks',label='Odds & risks',value='risks',className='workflow-tab',selected_className='workflow-tab-selected')
    ],className='workflow-tab-list',parent_className='workflow-tab-shell'),
    html.Div(id='session-result',role='tabpanel',**{'aria-live':'polite','aria-label':'Selected session view'})
],id='next-step',className='panel next-step',**{'data-session-view':'next'})
_tools_view=html.Section([
    html.P('OPTIONAL / EXPLORE & LEARN',className='eyebrow'),html.H2('Tools & learning'),
    html.P('Explore a recovery cycle, test your own bets, ask the analyst, or look up a term. Your tracked session stays saved while you explore.',className='beginner-intro'),
    tabbed_panels('tools-view',[
        ('recovery','Recovery calculator',_recovery),
        ('builder','Build a combination',_portfolio),
        ('analyst','AI host & analyst',host_hub()),
        ('terms','Roulette terms',html.Div([html.H2('Roulette terms & diagrams'),_glossary],className='panel')),
        ('method','Method & limits',html.Div([html.H2('Method, assumptions & research limits'),_method.children[0].children[1]],className='panel')),
        ('setup','Setup & status',html.Section([html.H2('Setup & status'),html.P('Check this installation before your demo or submission. Local checks use no AI tokens. The optional connection test uses a small fictional scenario and never shares saved sessions.'),html.Div([html.Button('Check setup',id='check-setup',n_clicks=0,className='secondary'),html.Button('Test AI connection',id='test-ai-connection',n_clicks=0,className='secondary')],className='button-row'),dcc.Loading(html.Div(id='setup-check-result',role='status'),type='dot',color=RED),html.P('From the terminal: python setup_check.py. Add --test-ai for a bounded connection test, or --json for a shareable check report.',className='small-note')],className='panel'))
    ])
],className='tools-step panel')
_number_help=html.P('Number buttons: click ±1 · Ctrl/⌘ click ±10 · Shift click ±100 · Ctrl/⌘ + Shift click ±1,000. Wagers must still match the chip size.',id='numeric-click-help',className='numeric-click-help')
_settings.children.append(_number_help)
_page.children=[_hero,tabbed_panels('workflow-tabs',[
    ('settings','Step 1 · Session settings',_settings_view),
    ('systems','Step 2 · Choose a system',_systems_view),
    ('track','Step 3 · Follow the system',_track_view),
    ('practice','Practice / demo',practice_layout(tabbed_panels)),
    ('tools','Tools & learning',_tools_view)
],primary=True),_footer]
app.layout.children.extend([dcc.Store(id='session-data',storage_type='local'),dcc.Store(id='settings-applied'),dcc.Store(id='host-settings-request'),dcc.Store(id='host-settings-undo-state'),dcc.Store(id='host-settings-receipts',data=[]),host_launcher(),host_panel(_analyst),tutorial_dialog()])
register_practice(app)
register_freeplay(app)

app.clientside_callback(
    """function(value) {
        requestAnimationFrame(() => window.dispatchEvent(new Event('resize')));
        return value;
    }""",Output('next-step','data-session-view'),Input('session-view','value'))


@callback(Output('workflow-tabs','value'),Output('session-view','value'),
          Input('settings-applied','data'),Input({'type':'choose-system','key':ALL,'calculation':ALL},'n_clicks'),
          Input('hero-practice','n_clicks'),Input('hero-settings','n_clicks'),State('calculation','data'),prevent_initial_call=True)
def advance_workflow(applied,clicks,practice,settings,result):
    if ctx.triggered_id=='hero-practice' and practice:return 'practice',no_update
    if ctx.triggered_id=='hero-settings' and settings:return 'settings',no_update
    if ctx.triggered_id=='settings-applied' and applied:
        return 'systems',no_update
    if (isinstance(ctx.triggered_id,dict) and any(clicks) and ctx.triggered[0].get('value') and result
            and ctx.triggered_id.get('calculation')==result['id']
            and any(row['key']==ctx.triggered_id.get('key') for row in result['rows'])):
        return 'track','next'
    raise PreventUpdate


def result_view(result):
    rows = result["rows"]
    best = rows[0]
    s = Scenario(**result["scenario"])
    mart = next(r for r in rows if r["key"]=="martingale")
    points = rows[1:] + rows[:1]  # Draw the best point last so nearby markers cannot hide it.
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[r["max_loss"] for r in points],y=[100*r["success"] for r in points],mode="markers",
        marker=dict(size=13,color=[RED if r==best else "#DED2BE" for r in points]),
        text=[r["label"] for r in points],customdata=[[r["mean"],r["base"] or 0] for r in points],
        hovertemplate="<b>%{text}</b><br>Success %{y:.4f}%<br>Maximum loss $%{x:,.0f}<br>Average net $%{customdata[0]:,.2f}<extra></extra>"))
    fig.update_xaxes(title="Maximum possible session loss ($)")
    fig.update_yaxes(title="Chance of reaching target (%)")
    plot_style(fig,"Success versus downside")
    return html.Div([
        html.Div([html.P("BEST AMONG TESTED POLICIES",className="eyebrow"),html.Div([html.H2(best["label"]),badge("VERIFIED CALCULATION")],className="result-title"),
            html.P(DESCRIPTIONS[best['key']],className="winner-explanation"),guide_button(best,"winner"),
            html.Div([metric("Reach the target",f"{best['success']:.4%}",f"+{100*(best['success']-mart['success']):.2f} pp vs optimized Martingale"),
                metric("Average net result",money(best["mean"]),"Across successes and failures"),metric("Worst 5% average",money(best["worst5"]),f"Maximum loss {money(best['max_loss'])}")],className="metric-grid"),
            html.P(f"{best['method']} · {s.spins} spins maximum · calculation {result['id']}",className="small-note")],className="winner-card"),
        dcc.Graph(figure=fig,config={"displayModeBar":False}),
        html.Div([html.H3("Compare the full session"),html.Div([html.Button("Export comparison report ↓",id="export-report",n_clicks=0,className="secondary"),html.Button("Export JSON ↓",id="export",n_clicks=0,className="text-button")],className="comparison-export-actions")],className="table-heading"),
        html.P("Click “How to use this strategy” for chip placement, the first wager, what changes after wins or losses, and when to stop.",className="small-note table-help"),
        table(["Strategy","Starting bet","Reach target","Average net","Max. loss","Worst 5%"],
            [[html.Div([html.Strong(r["label"]),guide_button(r,"table")],className="strategy-cell"),f"${r['base']}" if r["base"] else "Changes each spin",f"{r['success']:.4%}",money(r["mean"]),money(r["max_loss"]),money(r["worst5"])] for r in rows]),
        html.Div([html.Label("Inspect a terminal-outcome distribution"),dcc.Dropdown(id="distribution-strategy",options=[{"label":r["label"],"value":r["key"]} for r in rows],value=best["key"],clearable=False),dcc.Graph(id="distribution-chart",config={"displayModeBar":False})],className="distribution-panel"),
    ])


@callback(Output("strategy-guide-content","children"),Output("strategy-guide-modal","style"),
    Input({"type":"strategy-guide","key":ALL,"location":ALL},"n_clicks"),Input("close-strategy-guide","n_clicks"),State("calculation","data"),State("session-data","data"),prevent_initial_call=True)
def open_guide(_clicks,_close,result,session):
    triggered=ctx.triggered_id
    if triggered=="close-strategy-guide":return no_update,{"display":"none"}
    if not isinstance(triggered,dict) or not result or not ctx.triggered[0].get('value'):raise PreventUpdate
    if triggered.get('location')=='simple' and session:
        result=compare(Scenario(**session['scenario']))
    row=next((r for r in result['rows'] if r['key']==triggered['key']),None)
    if not row:raise PreventUpdate
    return guide_view(row,Scenario(**result['scenario']),session.get("even_bet","red") if session and session.get("key")==row["key"] else "red"),{"display":"flex"}


@callback(Output("results","children"),Output("calculation","data"),Output("active-scenario","data"),Output("scenario-error","children"),Output("search-notices","children"),Output("settings-applied","data"),
    Input("run","n_clicks"),*[State(k,"value") for k in FIELDS],State("session-data","data"),
    running=[(Output("run","disabled"),True,False),
             (Output("settings-progress","style"),{"display":"flex"},{"display":"none"}),
             (Output("settings-progress","aria-hidden"),"false","true")])
def calculate(_n,*values):
    saved=values[-1];values=values[:-1]
    try:
        resume_notice=""
        if ctx.triggered_id is None and saved:
            try:
                restored=validate_saved_session(saved)
                s=Scenario(**restored["scenario"])
            except (ValueError,TypeError,KeyError,ArithmeticError) as exc:
                # A broken local save must not block the calculator on startup.
                # Leave it intact until the user clears it or chooses a new system.
                s=Scenario(**dict(zip(FIELDS,values)))
                resume_notice=html.P("Saved session could not be resumed; the current settings were compared instead. "
                    "Use Clear saved session in Step 3, or choose a system in Step 2 to start a new tracker. "
                    +str(exc),className="error")
        else:s=Scenario(**dict(zip(FIELDS,values)))
        result=compare(s)
        notices=html.Div([html.P(x) for x in result["notices"]],className="notice") if result["notices"] else ""
        return result_view(result),result,asdict(s),resume_notice,notices,(dict(applied_at=time.time()) if ctx.triggered_id=="run" else no_update)
    except (ValueError,TypeError,KeyError,ArithmeticError) as exc:
        return no_update,no_update,no_update,html.P(str(exc),className="error"),no_update,no_update


@callback(Output("wheel-odds","children"),Output("wheel-caption","children"),Output("wheel-rules","children"),Output("hero-wheel-image","src"),Input("active-scenario","data"))
def wheel_caption(config):
    s=Scenario(**config)
    return f"18 / {s.pockets}",WHEELS[s.wheel]+" · even-money win",html.Div([html.Strong(WHEELS[s.wheel]),html.P(f"{s.pockets} pockets · {s.even_edge:.2%} house edge on even-money bets"),html.P(s.zero_rule),html.Small("French inside and dozen/column bets retain a 2.70% house edge.") if s.wheel=='french' else None]),f"/assets/practice-wheel-{s.wheel}.svg"


@callback(Output("distribution-chart","figure"),Input("distribution-strategy","value"),State("calculation","data"))
def distribution(key,result):
    if not result:
        raise PreventUpdate
    row=next((r for r in result["rows"] if r["key"]==key),result["rows"][0])
    dd=[x for x in row["distribution"] if x["probability"]>1e-10]
    fig=go.Figure(go.Bar(x=[x["net"] for x in dd],y=[100*x["probability"] for x in dd],marker_color=[RED if x["net"]<0 else "#DED2BE" for x in dd],hovertemplate="Net $%{x}<br>Probability %{y:.4f}%<extra></extra>"))
    fig.update_xaxes(title="Terminal net profit / loss ($)")
    fig.update_yaxes(title="Probability (%)")
    return plot_style(fig,row["label"])


@callback(Output("cycle-result","children"),Input("cycle-strategy","value"),Input("cycle-base","value"),Input("active-scenario","data"))
def render_cycle(name,base,config):
    try:
        result=cycle(Scenario(**config),name,base)
        profile=classic_profile(Scenario(**config),name,base)
        return html.Div([html.Div([metric("Session success at this base",f"{profile['success']:.4%}"),metric("Average net",money(profile['mean'])),metric("Maximum loss",money(profile['max_loss']))],className="metric-grid compact"),html.P(RULES[name],className="small-note"),table(["Spin","Required bet","Losses before","Net if this wins","Loss if this loses"],[[r["step"],money(r["bet"]),money(r["losses_before"]),money(r["profit_if_win"]),money(r["loss_if_lose"])] for r in result["rows"]]),html.P(result["stop"],className="stop-note")])
    except (ValueError,TypeError) as exc:
        return html.P(str(exc),className="error")


@callback(Output("base-chart","figure"),Input("cycle-strategy","value"),Input("calculation","data"))
def base_chart(name,result):
    if not result:raise PreventUpdate
    rows=result['curves'][name]
    fig=go.Figure(go.Scatter(x=[r['base'] for r in rows],y=[100*r['success'] for r in rows],customdata=[r['mean'] for r in rows],mode='lines+markers',line=dict(color=RED,width=2),marker=dict(size=4),hovertemplate="Base $%{x}<br>Reach target %{y:.4f}%<br>Average net $%{customdata:.2f}<extra></extra>"))
    fig.update_xaxes(title="Starting wager ($)");fig.update_yaxes(title="Chance of reaching target (%)")
    return plot_style(fig,LABELS[name]+" · all legal starting wagers")


@callback(Output("portfolio-data","data"),Input("add-position","n_clicks"),Input("clear-positions","n_clicks"),State("position","value"),State("position-amount","value"),State("portfolio-data","data"),prevent_initial_call=True)
def edit_portfolio(_add,_clear,position,amount,entries):
    if ctx.triggered_id=="clear-positions":
        return []
    if len(entries or [])>=12:
        raise PreventUpdate
    return list(entries or [])+[dict(position=position,amount=amount)]


@callback(Output("portfolio-list","children"),Input("portfolio-data","data"))
def portfolio_list(entries):
    return html.Div([html.Div([html.Span(POSITIONS.get(e.get("position"),{}).get("label","Unknown position")),html.Strong(str(e.get("amount"))+" USD")],className="position-row") for e in entries] or [html.P("No positions yet.",className="small-note")])


@callback(Output("portfolio-result","children"),Output("portfolio-error","children"),Input("evaluate-portfolio","n_clicks"),Input("active-scenario","data"),State("portfolio-data","data"))
def evaluate_portfolio(_n,config,entries):
    try:
        r=custom_portfolio(Scenario(**config),entries)
        fig=go.Figure(go.Bar(x=[x["number"] for x in r["outcomes"]],y=[x["net"] for x in r["outcomes"]],marker_color=[RED if x["net"]<0 else "#DED2BE" for x in r["outcomes"]],hovertemplate="Pocket %{x}<br>Net $%{y}<extra></extra>"))
        fig.update_xaxes(type="category",title="Winning pocket")
        fig.update_yaxes(title="Net result on this spin ($)")
        return html.Div([html.Div([metric("Total stake",money(r["total"])),metric("One-spin profit chance",f"{r['one_spin_profit']:.2%}"),metric("One-spin average",money(r["one_spin_mean"]))],className="metric-grid compact"),dcc.Graph(figure=plot_style(fig),config={"displayModeBar":False}),
            html.Div([metric("Repeated-session success",f"{r['profile']['success']:.4%}"),metric("Session average",money(r["profile"]["mean"])),metric("Worst 5% average",money(r["profile"]["worst5"]))],className="metric-grid compact"),html.P(r["policy"],className="small-note")]),""
    except (ValueError,TypeError) as exc:
        return html.P("Adjust the portfolio to evaluate it.",className="empty-state"),html.P(str(exc),className="error")


# Imported shell pattern: fast send -> paint bubble/dots -> separate Interval model step.
@callback(Output("messages","data"),Output("prompt","value"),Output("think-tick","disabled"),Output("prompt","disabled"),Output("send","disabled"),Input("send","n_clicks"),State("prompt","value"),State("messages","data"),State("think-tick","disabled"),prevent_initial_call=True)
def send_message(_n,text,messages,tick_disabled):
    if not tick_disabled or not (text or "").strip():
        raise PreventUpdate
    messages=list(messages or [])
    messages.append(dict(role="user",content=redact_secrets(text.strip())))
    return messages[-24:],"",False,True,True


def settings_update_view(proposal, receipts):
    receipt=next((r for r in receipts if r.get('id')==proposal.get('id')),None)
    if receipt and receipt.get('status')=='undone':
        return html.Div([html.Strong('Settings change undone'),html.P('Previous form fields and comparison restored. Game histories are unchanged.')],className='host-settings-update',role='status')
    if receipt and receipt.get('status')=='rejected':
        return html.Div([html.Strong('Settings kept unchanged'),html.P(receipt['message'])],className='host-settings-update',role='status')
    def formatted(field,value):
        if value is None:return 'blank'
        if field=='wheel':return WHEELS.get(value,str(value))
        if field=='spins':return str(value)
        return money(value) if isinstance(value,(int,float)) else str(value)
    changes=(receipt or proposal).get('changes',[])
    applying=proposal.get('action')=='apply'
    applied=receipt and receipt.get('status')=='applied'
    if applying:
        summary=[]
        if applied:
            best=receipt['best']
            summary=[html.P([html.Strong(best['label']), ' · highest target-reaching chance among the systems tested']),
                     html.Ul([html.Li(f"Entire-session success: {best['success']:.2%}"),
                              html.Li(f"Average final net: {money(best['mean'])}"),
                              html.Li(f"Worst 5% average: {money(best['worst5'])}")]),
                     html.Small(f"Calculation {receipt['calculation_id']} · {receipt['systems_tested']} systems compared. A higher success chance does not remove the house edge.")]
        return html.Div([
            html.Strong('Settings applied · systems compared' if applied else 'Applying settings & comparing…'),
            html.Ul([html.Li(f"{SETTING_LABELS[c['field']]}: {formatted(c['field'],c['after'])}") for c in changes]) if changes else None,
            *summary,
            html.P('Existing games keep their original settings and logs. Choose a system to start a new tracker.'),
            html.Button('View comparison →',id={'type':'host-comparison-review','id':proposal['id']},n_clicks=0,type='button',className='secondary') if applied else None,
        ],className='host-settings-update',role='status')
    return html.Div([
        html.Strong('Step 1 settings updated' if receipt else 'Updating Step 1…'),
        html.Ul([html.Li(f"{SETTING_LABELS[c['field']]}: {formatted(c['field'],c['before'])} → {formatted(c['field'],c['after'])}") for c in changes]),
        html.P('Say “Apply and compare” to run these settings here. Existing sessions are unchanged.'),
        html.Button('Review Step 1 settings →',id={'type':'host-settings-review','id':proposal['id']},n_clicks=0,type='button',className='secondary'),
    ],className='host-settings-update',role='status')


def comparison_outputs(result):
    notices=html.Div([html.P(x) for x in result['notices']],className='notice') if result['notices'] else ''
    return [result_view(result),result,result['scenario'],'',notices]


@callback(*[Output(k,'value',allow_duplicate=True) for k in FIELDS],
          *[Output(k,p,allow_duplicate=True) for k,p in [('results','children'),('calculation','data'),('active-scenario','data'),('scenario-error','children'),('search-notices','children')]],
          Output('host-settings-undo-state','data'),Output('host-settings-notice','children'),Output('host-settings-receipts','data'),
          Input('host-settings-request','data'),Input('host-settings-undo','n_clicks'),
          *[State(k,'value') for k in FIELDS],State('host-settings-receipts','data'),State('active-scenario','data'),State('host-settings-undo-state','data'),prevent_initial_call=True)
def commit_host_settings(request,undo_clicks,*values):
    current=dict(zip(FIELDS,values[:-3]))
    receipts=list(values[-3] or [])
    active=values[-2]; saved_undo=values[-1]
    if undo_clicks and ctx.triggered_id=='host-settings-undo':
        try:
            fields,applied=undo_settings_update(saved_undo,current,active)
            comparison=comparison_outputs(compare(Scenario(**applied))) if saved_undo['action']=='apply' else [no_update]*5
            updated_receipts=[dict(r,status='undone',undone_at=datetime.now(timezone.utc).isoformat()) if r.get('id')==saved_undo['id'] else r for r in receipts]
            return (*[fields[k] for k in FIELDS],*comparison,None,'Settings restored. Your games and logs are unchanged.',updated_receipts)
        except (ValueError,TypeError,KeyError) as exc:
            return (*[no_update]*13,no_update,str(exc),no_update)
    if not request:raise PreventUpdate
    if any(r.get('id')==request.get('id') for r in receipts):raise PreventUpdate
    comparison=[no_update]*5; undo=no_update
    try:
        updated,receipt=commit_settings_update(request,current)
        before_applied=asdict(Scenario(**active))
        after_applied=before_applied
        if receipt['action']=='apply':
            result=compare(Scenario(**updated))
            if request.get('calculation_id')!=result['id']:
                raise ValueError('The prepared comparison no longer matches. Ask to compare again.')
            comparison=comparison_outputs(result)
            after_applied=updated
            receipt.update(status='applied',calculation_id=result['id'],systems_tested=len(result['rows']),
                           best={k:result['rows'][0][k] for k in ('label','success','mean','worst5')})
        receipt.update(before_applied=before_applied,after_applied=after_applied)
        undo=dict(id=request['id'],action=receipt['action'],before_fields=current,after_fields=updated,
                  before_applied=before_applied,after_applied=after_applied)
        fields=[updated[k] for k in FIELDS]
        notice=''
    except (ValueError,TypeError,KeyError) as exc:
        fields=[no_update]*len(FIELDS)
        receipt=dict(id=request.get('id'),status='rejected',message=str(exc))
        notice='Settings kept unchanged: '+str(exc)
    return (*fields,*comparison,undo,notice,(receipts+[receipt])[-24:])


@callback(Output('host-settings-undo','disabled'),Input('host-settings-undo-state','data'),Input('think-tick','disabled'))
def undo_settings_enabled(snapshot,idle):
    return not snapshot or not idle


@callback(Output('workflow-tabs','value',allow_duplicate=True),Output('systems-view','value',allow_duplicate=True),
          Input({'type':'host-comparison-review','id':ALL},'n_clicks'),prevent_initial_call=True)
def review_host_comparison(clicks):
    if not any(clicks):raise PreventUpdate
    return 'systems','compare'


@callback(Output('workflow-tabs','value',allow_duplicate=True),Input({'type':'host-settings-review','id':ALL},'n_clicks'),prevent_initial_call=True)
def review_host_settings(clicks):
    if not any(clicks):raise PreventUpdate
    return 'settings'


@callback(Output("thread","children"),Input("messages","data"),Input("think-tick","disabled"),Input("host-settings-receipts","data"))
def render_thread(messages,tick_disabled,settings_receipts=None):
    children=[]
    for index,m in enumerate(messages or []):
        content=[dcc.Markdown(m["content"],dangerously_allow_html=False)]
        if m.get('settings_update'):
            content.append(settings_update_view(m['settings_update'],settings_receipts or []))
        cost=message_cost(m) if m['role']=='assistant' else None
        if m.get("trace"):
            guard_notes=[]
            for call in m['trace']:
                if call.get('tool')=='safety_guard':guard_notes.append('Credential request blocked before AI.')
                elif call.get('tool') in ('apply_session_settings','update_session_settings') and call.get('status')=='rejected':guard_notes.append('Settings action rejected; no update from this request.')
                elif call.get('tool')=='output_guard':guard_notes.append('Unverified explanation replaced with calculator results.')
            notes=[html.Ul([html.Li(note) for note in guard_notes])] if guard_notes else []
            content.append(html.Details([html.Summary("See the calculations"),*notes,html.Pre(json.dumps(m["trace"],indent=2)),html.P([cost['note'],html.Br(),'Standard rates per 1M tokens: $0.10 input · $0.01 cached input · $0.50 output. ',html.Br(),html.A('Rates verified '+RATE_CARD['verified_on'],href=RATE_CARD['source'],target='_blank',rel='noopener noreferrer')],className='cost-source') if cost else None],className="trace",open=False))
        if m.get("usage"):
            u=m["usage"]
            content.append(html.Small(f"Measured tokens: {u.get('input',0):,} input · {u.get('cached',0):,} cached · {u.get('output',0):,} output",className="message-usage"))
        if m['role']=='assistant':
            content.append(html.Small(cost_label(cost),className='message-cost',title=cost['note']))
            run_id=m.get('run',{}).get('id') or m.get('turn_id') or f'message-{index}'
            content.append(html.Button('Export AI run',id={'type':'export-ai-run','run':run_id},n_clicks=0,type='button',className='text-button ai-run-export',disabled=not tick_disabled,title='Download this question, reply, calculation trace and measured tokens as JSON. Review before sharing.'))
        bubble=html.Div(content,className=f"bubble {m['role']}")
        children.append(html.Div([portrait("host-portrait host-message-avatar"),bubble],className="host-message-row") if m['role']=='assistant' else bubble)
    if not children:
        children=[html.Div([html.P("Welcome to Crimson Calculus.",className="host-welcome-title"),html.P("I’m Vivienne, your AI host. Let’s make the numbers a little less mysterious. I can show you around, explain a betting system, change and apply your settings, compare systems right here, and help you understand your results. With session sharing on, I can also review your Step 3, practice, and free-play logs."),html.Small("Try asking"),html.P("“Review my latest system practice spins.”"),html.P("“Set my profit target to $300, apply and compare.”"),html.P("“How do I get started?”")],className="chat-starter")]
    if not tick_disabled:
        children.append(html.Div([html.Span(),html.Span(),html.Span()],className="dots",**{"aria-label":"thinking"}))
    return children


@callback(Output("messages","data",allow_duplicate=True),Output("think-tick","disabled",allow_duplicate=True),Output("prompt","disabled",allow_duplicate=True),Output("send","disabled",allow_duplicate=True),Output("host-settings-request","data"),
    Input("think-tick","n_intervals"),State("messages","data"),State("think-tick","disabled"),State("active-scenario","data"),State("session-data","data"),State("share-session","value"),State('practice-data','data'),State('free-data','data'),State('workflow-tabs','value'),State('practice-mode','value'),*[State(k,'value') for k in FIELDS],prevent_initial_call=True,
    running=[(Output("think-tick","disabled",allow_duplicate=True),True,True)])
def think(_n,messages,tick_disabled,config,session,share_session,practice,free_play,view,practice_mode,*draft_values):
    if tick_disabled:
        raise PreventUpdate
    session_context=None
    if "include" in (share_session or []):
        session_context=build_session_context(session,practice,free_play,view,practice_mode)
    settings_context=dict(values=dict(zip(FIELDS,draft_values)) if draft_values else dict(config))
    started=time.time()
    reply=generate(list(messages or []),config,session_context,settings_context)
    finished=time.time()
    reply['run']=dict(id=reply.get('turn_id') or uuid4().hex,
        question=next((m['content'] for m in reversed(messages or []) if m.get('role')=='user'),''),
        model=MODEL,started_at=datetime.fromtimestamp(started,timezone.utc).isoformat(),
        finished_at=datetime.fromtimestamp(finished,timezone.utc).isoformat(),duration_seconds=round(finished-started,3),
        applied_scenario=config,form_fields=settings_context['values'],session_sharing_enabled=session_context is not None)
    messages=list(messages or [])
    messages.append(dict(role="assistant",**reply))
    return messages[-24:],True,False,False,reply.get("settings_update",no_update)


@callback(Output('host-context-status','children'),Input('share-session','value'))
def host_context_status(sharing):
    return ('Session sharing on · Step 3, system practice & free play. Updated when you send.'
            if 'include' in (sharing or []) else 'Session sharing off · New requests exclude session logs.')


@callback(Output('usage-summary','children'),Output('host-usage-status','children'),
          Input('messages','data'),Input('usage-tick','n_intervals'),Input('think-tick','disabled'))
def render_usage(_messages,_tick=0,idle=True):
    u=usage_summary()
    configured=bool(os.getenv('PORTKEY_API_KEY','').strip() or os.getenv('OPENAI_API_KEY','').strip())
    if not configured:label='AI key needed · calculator ready'
    elif not idle:label='Vivienne is working…'
    elif u['available']:label=f"AI ready · {u['turns_remaining']}/{u['turn_limit']} messages left"
    else:label='AI allowance temporarily unavailable'
    availability='Ready for your next message.' if u['available'] else 'Waiting for allowance to free up.'
    if not configured:availability='Configure an AI key, then use Test AI connection in Tools & learning → Setup & status.'
    if configured and u['next_available_at']:
        wait=max(1,int(u['next_available_at']-u['checked_at'])+1)
        duration=f'{wait} seconds' if wait<60 else f'{(wait+59)//60} minutes' if wait<3600 else f'{wait/3600:.1f} hours'
        stamp=datetime.fromtimestamp(u['next_available_at'],timezone.utc).strftime('%b %d, %H:%M UTC')
        availability=f'Next request available in about {duration} ({stamp}), if no new requests start. Finishing an in-flight request may free allowance sooner.'
    details=html.Div([
        html.Strong(availability),
        html.P('Shared demo: this allowance is shared by visitors and its server records can reset when free hosting sleeps or restarts. It is not a durable provider spending cap.') if HOSTED_DEMO else None,
        html.P(f"Messages remaining: {u['turns_remaining']:,} / {u['turn_limit']:,} in a rolling 24 hours."),
        html.P(f"Tokens: {u['used_tokens']:,} counted against allowance · {u['reserved_tokens']:,} reserved for in-flight requests · {u['remaining_tokens']:,} unreserved / {u['token_limit']:,}."),
        html.P(f"Each new message needs room to reserve {u['reservation']:,} tokens. Completed messages normally count measured usage; missing provider usage keeps the reservation until it expires. At most 4 messages may start per minute."),
        html.P(f"Missing-usage allowance hold: {u.get('uncertain_tokens',0):,} tokens. This is a conservative allowance hold, not a measured charge.") if u.get('uncertain_tokens') else None,
        html.P(f"Provider measurements: {u['calls']} model calls · {u['input']:,} input / {u['cached']:,} cached input / {u['output']:,} output tokens. Cached input is included in input."),
        html.Small('Shared local app allowance, not your provider account balance. It frees progressively 24 hours after usage; it does not reset at midnight. Each reply shows a published-rate token estimate; gateway fees, discounts, tax and unreported/cache-write charges are excluded. Roulette calculations use no AI tokens. Refreshes automatically every 30 seconds.')
    ],className='ai-usage-details')
    return details,label


@callback(Output('download-ai-run','data'),Input({'type':'export-ai-run','run':ALL},'n_clicks'),
          State('messages','data'),State('host-settings-receipts','data'),prevent_initial_call=True)
def download_ai_run(clicks,messages,receipts):
    trigger=ctx.triggered_id
    if not any(clicks) or not isinstance(trigger,dict) or not ctx.triggered[0].get('value'):raise PreventUpdate
    payload=export_run(messages,trigger['run'],receipts)
    return dict(content=json.dumps(payload,indent=2,ensure_ascii=False),filename='crimson-calculus-ai-run.json',type='application/json')


@callback(Output('setup-check-result','children'),Input('check-setup','n_clicks'),Input('test-ai-connection','n_clicks'),
          running=[(Output('check-setup','disabled'),True,False),(Output('test-ai-connection','disabled'),True,False)])
def check_setup(_local,_ai):
    result=run_checks(test_ai=ctx.triggered_id=='test-ai-connection')
    return html.Div([
        html.P('Setup checks passed' if result['ready'] else 'Some checks need attention',className='setup-overall'),
        html.Ul([html.Li([html.Strong(row['name']),html.Span(row['status'].upper(),className='setup-badge '+row['status']),html.P(row['detail'])],className='setup-check-row') for row in result['checks']],className='setup-check-list'),
        html.Small('Checked '+result['checked_at']+' · No key values are displayed.'),
        html.P('Connection-test tokens: '+json.dumps(result['ai_test']['usage'])) if result.get('ai_test') else None
    ])


@callback(Output('example-content','children'),Output('example-modal','style'),Output('example-step','data'),
          Output('example-back','disabled'),Output('example-next','disabled'),
          Input('try-example','n_clicks'),Input('example-close','n_clicks'),Input('example-back','n_clicks'),Input('example-next','n_clicks'),
          State('example-step','data'),prevent_initial_call=True)
def navigate_example(open_clicks,close_clicks,back_clicks,next_clicks,step):
    trigger=ctx.triggered_id
    if trigger=='example-close':return no_update,{'display':'none'},0,True,False
    if trigger=='try-example':step=0
    elif trigger=='example-back':step=max(0,int(step or 0)-1)
    elif trigger=='example-next':step=min(2,int(step or 0)+1)
    else:raise PreventUpdate
    return example_view(step),{'display':'flex'},step,step==0,step==2


@callback(Output('download-comparison-report','data'),Input('export-report','n_clicks'),
          State('calculation','data'),State('distribution-strategy','value'),prevent_initial_call=True)
def download_comparison_report(clicks,result,selected):
    if not clicks or not result:raise PreventUpdate
    return dict(content=comparison_report(result,selected),filename=f"crimson-calculus-comparison-{result['id']}.html",type='text/html')


@callback(Output('download-example-report','data'),Input('export-example-report','n_clicks'),prevent_initial_call=True)
def download_example_report(clicks):
    if not clicks:raise PreventUpdate
    result,benchmarks=example_data()
    return dict(content=comparison_report(result,benchmarks=benchmarks),filename='crimson-calculus-guided-example.html',type='text/html')


@callback(Output("download-comparison","data"),Input("export","n_clicks"),State("calculation","data"),prevent_initial_call=True)
def export(n,result):
    if not n or not result:
        raise PreventUpdate
    return dict(content=json.dumps(result,indent=2),filename=f"crimson-calculus-{result['id']}.json",type="application/json")




def system_help(key):
    info=SYSTEMS[key]
    def section(label,text):
        return html.Span([html.Strong(label,className="preview-label"),html.Span(text)],className="preview-section")
    return html.Span([
        section("How it works",info['how']),
        section("Example",info['example']),
        section("Pros"," · ".join(info['pros'])),
        section("Cons / risks"," · ".join(info['cons'])),
        html.Span("Examples use illustrative amounts. Follow the displayed stake and stop at your limits. No system removes the house edge.",className="preview-footnote")
    ],id="system-help-"+key,role="tooltip",className="system-preview")


@callback(Output("system-list","children"),Output("session-settings-label","children"),
          Input("calculation","data"),Input("session-data","data"),State("system-list","children"))
def system_choices(result,data,previous):
    if not result:raise PreventUpdate
    if not isinstance(data,dict):data=None
    selected=(data or {}).get('key') if data and data.get('calculation')==result['id'] else None
    same=bool(previous and previous.get('props',{}).get('data-selected')==(selected or '') and previous.get('props',{}).get('data-calculation')==result['id'])
    return (no_update if same else html.Div([html.Button([
        html.Span({'oneshot':'◆','martingale':'↗','grand_martingale':'♠','flat':'=','dalembert':'+','reverse_dalembert':'−','fibonacci':'φ','paroli':'♣','1326':'♦','even':'◉','dozen':'▦','sixline':'✦','groups':'♠','research':'✧'}.get(r['key'],'♠'),className='system-symbol',**{'aria-hidden':'true'}),
        html.Span([html.Strong(r['label']),system_help(r['key'])],className="system-name"),
        html.Small(f"{r['success']:.2%} session success · "+(f"starts at {money(r['base'])}" if r['base'] else "stake varies")),
        html.Span(SYSTEMS[r['key']]['subtitle'],className='system-risk-tag')
    ],id={"type":"choose-system","key":r['key'],"calculation":result['id']},n_clicks=0,
      className="system-option"+(" selected" if selected==r['key'] else ""),
      **{"aria-pressed":selected==r['key'],"aria-describedby":"system-help-"+r['key'],"aria-label":r["label"]+f" {r['success']:.2%} session success · "+(f"starts at {money(r['base'])}" if r["base"] else "stake varies")}) for r in result['rows']],className="system-options",**{"data-selected":selected or "", "data-calculation":result["id"]})),(
      f"Last applied session · {money(result['scenario']['bankroll'])} bankroll · +{money(result['scenario']['target'])} target · {result['scenario']['spins']} spins · {WHEELS[result['scenario']['wheel']]}")


@callback(Output("session-data","data"),Output("session-notice","children"),
          Input({"type":"choose-system","key":ALL,"calculation":ALL},"n_clicks"),
          Input({"type":"record-spin","index":ALL,"token":ALL},"n_clicks"),
          Input("session-undo","n_clicks"),Input("session-reset","n_clicks"),Input("session-clear","n_clicks"),Input("calculation","data"),
          Input({"type":"record-number","token":ALL},"n_clicks"),Input({"type":"winning-number","token":ALL},"n_submit"),Input({"type":"even-choice","token":ALL},"value"),
          State({"type":"winning-number","token":ALL},"value"),State("session-data","data"),prevent_initial_call=True)
def update_simple_session(_choices,_results,_undo,_reset,_clear,result,_number_clicks,_number_submits,even_choices,winning_numbers,data):
    trigger=ctx.triggered_id
    if trigger=="session-clear":return None,"Saved session cleared. Choose a system to start again."
    if trigger=="calculation":
        if data and result:
            try:
                restored=validate_saved_session(data)
                return restored,("Saved session resumed. Bankroll, recorded results, and Undo history restored." if data.get('calculation')==result['id'] else
                                 "Comparison updated. Your current tracker keeps its original settings and log. Choose a system to begin a new tracker.")
            except (ValueError,TypeError,KeyError,ArithmeticError) as exc:
                return no_update,"Saved session could not be resumed: "+str(exc)
        return None,"Choose a system to see your first bet."
    if not result:raise PreventUpdate
    if isinstance(trigger,dict) and trigger.get('type')=='choose-system':
        if not any(_choices):raise PreventUpdate
        if trigger.get('calculation')!=result['id']:
            return no_update,"Comparison changed. Wait for the refreshed system cards, then choose a system again."
        row=next((r for r in result['rows'] if r['key']==trigger['key']),None)
        if not row:raise PreventUpdate
        previous_choice=data.get('even_bet') if isinstance(data,dict) else None
        even_bet=previous_choice if isinstance(previous_choice,str) and previous_choice in EVEN_CHOICES else 'red'
        return dict(version=1,key=row['key'],base=row['base'],history=[],calculation=result['id'],scenario=result["scenario"],saved_at=time.time(),even_bet=even_bet),"System selected. Start with the bet below."
    if not data:raise PreventUpdate
    # A comparison is a new scenario, not a rewrite of a game in progress.
    if data['calculation']!=result['id']:result=compare(Scenario(**data['scenario']))
    token=state_token(data)
    data=dict(data,history=list(data['history']),saved_at=time.time())
    if trigger=="session-reset":
        data['history']=[]
        return data,"System restarted from your session settings."
    if trigger=="session-undo":
        if not data['history']:raise PreventUpdate
        removed=data['history'].pop()
        data['even_bet']=removed.get('even_bet','red')
        return data,"Last result undone. Your previous bet and session state are restored."
    if isinstance(trigger,dict) and trigger.get('type')=='even-choice':
        choice=(even_choices or [None])[0]
        if trigger['token']!=token or choice==data.get('even_bet','red'):raise PreventUpdate
        if choice not in EVEN_CHOICES:return no_update,"Choose one of the six even-money bets."
        current=session_snapshot(Scenario(**result['scenario']),data['key'],data['base'],data['history'],with_stats=False,even_bet=data.get('even_bet','red'))
        if not supports_even_choice(data['key'],current):raise PreventUpdate
        data['even_bet']=choice
        return data,f"Next even-money wager uses {EVEN_CHOICES[choice]}. Earlier log rows are unchanged."
    if isinstance(trigger,dict) and trigger.get('type') in ('record-number','winning-number'):
        if not any(_number_submits if trigger['type']=='winning-number' else _number_clicks) or trigger['token']!=token:raise PreventUpdate
        try:
            value=(winning_numbers or [None])[0]
            if value is None:raise ValueError('Enter the winning number first.')
            data['history']=record_number(Scenario(**result['scenario']),data['key'],data['base'],data['history'],value,even_bet=data.get('even_bet','red'))
            return data,f"Recorded wheel result {data['history'][-1]['winning_number']}: {money(data['history'][-1]['net'])}. Autosaved."
        except (ValueError,TypeError,KeyError,ArithmeticError) as exc:return no_update,str(exc)
    if isinstance(trigger,dict) and trigger.get('type')=='record-spin':
        if not any(_results) or trigger['token']!=token:raise PreventUpdate
        try:
            data['history']=session_record(Scenario(**result['scenario']),data['key'],data['base'],data['history'],trigger['index'],even_bet=data.get('even_bet','red'))
            return data,f"Recorded {money(data['history'][-1]['net'])}. Next step updated."
        except (ValueError,TypeError,KeyError) as exc:return no_update,str(exc)
    raise PreventUpdate


def risk_preview(s,row,started):
    profile=risk_profile(s,row)
    example=profile['example']
    example_view=None
    if example and example['stop']=='blocked':
        example_view=html.P([
            html.Strong("One possible full-loss path: "),
            f"after {example['losses']} consecutive full losses, {money(example['bankroll'])} cash remains. "
            f"The next required wager is {money(example['required'])}. It is blocked by "+
            " and ".join(example['reasons'])+
            f" (table maximum {money(s.maximum)}; remaining loss allowance {money(example['available'])}). "
            "The plan stops instead of shrinking that wager."
        ],className="risk-example")
    elif example and example['stop']=='one-shot':
        example_view=html.P(f"After one full loss, {money(example['bankroll'])} remains, but one-shot still ends the session.",className="risk-example")
    elif example:
        example_view=html.P(f"One possible full-loss path records {example['losses']} losses and leaves {money(example['bankroll'])}; it ends at the {example['stop']}.",className="risk-example")
    children=[
        html.P("BEFORE YOUR FIRST SPIN" if not started else "SYSTEM RISK PROFILE",className="eyebrow"),
        html.H3(profile['kind']),
        html.Details([html.Summary('How it works · example · pros and cons'),
            html.P(SYSTEMS[row['key']]['how']),
            html.P(SYSTEMS[row['key']]['example'],className='risk-example'),
            html.Div([html.Div([html.H4('Pros'),html.Ul([html.Li(x) for x in SYSTEMS[row['key']]['pros']])]),html.Div([html.H4('Cons / risks'),html.Ul([html.Li(x) for x in SYSTEMS[row['key']]['cons']])])],className='pros-cons'),
            html.Small(EXAMPLE_NOTE)],className='beginner-details'),
        html.P(profile['pattern']),
        html.P(profile['stakes']),
        html.Div([metric("Reach target · entire session",f"{row['success']:.4%}"),
                  metric("Average final net",money(row['mean'])),
                  metric("Maximum modeled loss",money(row['max_loss'])),
                  metric("Worst 5% final average",money(row['worst5']))],className="risk-metrics"),
        html.P(f"First wager only: {profile['opening_win']:.2%} chance of net profit · {profile['opening_loss']:.2%} chance of net loss"+
               (f" · {profile['opening_even']:.2%} break even" if profile['opening_even'] else "")+
               ". These are different from the whole-session target probability.",className="small-note"),
        html.H4("Why cash can remain when the system stops"),
        html.P(f"The app stops before a required wager would exceed the {money(s.maximum)} table maximum or the remaining loss allowance. "
               f"Your loss limit protects {money(s.bankroll-s.loss_limit)} of the starting bankroll. "
               f"Cash below the required stake, the {money(s.minimum)} position minimum, or a legal chip increment may be unusable. "
               f"The session also ends at the +{money(s.target)} profit target or after {s.spins} spins."),
        example_view,
        html.P("Examples use consecutive full losses, not every possible losing path. French zero half-losses can follow a different path."
               if s.wheel=='french' else "The full-loss example is one possible path, not a prediction or the chance of a streak anywhere in the session.",className="small-note") if example else None,
        html.Strong("A high target-reaching probability does not mean frequent winning spins, a safe system, or a positive average result.")
    ]
    if started:return html.Details([html.Summary("System risk profile · starting-session figures"),html.Div(children,className="risk-body")],className="system-risk-profile")
    return html.Section(children,className="system-risk-profile risk-body",**{"aria-label":"Risk information before starting"})


@callback(Output("session-result","children"),Output("session-undo","disabled"),Output("session-reset","disabled"),Output("session-save-status","children"),
          Input("session-data","data"),Input("calculation","data"))
def render_simple_session(data,result):
    if not data or not result:
        return html.P("Choose a system in step 2. Its next bet and result buttons will appear here.",className="empty-state"),True,True,"Sessions save automatically in this browser once you choose a system."
    try:
        # Match the exact browser store that update_simple_session receives.
        # Replay can rebuild 95 as 95.0 after a French half-refund; use replayed
        # data for the display without changing the event's originating token.
        control_token=state_token(data)
        data=validate_saved_session(data)
        different=data['calculation']!=result['id']
        s=Scenario(**data['scenario'])
        if different:result=compare(s)
        row=next(r for r in result['rows'] if r['key']==data['key'])
        r=session_snapshot(s,data['key'],data['base'],data['history'],even_bet=data.get('even_bet','red'))
    except (ValueError,TypeError,KeyError,ArithmeticError,StopIteration):
        return (html.P("This saved session could not be resumed. Use Clear saved session above, or choose a system in Step 2 to start a new tracker.",className="error"),
                True,True,"The unreadable save has been kept until you choose how to replace it.")
    losses=policy_loss_stats(data['history'])
    status=html.Div([metric("Bankroll",money(r['bankroll'])),metric("Session profit",money(r['net_profit'])),
                    metric("Spins left",str(r['spins_left']))],className="metric-grid compact live-status")
    if r.get('stop'):
        action=html.Div([html.H3("Stop here"),html.P(r['stop'])],className="next-action stop-action")
    else:
        choices=[]
        for i,o in enumerate(r['outcomes']):
            label=o.get('label') or ('Win' if o['net']>0 else 'Loss' if o['net']<0 else 'Break even')
            choices.append(html.Button([html.Strong(label),html.Span(money(o['net']))],
                          id={"type":"record-spin","index":i,"token":control_token},n_clicks=0,
                          className="record-button "+("record-win" if o['net']>0 else "record-loss")))
        action=html.Div([
            html.P("NEXT BET",className="eyebrow"),
            html.Fieldset([html.Legend("Choose your even-money bet"),
                dcc.RadioItems(id={"type":"even-choice","token":control_token},
                    options=[{"label":label,"value":key} for key,label in EVEN_CHOICES.items()],
                    value=data.get('even_bet','red'),className="even-choice-options",inline=True),
                html.Small("Choose before the next spin. All six have equal odds; the winning numbers differ. Earlier bets stay unchanged in your log.")
            ],className="even-choice-picker") if supports_even_choice(data['key'],r) else None,
            html.H3(f"Wager {money(r['total'])} total"),
            html.Ul([html.Li([html.Strong(money(e['amount'])+" on "+position_name(e['numbers'])),
                             html.Small(placement_instruction(e['numbers']))]) for e in r['entries']],className="bet-instructions"),
            html.Div([html.Label(["Winning wheel number",
                dcc.Input(id={"type":"winning-number","token":control_token},type="text",placeholder="0–36"+(" / 00 / 000" if s.wheel=="triple" else " / 00" if s.wheel=="double" else ""),maxLength=3,inputMode="numeric",n_submit=0)],className="number-label"),
                html.Button("Record number",id={"type":"record-number","token":control_token},n_clicks=0,className="primary"),
                html.Small("Calculates every displayed wager automatically. Use 00 or 000 exactly as shown on the wheel.")],className="number-entry"),
            html.P("Or record the net result directly:",className="result-prompt"),
            html.Div(choices,className="record-buttons"),
            html.Small("Amounts are net profit or loss on this spin. Choose the matching payout when more than one win is possible.")
        ],className="next-action")
    details=html.Section([html.H3("Session odds, losses & explanation"),html.Div([
        html.P(DESCRIPTIONS[data['key']]),
        metric("Reach target over all remaining spins",f"{r['stats']['success']:.4%}"),
        html.P("This covers the rest of the session, not just the next spin. Spins remain independent. A high success rate can still involve long losing runs and large losses.",className="small-note"),
        html.Div([metric("Projected final average",money(r['stats']['mean'])),metric("Worst 5% final average",money(r['stats']['worst5'])),
                  metric("Consecutive losses",str(losses['streak'])),metric("Total lost on losing spins",money(losses['gross_losses'])),
                  metric("Loss sequence probability",f"{losses['streak_probability']:.6%}" if losses['streak'] else "No current streak")],className="metric-grid compact"),
        html.P("Loss-sequence odds multiply each suggested wager’s loss probability along this recorded path. This is not the chance of a streak anywhere in the session or over every possible losing path. Break-even spins end the streak; Undo reverses recorded results.",className="small-note"),
        guide_button(row,"simple"),
        table(["Net this spin","Next-spin probability"],[[money(o['net']),f"{o['probability']:.4%}"] for o in r.get('outcomes',[])])
    ],className="session-details")],className="session-more")
    log=session_log(s,data['key'],data['base'],data['history'])
    log_view=html.Section([html.H3(f"Session log · {len(log)} recorded "+("spin" if len(log)==1 else "spins")),html.Div([
        html.Div([html.P("Each row records the wagers shown before that spin. Undo removes the latest row. Number entries show the pocket; result-button entries do not invent a winning number.",className="small-note"),
                  html.Button("Export session log (CSV)",id="export-session-log",n_clicks=0,className="secondary",disabled=not bool(log))],className="session-log-heading"),
        table(["Spin","Bets placed","Total wager","Result","Spin net","Bankroll","Running profit","Spins left"],[
            [r['spin'],html.Ul([html.Li(f"{money(b['amount'])} on {b['position']}") for b in r['bets']],className="log-bets"),
             money(r['total_wager']),
             (f"Pocket {r['winning_number']} · {r['result']}" if r['winning_number'] is not None else r['result']+" · result button"),
             money(r['net']),money(r['bankroll']),money(r['profit']),r['spins_left']] for r in log],
             class_name="session-log-table") if log else html.P("No spins recorded yet. Your log will appear here after the first result.",className="empty-state"),
        html.P("CSV includes the system, roulette rules, and session limits for your report. All monetary columns are in USD. Downloaded exports are snapshots; export again after corrections.",className="small-note")
    ],className="session-log-body")],className="session-log")
    preserved=html.P(f"This tracker keeps its original {money(s.bankroll)} bankroll, +{money(s.target)} target and {s.spins}-spin limit ({WHEELS[s.wheel]}). The comparison uses new settings. Choose a system in Step 2 to start a new tracker.",className='notice') if different else None
    return html.Div([html.H2(row['label']),preserved,status,html.Div(risk_preview(s,row,bool(data['history'])),className="session-risk-pane"+(" before-first-spin" if not data['history'] else "")),action,log_view,details]),not bool(data['history']),False,"Autosaved locally · resumes automatically in this browser · Undo history included"


@callback(Output("download-session-log","data"),Input("export-session-log","n_clicks"),
          State("session-data","data"),prevent_initial_call=True)
def export_session_log(n,data):
    if not n or not data or not data.get('history'):raise PreventUpdate
    content=session_log_csv(data)
    return dict(content="\ufeff"+content,filename=f"crimson-calculus-session-{data['key']}-{data['calculation']}.csv",
                type="text/csv;charset=utf-8")


@server.get("/health")
def health():
    return {"status":"ok","app":APP_TITLE,"model":MODEL}


if __name__=="__main__":
    app.run(host="127.0.0.1",port=PORT,debug=False,use_reloader=False)
