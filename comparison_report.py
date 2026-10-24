"""Self-contained comparison reports from freshly verified calculator output."""
from dataclasses import asdict
from datetime import datetime,timezone
from html import escape
import math
from engine import Scenario,WHEELS,compare


def dollars(value):return ('−' if value<0 else '')+f'${abs(value):,.2f}'
def e(value):return escape(str(value),quote=True)


def distribution_svg(row):
    data=row['distribution'];lo=min(d['net'] for d in data);hi=max(d['net'] for d in data)
    count=min(50,len(data));bins=[0.]*count
    if hi==lo:bins[0]=sum(d['probability'] for d in data)
    else:
        for d in data:bins[min(count-1,int((d['net']-lo)/(hi-lo)*count))]+=d['probability']
    ceiling=max(bins) or 1;bars=[]
    for i,p in enumerate(bins):
        x=56+i*860/count;h=p/ceiling*155
        bars.append(f'<rect x="{x:.2f}" y="{185-h:.2f}" width="{max(1,860/count-2):.2f}" height="{h:.2f}" fill="#8b2036"><title>Bucket {i+1}: {p:.6%} of modeled sessions</title></rect>')
    return f'<svg viewBox="0 0 960 235" role="img" aria-label="Modeled final net result distribution"><text x="56" y="18">Probability per bucket; highest bucket {ceiling:.2%}</text>{"".join(bars)}<line x1="56" x2="916" y1="185" y2="185" stroke="#302224"/><text x="56" y="212">{e(dollars(lo))}</text><text x="916" y="212" text-anchor="end">{e(dollars(hi))}</text><text x="480" y="233" text-anchor="middle">Final session net profit / loss</text></svg>'


