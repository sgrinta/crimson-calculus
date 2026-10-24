"""A prepared, illustrated walkthrough; opening it never calls AI or changes a session."""
from dash import html
import json
from host_ui import PORTRAIT


PAGES = [{'key': 'welcome',
  'nav': 'Welcome',
  'title': 'Welcome to Crimson Calculus.',
  'intro': 'Crimson Calculus helps you understand roulette odds, compare betting systems, and explore their risks before you play. Its calculator uses your budget, target, and limits to estimate whole-session results, while practice mode lets you experiment with virtual money. I’m Vivienne, your guide to the app. Let’s start with the main shortcuts.',
  'image': 'welcome.jpg',
  'alt': 'Crimson Calculus home page with the main session steps and practice tools.'},
 {'key': 'settings',
  'nav': 'Session settings',
  'title': 'Step 1 · Set your limits.',
  'intro': 'Every comparison starts with your session settings. I’ll explain how your budget, profit target, stopping limits, and wheel rules shape the results, then show you how to apply them. These settings define what success means for your session.',
  'image': 'settings.jpg',
  'alt': 'Session settings showing bankroll, target, loss limit, table limits, chip size, spin limit, and '
         'wheel rules.'},
 {'key': 'systems',
  'nav': 'Choose a system',
  'title': 'Step 2 · Compare, then choose.',
  'intro': 'Here you can compare the systems tested under the same settings and choose one to follow. I’ll show you how to read the cards, understand their starting stakes and session-success estimates, and find explanations of how each system works.',
  'image': 'systems.jpg',
  'alt': 'The system selection cards with success probabilities, starting stakes, and short descriptions.'},
 {'key': 'tracker',
  'nav': 'Follow the system',
  'title': 'Step 3 · Record one spin at a time.',
  'intro': 'Once you choose a system, this screen turns it into instructions for the next spin. I’ll show you how to choose an eligible bet, read the wager, and record the outcome so your bankroll, remaining spins, and next action update together.',
  'image': 'tracker.jpg',
  'alt': 'Step 3 with a selected system, next wager instructions, winning-number entry, and result '
         'controls.'},
 {'key': 'logs',
  'nav': 'Logs & resume',
  'title': 'Keep a record of what happened.',
  'intro': 'Your session log helps you review each bet and result instead of relying on memory. I’ll explain the running bankroll and profit columns, how autosave lets you resume in this browser, and how to export a record for your project.',
  'image': 'logs.jpg',
  'alt': 'A session log showing spin numbers, itemized bets, outcomes, running bankroll, profit, and CSV '
         'export.'},
 {'key': 'practice',
  'nav': 'Practice a system',
  'title': 'Try the system on the practice wheel.',
  'intro': 'Practice mode lets you follow a betting system with virtual money and independent random wheel results. I’ll show you how to spin, read the outcome, and follow the updated instructions. Practice has its own log and bankroll, separate from Step 3.',
  'image': 'practice.jpg',
  'alt': 'System practice with the illustrated roulette wheel, recent pockets, next wagers, and session '
         'statistics.'},
 {'key': 'free-play',
  'nav': 'Free play',
  'title': 'Build your own virtual bet slip.',
  'intro': 'Free play puts you in charge of the bets. I’ll show you where to click for numbers, splits, corners, streets, and outside bets, and how to read the chance of net profit for your combined wagers on the next spin.',
  'image': 'free-play.jpg',
  'alt': 'Free-play roulette table with number, split, corner, street, and outside betting positions.'},
 {'key': 'tools',
  'nav': 'Tools & learning',
  'title': 'Understand the bets and the mathematics.',
  'intro': 'These tools help you explore why a system behaves the way it does. I’ll introduce the recovery calculator, combination builder, and illustrated glossary so you can investigate growing wagers, overlapping bets, and unfamiliar roulette terms.',
  'image': 'tools.jpg',
  'alt': 'Roulette terms and diagrams explaining a bet using the app’s illustrated table.'},
 {'key': 'host',
  'nav': 'Ask Vivienne',
  'title': 'Your AI host stays close by.',
  'intro': 'You can open my panel from any tab for help with the app and its results. I’ll show you how to ask a question, control session sharing, request settings changes, and inspect the calculations and estimated AI cost behind a reply.',
  'image': 'host.jpg',
  'alt': 'Vivienne’s host panel with session-sharing controls and the chat composer.'}]


def control(title, explanation, box):
    """Screenshot coordinates are percentages of the original image, including its edges."""
    return dict(title=title, explanation=explanation, box=box)


