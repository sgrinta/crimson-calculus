"""Always-mounted, modeless AI host UI; no session or wager state lives here."""
from dash import html

PORTRAIT = '/assets/ai-host-selected-blonde.png'


def portrait(class_name='host-portrait'):
    return html.Span(html.Img(src=PORTRAIT, alt='', draggable='false'), className=class_name, **{'aria-hidden':'true'})


def host_launcher():
    return html.Button([
        portrait('host-portrait host-launcher-portrait'),
        html.Span([html.Strong('Vivienne'),html.Small('Your AI host & analyst')],className='host-launcher-label'),
    ],id='host-launcher',type='button',className='host-launcher',
       **{'data-host-toggle':'true','aria-label':'Open Vivienne, AI host and analyst','aria-controls':'host-panel','aria-expanded':'false'})


def host_panel(analyst):
    return html.Aside([
        html.Header([
            portrait(),
            html.Div([html.P('AI HOST & ANALYST',className='eyebrow'),html.H2('Vivienne',id='host-panel-title')],className='host-heading'),
            html.Button('×',id='host-close',type='button',className='host-close',**{'data-host-close':'true','aria-label':'Minimize Vivienne, AI host and analyst'}),
        ],className='host-panel-header'),
        analyst,
    ],id='host-panel',className='host-panel',hidden=True,role='dialog',
       **{'aria-modal':'false','aria-labelledby':'host-panel-title'})


def host_tour():
    return html.Details([
        html.Summary('New here? A quick tour'),
        html.Div([
            html.P([html.Strong('What is Crimson Calculus? '),
                    'Crimson Calculus is a roulette learning and strategy comparison app. Explore how different betting systems affect your chance of reaching a profit target within your budget and limits, while seeing average results and the risk of losses.']),
            html.P('The calculator works out the odds and payouts. Practice / demo lets you try roulette with virtual money, and the session logs track each spin. Vivienne, your AI host and analyst, explains the results and can review your shared logs.'),
            html.P('You can ask Vivienne to change your Step 1 settings, such as “Set my profit target to $300.” She updates the fields and shows what changed. Say “Apply and compare” to apply them and compare systems directly in this chat. You can also combine both: “Set my target to $300, apply and compare.” Existing games keep their original settings and logs.'),
            html.P('Use it to understand the tradeoffs: a high chance of reaching a target can still come with large losses. No betting system removes the house edge or predicts the next spin.'),
            html.P(html.Strong('How to get started')),
            html.Ol([
                html.Li([html.Strong('Set your limits. '),'Choose the wheel, bankroll, target and stopping limits in Step 1.']),
                html.Li([html.Strong('Choose a system. '),'Compare the tested systems in Step 2 and read their tradeoffs.']),
                html.Li([html.Strong('Follow or practice. '),'Record results in Step 3, or try virtual spins in Practice / demo.']),
            ]),
            html.P('This panel stays with you as you move between tabs. Minimize it whenever you need the full table.'),
        ],className='host-tour-body'),
    ],className='host-tour')


def host_hub():
    return html.Section([
        html.Div([
            portrait('host-portrait host-hub-portrait'),
            html.Div([html.P('YOUR AI HOST',className='eyebrow'),html.H2('Meet Vivienne.'),
                      html.P('Get help with the app, understand a system, or explore the calculation behind a result. Vivienne is available from the portrait button on every tab.')]),
        ],className='host-hub-intro'),
        html.Button('Chat with Vivienne ↗',id='host-open-tools',type='button',className='primary',
                    **{'data-host-open':'true','aria-controls':'host-panel','aria-expanded':'false'}),
        html.P('One conversation follows you around the app. Opening or minimizing it keeps your session, wagers and form drafts in place.',className='small-note'),
    ],className='panel host-hub')