def comparison_report(snapshot,selected=None,benchmarks=None):
    """Ignore client-supplied row values; regenerate from validated saved scenario."""
    s=Scenario(**snapshot['scenario']);result=compare(s)
    if snapshot.get('id')!=result['id']:raise ValueError('Comparison ID does not match its scenario. Apply settings again before exporting.')
    rows=result['rows'];best=rows[0]
    chosen=next((r for r in rows if r['key']==selected),best)
    settings=[('Wheel / rules',WHEELS[s.wheel]),('Starting bankroll',dollars(s.bankroll)),('Net-profit target','+'+dollars(s.target)),('Loss limit',dollars(s.loss_limit)),('Minimum per position',dollars(s.minimum)),('Maximum total wager per spin',dollars(s.maximum)),('Chip size',dollars(s.chip)),('Maximum spins',s.spins)]
    setting_rows=''.join(f'<tr><th>{e(k)}</th><td>{e(v)}</td></tr>' for k,v in settings)
    def row_html(r,index):
        base=dollars(r['base']) if r.get('base') else 'Changes each spin'
        return f'<tr><td>{index}</td><th>{e(r["label"])}</th><td>{e(base)}</td><td>{r["success"]:.4%}</td><td>{e(dollars(r["mean"]))}</td><td>{e(dollars(r["max_loss"]))}</td><td>{e(dollars(r["worst5"]))}</td></tr>'
    ranked=''.join(row_html(r,i+1) for i,r in enumerate(rows))
    methods=''.join(f'<li><strong>{e(r["label"])}</strong>: {e(r["method"])}. {e(r["scope"])}</li>' for r in rows)
    notices=''.join('<li>'+e(n)+'</li>' for n in result['notices']) or '<li>No tested family was omitted by an interactive calculation limit.</li>'
    benchmark_html=''
    if benchmarks:
        # Only the fixed fictional example supplies these server-side profiles.
        benchmark_html='<h2>Guided example: fixed starting amounts</h2><p>These rows use prescribed starting bets, rather than the optimized starting amounts in the main ranking.</p><div class="table-scroll"><table><thead><tr><th>#</th><th>Plan</th><th>Starts at</th><th>Reach target</th><th>Average net</th><th>Max loss</th><th>Worst 5% average</th></tr></thead><tbody>'+''.join(row_html(r,i+1) for i,r in enumerate(benchmarks))+'</tbody></table></div>'
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Crimson Calculus — Comparison {e(result['id'])}</title>
<style>body{{background:#f7f2e9;color:#21191b;font:17px/1.55 system-ui,sans-serif;max-width:1100px;margin:36px auto;padding:0 24px}}h1,h2{{font-family:Georgia,serif;color:#751a30;line-height:1.2}}h1{{font-size:38px}}.eyebrow{{letter-spacing:2px;font-size:13px;text-transform:uppercase}}.summary{{background:white;padding:24px;border-left:5px solid #8b2036}}table{{border-collapse:collapse;width:100%;font-size:14px;background:white}}th,td{{text-align:left;padding:10px;border-bottom:1px solid #d8cec0}}thead{{background:#21191b;color:#fff}}.table-scroll{{overflow:auto}}svg{{width:100%;background:#fff;font:13px system-ui,sans-serif}}li{{margin-bottom:10px}}.note{{font-size:14px;color:#51434a}}@media print{{body{{margin:0;padding:0;background:white}}thead{{display:table-header-group}}tr,svg,.summary{{break-inside:avoid}}.table-scroll{{overflow:visible}}a{{color:inherit}}table{{font-size:11px}}th,td{{padding:6px}}}}@page{{size:letter;margin:.55in}}</style></head><body>
<p class="eyebrow">Crimson Calculus · Roulette Odds, Strategy &amp; Risk</p><h1>Session strategy comparison</h1><p class="note">Generated {datetime.now(timezone.utc).strftime('%B %d, %Y at %H:%M UTC')} · Calculation {e(result['id'])}</p>
<div class="summary"><strong>Best among tested systems: {e(best['label'])}</strong><p>{best['success']:.4%} chance of reaching the net-profit target within the modeled limits. Average final net: {e(dollars(best['mean']))}. Worst-5% average: {e(dollars(best['worst5']))}. Maximum possible loss: {e(dollars(best['max_loss']))}.</p><p>A high chance of reaching a target can accompany a negative average and large occasional losses. This is a finite candidate comparison, not a guarantee or a global optimum.</p></div>
<h2>Applied settings</h2><p>This snapshot uses the last applied comparison, not unapplied field edits or the current bankroll of an ongoing game.</p><table>{setting_rows}</table>
<h2>All tested systems</h2><p>Ranked by the probability of reaching at least the target before stopping. Average net and downside include failed sessions.</p><div class="table-scroll"><table><thead><tr><th>#</th><th>System</th><th>Starts at</th><th>Reach target</th><th>Average net</th><th>Max loss</th><th>Worst 5% average</th></tr></thead><tbody>{ranked}</tbody></table></div>
{benchmark_html}<h2>Final results: {e(chosen['label'])}</h2>{distribution_svg(chosen)}<p class="note">Exact modeled probabilities grouped into up to 50 chart buckets for readability. This is a distribution of whole-session net results, not a prediction of the next spin.</p>
<h2>How to read the risks</h2><ul><li>Success means reaching at least the net target within the constraints, not winning every spin.</li><li>Average net is the expected result over both successes and failures.</li><li>Worst-5% average is the mean net result in the worst five percent of sessions, including fractional probability at the cutoff.</li><li>Maximum loss is the largest terminal loss possible for that policy. The next prescribed wager may be blocked before the bankroll reaches zero.</li></ul>
<h2>Method and boundaries</h2><p>{e(result['assumptions'])}</p><ul>{methods}</ul><h2>Calculation notices</h2><ul>{notices}</ul>
<p class="note">No AI request is made to generate this report. It contains calculator results only, with no chat, API credentials or game logs. The report embeds its chart and styles and opens offline. Use your browser's Print command to save a PDF. This educational simulator cannot predict wheel results, connect to a casino or place wagers.</p></body></html>'''