CONTROLS = {
    'welcome': [
        control('Tutorial', 'This button opens our illustrated tour. Next highlights one control at a time; Back revisits the previous one. These screenshots are examples, so exploring them never changes your session.', [45,58.6,11.5,9]),
        control('Set your limits', 'This shortcut takes you to Step 1. Start there to choose your wheel, budget, profit target, and stopping rules before comparing systems.', [31.5,60.2,11.6,5.9]),
        control('Open practice room', 'This opens Practice / demo. You can follow a system on the virtual wheel or choose your own bets in Free play. Both keep their bankrolls separate from Step 3.', [3.7,58.8,26,8.6]),
    ],
    'settings': [
        control('Bankroll', 'Enter the money available at the start of your session. For example, $1,000 means you begin with $1,000. Use the minus/plus buttons or type directly in the field.', [2.3,21,23,8]),
        control('Profit target', 'This is the net gain you want before stopping—not the final bankroll. A $200 target with a $1,000 bankroll means the goal is at least $1,200.', [26.7,21,23,8]),
        control('Loss limit', 'Set the most of your starting bankroll you will allow yourself to lose. A $300 loss limit protects the remaining $700 of a $1,000 bankroll. A system may stop earlier if its next wager will not fit.', [51.2,21,23,8]),
        control('Minimum bet', 'This minimum applies to each occupied betting position. With a $5 minimum, a combination of three separate positions needs at least $5 on each, or $15 total.', [75.8,21,22,8]),
        control('Maximum wager', 'This caps the combined stake for one spin. Two $300 bets require a $600 total maximum. Progressions stop if their next required wager exceeds this limit.', [2.3,40.5,23,8]),
        control('Chip size', 'This sets the increment for legal wagers. With $5 chips, use $5, $10, $15, and so on. The number buttons change by 1 normally, 10 with Ctrl/⌘, 100 with Shift, or 1,000 with both; the final wager must still fit the chip size.', [26.7,40.5,23,8]),
        control('Spin limit', 'Choose the maximum number of spins for the session. The success probability is calculated for reaching your target within this horizon and the other limits, not just for winning the next spin.', [51.2,40.5,23,8]),
        control('Wheel / rules', 'Choose European single zero, French La Partage, American double zero, or triple zero. French mode refunds half an eligible even-money stake when zero lands. Read the rules summary below the fields.', [75.8,40,22,9]),
        control('Apply settings & continue', 'This runs the local calculator with your entered settings, then opens the system comparison. Wait for it to finish before choosing a system. Changing a field alone does not apply a new scenario.', [2.3,75,30,9]),
    ],
    'systems': [
        control('System name', 'Hover over the name for an explanation, example, pros, and risks. Martingale doubles after a loss and resets after a win; it can use any selected even-money box.', [36,72,28,9]),
        control('Session success and starting stake', 'This percentage is the modeled chance of reaching your target before the session ends. “Starts at” is the best starting amount tested for those settings. Compare average results and downside in the Compare systems sub-tab too.', [36,79,28,9]),
        control('Choose a system card', 'Click a card to select that system and open Step 3. The chosen card is crimson. Choosing another system starts a fresh tracker, so export a log you want to keep first.', [34,70,32,30]),
        control('Custom optimized betting plan', 'This plan is generated by the app. It can change bets as bankroll and remaining spins change. “Best” applies only to the combinations tested; it is not a prediction or proof of a global optimum.', [0.5,0.5,31.5,34]),
    ],
    'tracker': [
        control('Choose your even-money bet', 'For a compatible system, select red, black, odd, even, low (1–18), or high (19–36) before the next spin. Their odds are equal on a given wheel, but their winning numbers differ. Earlier log rows stay unchanged.', [3,10.5,94,16]),
        control('Next wager instructions', 'Place all listed wagers together for one spin. This example says $30 on Red. The amount can change after each recorded result, especially in a recovery system.', [3,29,88,16]),
        control('Winning wheel number', 'Type the pocket that actually won: 0–36, plus 00 or 000 on the appropriate wheel. Preserve the zeros exactly. This lets the calculator settle every displayed bet, including overlapping bets.', [3.2,54.5,18,9]),
        control('Record number', 'Click here after entering the winning pocket. It records one spin, settles the displayed wagers, and updates bankroll, profit, spins remaining, and the next instruction.', [21.5,54.5,22,9]),
        control('Win result button', 'Use this alternative when the displayed net payout matches your result. It records the amount shown without inventing a winning pocket. Use either the number entry or a result button for that spin, not both.', [3,77,17,15]),
        control('Loss result button', 'Use this when the displayed net loss matches the spin. If you click the wrong result, Undo last result at the top of Step 3 reverses it. A blocked next wager may end the system before your bankroll reaches zero.', [23,77,17,15]),
    ],
    'logs': [
        control('Each recorded spin', 'Each row shows the wagers placed before that spin and its result. Here the first $30 Red bet lost on 2; the second $60 Red bet won on 1. Undo removes the latest row.', [0.5,52,99,29]),
        control('Bankroll and running profit', 'Bankroll is the money left after that result. Running profit subtracts the starting bankroll. In this example, $1,030 is a $30 profit from a $1,000 start. Sessions autosave in this browser.', [66,40,23,41]),
        control('Export session log (CSV)', 'This downloads the current log for your project, including session settings and numeric money columns. Practice and free play have separate export tabs labeled as virtual play. Export again after corrections to get an updated file.', [78,22,22,12]),
    ],
    'practice': [
        control('Spin wheel', 'After you choose a system and start a practice session, this button places its displayed virtual wagers and animates one independent random result. The app settles the spin automatically; no real money is used.', [3.4,59.5,34,7]),
        control('Practice result', 'This shows the settled pocket and net gain or loss for the latest spin. The small pocket chips beneath it show recent results. Earlier pockets do not make a future number due.', [15,50,27,7]),
        control('Even-money box', 'Choose which eligible box the next practice wager uses. Changing it affects future spins; it does not rewrite previous bets or results.', [45.5,35.8,54,16]),
        control('Remaining-session probability', 'This is the calculator’s chance of reaching the target over all remaining spins while following this system. It is different from the next spin’s winning chance, and a high value can still involve severe losses.', [73,17.5,26,15]),
        control('Next practice bet', 'Read the new stake after every result. The example lost $30 and now calls for $60. Undo practice spin and Practice log & export are above this play area, so you can revisit and document the experiment.', [45.5,54,54,45]),
    ],
    'free-play': [
        control('A single number', 'In Free play, set the amount to add, then click a number to put that amount on it. A straight-up bet covers one pocket and pays 35:1 net if it wins. Every click adds to the bet slip.', [9.4,36,6.8,10.5]),
        control('A split between numbers', 'Click the dividing line between two adjacent numbers to cover both with one wager. This highlighted boundary is between 1 and 4. A winning split pays 17:1 net.', [15.5,38.5,2.5,6]),
        control('A corner intersection', 'Click the intersection of four adjacent squares for a corner. This example covers 1, 2, 4, and 5 with one $5 stake. A winning corner pays 8:1 net.', [15.2,34.3,3,4.2]),
        control('A street label', 'Click the 1–3 label along the bottom edge to cover that row of three numbers with one wager. Each street has its own label and pays 11:1 net if it wins.', [9.3,46.5,7,9]),
        control('An outside even-money box', 'Click Red, Black, Odd, Even, low, or high to add the chosen amount to that box. All occupied positions settle together. Review your itemized slip before using Spin with my bets.', [34.8,64.4,15.1,9.3]),
        control('A dozen box', 'This covers 1–12 with one wager and pays 2:1 net. Free play allows combinations of the available bets. Its displayed chance of net profit applies to the current spin; future manual bets are unspecified, so it has no full-session success estimate.', [3.5,55.5,31.5,9]),
    ],
    'tools': [
        control('Recovery calculator tab', 'Open this tool to inspect a sequence of wagers after losses. It shows how stakes grow and the first required wager blocked by the limits, helping explain why a system might stop with money left.', [5,21,21,7]),
        control('Build a combination tab', 'This lets you combine supported positions and evaluate repeating that portfolio. Read the supported wheel/layout notes and remember that the maximum applies to the total stake.', [26,21,21,7]),
        control('An alphabetized term', 'In Roulette terms, hover, focus, or tap a dotted term for its definition. The list includes betting systems and wheel types as well as bets. Here, Corner opens an explanation and diagram.', [47.3,48,5.6,4.2]),
        control('The definition diagram', 'Use the highlighted squares and chip marker to see which numbers a wager covers and where to place it. The × closes this definition. These diagrams explain placement; they do not predict outcomes.', [53.4,1,39.3,82]),
    ],
    'host': [
        control('New here? A quick tour', 'This gives a short description of Crimson Calculus and the three main steps. Use the main-page Tutorial button whenever you want this illustrated walkthrough again.', [4,25,91,4]),
        control('Session sharing & AI details', 'Expand this section to control what context is shared and see AI model/usage details. The small status line below tells you whether fresh session logs will accompany your next message.', [4,30,91,4]),
        control('Share session logs switch', 'When checked, your next message includes replay-validated snapshots of Step 3, system practice, and free play for the configured AI provider. Turn it off to exclude fresh logs. Earlier conversation text may still mention previously shared details.', [3.2,35,5,3.5]),
        control('Message Vivienne', 'Type a question here, such as “Why did my Step 3 system stop?” or “Set my target to $300, apply and compare.” I can edit and apply session settings and run the comparison. Undo settings reverses my latest settings change when no newer edits conflict. Existing game histories keep their own limits. Enter sends; Shift+Enter adds a line.', [4,82,72,10]),
        control('Send', 'Send submits your question and enabled context to the AI. The calculator provides the numerical results, while I explain them. Expand “See the calculations” under a reply to inspect the tools used. Each reply shows an estimated AI token cost and an Export AI run button for your project evidence. I cannot place real wagers.', [76,82,20,10]),
        control('Minimize Vivienne', 'The × minimizes my panel. Your conversation, draft, and session stay in place; click my portrait on any tab to return. This prepared tutorial itself makes no AI requests.', [88.5,2.5,8,5]),
    ],
}


