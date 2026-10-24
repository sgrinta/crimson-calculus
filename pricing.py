"""Published-rate token estimates, not provider invoices. No network or AI calls."""
from decimal import Decimal
import math

MODEL='gpt-6-luna'
RATE_CARD=dict(model=MODEL,currency='USD',per_tokens=1_000_000,
    input='0.10',cached_input='0.01',output='0.50',
    source='https://developers.openai.com/api/docs/models/gpt-6-luna',
    verified_on='2026-10-24',tier='Standard, short context (at most 272K input tokens per request)')
COST_NOTE=('Published OpenAI token-rate estimate, not a provider bill. Cached input is part of input. '
           'Excludes gateway fees, discounts, tax and unreported/cache-write charges. '
           'This app bounds each request well below the long-context threshold.')


def estimate_cost(usage,model=MODEL,mode=None):
    result=dict(estimated_cost_usd=None,currency='USD',status='unavailable',note=COST_NOTE,
                rates=dict(RATE_CARD) if model==MODEL else None)
    if not isinstance(usage,dict) and mode not in ('blocked','budget guard','calculator only'):
        return dict(result,note='Provider token measurements are unavailable.')
    if not isinstance(usage,dict):usage={}
    if mode in ('blocked','budget guard','calculator only') and not any((usage or {}).get(k,0) for k in ('input','cached','output')):
        return dict(result,estimated_cost_usd=0.,status='no_ai_request',note='No AI request was made for this reply.')
    if model!=MODEL:return dict(result,note='No verified rate card is configured for this model.')
    if not isinstance(usage,dict):return dict(result,note='Provider token measurements are unavailable.')
    counts=[usage.get(k) for k in ('input','cached','output')]
    if any(isinstance(n,bool) or not isinstance(n,(int,float)) or not math.isfinite(n) or n<0 or n!=int(n) for n in counts):
        return dict(result,note='Provider token measurements are missing or invalid.')
    total,cached,output=map(int,counts)
    if cached>total:return dict(result,note='Cached input cannot exceed total input.')
    if total+output==0:return dict(result,note='No billable token measurements were reported; an unreported request may still have a charge.')
    # App requests are byte-bounded below 21k, so even aggregate multi-call turn
    # usage stays within short-context pricing. Unknown external large runs fail closed.
    if total>272_000:return dict(result,note='Per-request context sizes are needed to price this large aggregate safely.')
    parts=dict(uncached_input_usd=Decimal(total-cached)*Decimal(RATE_CARD['input'])/1_000_000,
               cached_input_usd=Decimal(cached)*Decimal(RATE_CARD['cached_input'])/1_000_000,
               output_usd=Decimal(output)*Decimal(RATE_CARD['output'])/1_000_000)
    partial=bool(usage.get('unreported_calls')) or mode=='connection error'
    return dict(result,estimated_cost_usd=float(sum(parts.values())),breakdown={k:float(v) for k,v in parts.items()},
                measured_tokens=dict(input=total,cached=cached,uncached_input=total-cached,output=output),
                status='partial' if partial else 'estimated',
                note=('Some calls have no reported usage; the estimate covers reported tokens only. ' if partial else '')+COST_NOTE)


def message_cost(message):
    return estimate_cost(message.get('usage'),message.get('run',{}).get('model',MODEL),message.get('mode'))


def cost_label(cost):
    value=cost['estimated_cost_usd']
    if value is None:return 'Estimated AI cost: unavailable'
    if cost['status']=='no_ai_request':return 'AI token cost: $0 · no AI request'
    return f"Estimated AI token cost: ${value:.6f}"+(' · partial usage' if cost['status']=='partial' else '')
