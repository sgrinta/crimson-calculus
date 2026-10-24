"""Allowlisted, locally downloaded AI-run evidence with credential redaction."""
from datetime import datetime, timezone
import os
import re
from safety import redact_secrets
from pricing import message_cost


def redact(value):
    if isinstance(value, dict):return {k:redact(v) for k,v in value.items()}
    if isinstance(value, (list,tuple)):return [redact(v) for v in value]
    if not isinstance(value,str):return value
    return redact_secrets(value)


def export_run(messages, run_id, receipts):
    from agent import TOOLS, MODEL
    from host_settings import FIELDS
    allowed={t['function']['name']:set(t['function']['parameters']['properties']) for t in TOOLS}
    index=next((i for i,m in enumerate(messages or []) if m.get('role')=='assistant' and
                (m.get('run',{}).get('id') or m.get('turn_id') or f'message-{i}')==run_id),None)
    if index is None:raise ValueError('That run is no longer in this chat. Export a visible reply.')
    message=messages[index]; meta=message.get('run',{})
    question=meta.get('question') or next((m.get('content','') for m in reversed(messages[:index]) if m.get('role')=='user'),'Question no longer available')
    trace=[]
    for call in message.get('trace',[]):
        item={k:call[k] for k in ('tool','status','calculation_id','source','access','spins_returned','elapsed_ms','reasons','messages_removed') if k in call}
        item['arguments']={k:v for k,v in (call.get('arguments') or {}).items() if k in allowed.get(call.get('tool'),set())}
        trace.append(item)
    fields=lambda source:{k:v for k,v in (source or {}).items() if k in FIELDS}
    proposal=message.get('settings_update') or {}
    receipt=next((r for r in receipts or [] if proposal.get('id') and r.get('id')==proposal['id']),None)
    settings=None
    if proposal:
        settings=dict(action=proposal.get('action','edit'),before_fields=fields(proposal.get('before')),
                      after_fields=fields(proposal.get('after')),receipt={k:receipt[k] for k in
                      ('status','changes','message','calculation_id','systems_tested','best','undone_at','before_applied','after_applied') if k in receipt} if receipt else None)
    usage={k:message.get('usage',{}).get(k) for k in ('input','cached','output')}
    usage.update({k:message['usage'][k] for k in ('reported_calls','unreported_calls') if k in message.get('usage',{})})
    cost=message_cost(message)
    payload=dict(format='crimson-calculus-ai-run-v1',exported_at=datetime.now(timezone.utc).isoformat(),
        run_id=run_id,model=meta.get('model',MODEL),mode=message.get('mode'),
        started_at=meta.get('started_at'),finished_at=meta.get('finished_at'),duration_seconds=meta.get('duration_seconds'),
        question=question,response=message.get('content',''),tools=trace,
        applied_scenario_at_request=fields(meta.get('applied_scenario')),form_fields_at_request=fields(meta.get('form_fields')),
        session_sharing_enabled=meta.get('session_sharing_enabled'),settings_transaction=settings,
        tokens=usage,token_note='Cached input is part of input, not an extra token charge.',
        estimated_cost_usd=cost['estimated_cost_usd'],cost_estimate=cost,cost_note=cost['note'],
        privacy_note='No raw session logs, keys, environment dump or hidden prompts are bundled. The question and reply may contain session details; review before sharing.')
    return redact(payload)