def tutorial_button():
    return html.Button('Tutorial', id='open-tutorial', type='button', className='hero-tutorial',
                       **{'data-tutorial-open': 'true', 'aria-haspopup': 'dialog', 'aria-controls': 'tutorial-dialog'})


def tutorial_dialog():
    total = sum(len(CONTROLS[p['key']]) for p in PAGES)
    return html.Dialog([
        html.Header([
            html.Div([html.P('VIVIENNE’S GUIDED TOUR', className='eyebrow'),
                      html.H2('Let me show you around.', id='tutorial-title'),
                      html.P('Next highlights one control at a time. Example screens only; your session stays in place.', id='tutorial-description')]),
            html.Button('×', type='button', className='tutorial-close', **{'data-tutorial-close': 'true', 'aria-label': 'Close tutorial'}),
        ], className='tutorial-header'),
        html.Div([
            html.Aside([
                html.Div(html.Img(src=PORTRAIT, alt='Vivienne, your fictional AI host, in a black evening gown with a crimson wrap.'), className='tutorial-host-image'),
                html.Div([html.Strong('Vivienne'), html.Span('Your AI host & analyst'),
                          html.P('I’ll explain the highlighted control. Use Next to follow along, or choose a chapter.')], className='tutorial-host-caption'),
            ], className='tutorial-host-column'),
            html.Div([
                html.Nav([html.Button([html.Span(f'{i+1:02d}', **{'aria-hidden': 'true'}), page['nav']], type='button',
                                      **{'data-tutorial-step': str(i), 'aria-controls': 'tutorial-page-'+page['key'],
                                         **({'aria-current': 'step'} if i == 0 else {})}) for i, page in enumerate(PAGES)],
                         className='tutorial-nav', **{'aria-label': 'Tutorial chapters'}),
                html.Div([html.Section([
                    html.P(page['title'], className='tutorial-chapter-title'),
                    html.P(page['intro'], className='tutorial-chapter-intro'),
                    html.Div([
                        html.P('VIVIENNE EXPLAINS · 1 OF '+str(len(CONTROLS[page['key']])), className='tutorial-speaker'),
                        html.H3(CONTROLS[page['key']][0]['title'], tabIndex=-1, className='tutorial-control-title'),
                        html.P(CONTROLS[page['key']][0]['explanation'], className='tutorial-control-explanation'),
                    ], className='tutorial-guidance', role='status', **{'aria-live': 'polite', 'aria-atomic': 'true'}),
                    html.Figure([
                        html.Div([
                            html.Img(src='/assets/tutorial/'+page['image'], alt=page['alt']),
                            html.Span(html.Span('1', className='tutorial-spotlight-number'), className='tutorial-spotlight', **{'aria-hidden': 'true'}),
                        ], className='tutorial-screenshot-stage'),
                        html.Figcaption([
                            html.Span('Example screenshot · Highlighted controls are not live buttons. '),
                            html.A('View full size ↗', href='/assets/tutorial/'+page['image'], target='_blank', rel='noopener noreferrer'),
                        ]),
                    ]),
                    html.Div([html.Span(**{'data-control-title': item['title'],
                                          'data-control-explanation': item['explanation'],
                                          'data-control-box': json.dumps(item['box'])}) for item in CONTROLS[page['key']]],
                             hidden=True, className='tutorial-control-data'),
                    *([html.Button('Close tour & ask Vivienne ↗', type='button', className='secondary',
                                   **{'data-tutorial-close': 'true', 'data-host-open': 'true', 'aria-controls': 'host-panel'})] if page['key'] == 'host' else []),
                ], id='tutorial-page-'+page['key'], hidden=i != 0, className='tutorial-page') for i, page in enumerate(PAGES)], className='tutorial-content'),
            ], className='tutorial-workspace'),
        ], className='tutorial-body'),
        html.Footer([
            html.Span(f'Control 1 of {total} · Welcome', id='tutorial-progress'),
            html.Div([html.Button('← Back', id='tutorial-back', type='button', disabled=True),
                      html.Button('Next →', id='tutorial-next', type='button')], className='tutorial-controls'),
        ], className='tutorial-footer'),
    ], id='tutorial-dialog', className='tutorial-dialog', **{'aria-labelledby': 'tutorial-title', 'aria-describedby': 'tutorial-description'})
