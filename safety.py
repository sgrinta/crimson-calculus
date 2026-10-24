"""Bounded safety checks around model input, settings capabilities and prose.

These are defense-in-depth checks, not a complete prompt-injection detector or
semantic fact checker. Calculator values and validated UI receipts stay authoritative.
"""
import base64
import json
import os
import re
import unicodedata

CONFUSABLES=str.maketrans({'О':'O','о':'o','А':'A','а':'a','Е':'E','е':'e','І':'I','і':'i','Р':'P','р':'p','С':'C','с':'c','К':'K','к':'k'})


def normalize(text):
    return ''.join(c for c in unicodedata.normalize('NFKC',text).translate(CONFUSABLES)
                   if unicodedata.category(c)!='Cf').lower()


def redact_secrets(text):
    """Scrub known configured keys and common credential forms; never log originals."""
    if not isinstance(text,str):return text
    for name in ('PORTKEY_API_KEY','OPENAI_API_KEY'):
        secret=os.getenv(name,'').strip()
        if len(secret)>=8:
            for representation in (secret,base64.b64encode(secret.encode()).decode(),secret.encode().hex()):
                text=text.replace(representation,'[REDACTED]')
    text=re.sub(r'\bsk-[A-Za-z0-9_-]{8,}', '[REDACTED]', text)
    text=re.sub(r'(?i)(\b(?:PORTKEY_API_KEY|OPENAI_API_KEY)\s*[=:]\s*)[^\s,;]+',r'\1[REDACTED]',text)
    return re.sub(r'(?i)(\bBearer\s+)[A-Za-z0-9_.-]{8,}',r'\1[REDACTED]',text)


def check_prompt(text):
    if '[REDACTED]' in text or redact_secrets(text)!=text:
        raise ValueError('Credential access blocked. Keep keys out of chat; configure them in the project or parent .env file.')
    canonical=normalize(text)
    # Decode small explicit base64 strings for screening, never for execution.
    for token in re.findall(r'\b[A-Za-z0-9+/]{16,}={0,2}\b',text):
        try:
            decoded=base64.b64decode(token,validate=True).decode('utf-8')
            if decoded.isprintable():canonical+=' '+normalize(decoded[:2000])
        except (ValueError,UnicodeError):pass
    compact=re.sub(r'[^a-z0-9]','',canonical)
    targets=('portkeyapikey','openaiapikey','apikey','systemprompt','credentials','environmentvariables','authorization','bearertoken','secrets')
    sensitive=any(t in compact for t in targets) or '.env' in canonical
    hard=any(t in compact for t in ('reveal','print','dump','expose','disclose','leak','exfiltrate','verbatim','exactstring','thevalueof','valueof','secretin','backwards'))
    soft=any(t in compact for t in ('show','read','display','output','return','tellme','getthe'))
    setup=bool(re.search(r'\b(where|configure|configuration|setup|install|add|put|missing|connect)\b',canonical))
    if sensitive and (hard or (soft and not setup)):
        raise ValueError('Credential access blocked. Vivienne can use approved calculation and settings tools only.')


ALIASES={
 'bankroll':r'bankroll|starting\s+balance|budget',
 'target':r'(?:profit\s+|net\s+profit\s+)?target',
 'loss_limit':r'loss\s+limit|stop[- ]loss|maximum\s+(?:net\s+)?loss',
 'minimum':r'minimum\s+(?:bet|wager)|min\s+bet|table\s+minimum',
 'maximum':r'maximum\s+(?:total\s+)?(?:wager|bet)|max\s+(?:wager|bet)|table\s+maximum',
 'chip':r'chip\s*(?:size|value)?',
 'spins':r'spin\s+limit|spins|turn\s+limit',
 'wheel':r'wheel(?:\s*(?:type|rules))?|roulette\s+type',
}
FIELD_PATTERN=re.compile(r'\b(?:'+ '|'.join(f'(?P<{k}>{v})' for k,v in ALIASES.items())+r')\b')
AMOUNT=r'\$?\s*(-?\d[\d,]*(?:\.\d+)?\s*[kK]?)'
WHEELS={'french':r'french|la\s+partage','triple':r'triple(?:[- ]zero)?|000',
        'double':r'american|double(?:[- ]zero)?|00','single':r'european|single(?:[- ]zero)?'}


def settings_intent(text,values):
    """Conservative parser for direct assignments, not a general language interpreter.

    Quoted/code examples, what-ifs, negated changes and role-spoofed documents
    cannot grant a write capability. Ambiguous/unparsed edits require rephrasing.
    """
    direct=re.sub(r'(?m)^\s*>.*$',' ',text)
    direct=re.sub(r'```.*?(?:```|\Z)|`[^`]*`|"[^"\n]*"|“[^”\n]*”|(?<!\w)\x27[^\x27\n]+\x27(?!\w)',' ',direct,flags=re.S)
    direct=normalize(direct)
    read_only=bool(re.search(r'\b(what\s+if|hypothetical\w*|suppose|imagine|would\s+happen|if\s+i|review|explain\s+this|quoted|how\s+to|how\s+(?:do|can|would|should)\s+(?:i|we)|(?:should|would|could)\s+i|instructions?\s+(?:for|on)|steps?\s+(?:for|to))\b|\[(?:/?system|/?developer)\]|\b(?:system|developer|tool\s+result)\s*:',direct))
    read_only=read_only or bool(re.search(r"\b(?:do\s+not|don['’]t|never|without)\s+(?:\w+\s+){0,3}(?:apply|change|edit|update|set|touch|modify|compare|run\s+(?:the\s+)?comparison)\b",direct))
    result=dict(edit=False,apply=False,fields={})
    if read_only:return result
    action_pattern=r'\b(set|change|update|make|use|switch|choose|select|increase|decrease|reduce|raise|lower)\b'
    action=re.search(action_pattern,direct)
    result['apply']=bool(re.search(r'\bapply\b|\brun\s+(?:the\s+)?comparison\b|\bcompare\s+(?:the\s+)?(?:systems|strategies)\b',direct))
    operation=action or re.search(r'\b(?:apply|compare|run)\b',direct)
    if operation and (re.search(r'\b(?:explain|describe|summarize)\b',direct[:operation.start()]) or
                      re.search(r'\b(?:says?|states?|tells?|instructs?)\s+(?:me\s+)?to\b',direct[:operation.start()])):
        return dict(edit=False,apply=False,fields={})
    if not action:return result
    # Stop at a semicolon/new sentence: later factual clauses cannot inherit Set.
    assignment=direct[action.start():]
    assignment=re.split(r'[;!?\n]|\.(?!\d)',assignment,maxsplit=1)[0]
    found=list(FIELD_PATTERN.finditer(assignment))
    def amount(raw):
        raw=raw.strip().replace(',','')
        value=float(raw[:-1])*1000 if raw.lower().endswith('k') else float(raw)
        return int(value) if value.is_integer() else value
    pending=[]
    claimed=[]
    for i,match in enumerate(found):
        field=match.lastgroup
        suffix=assignment[match.end():found[i+1].start() if i+1<len(found) else len(assignment)]
        prefix=assignment[found[i-1].end() if i else 0:match.start()]
        # A later assignment can reverse direction: "increase target by 10 and
        # decrease maximum wager by 20" must use each field's own verb.
        field_actions=list(re.finditer(action_pattern,assignment[:match.start()]))
        field_action=field_actions[-1].group(1) if field_actions else action.group(1)
        value=None
        chosen=None
        if re.search(r'\bor\b',suffix):
            # Alternatives are a question, not permission to silently choose one.
            return dict(edit=False,apply=False,fields={})
        if field=='wheel':
            for wheel,pattern in WHEELS.items():
                if re.search(r'\b(?:'+pattern+r')\b',suffix):value=wheel;break
        else:
            before=re.search(AMOUNT+r'\s*$',prefix)
            prefix_start=found[i-1].end() if i else 0
            before_span=(prefix_start+before.start(1),prefix_start+before.end(1)) if before else None
            before_unused=before and not any(max(before_span[0],a)<min(before_span[1],b) for a,b in claimed)
            numbers=list(re.finditer(AMOUNT,suffix))
            if before_unused and not re.match(r'\s*(?:to|by|=|:)',suffix):
                value=amount(before.group(1));numbers=[];chosen=before_span
            # Do not turn statements like "my bankroll is 500" into assignments.
            if numbers and not re.match(r'\s+is\b',suffix):
                to=re.search(r'\bto\s*'+AMOUNT,suffix)
                if to:
                    value=amount(to.group(1));chosen=(match.end()+to.start(1),match.end()+to.end(1))
                elif len(numbers)==1 and re.fullmatch(r'\s*(?:by|of|at|=|:)?\s*\$?\s*',suffix[:numbers[0].start(1)]):
                    value=amount(numbers[0].group(1));chosen=(match.end()+numbers[0].start(1),match.end()+numbers[0].end(1))
                if value is not None and re.match(r'\s+by\b',suffix):
                    base=values.get(field)
                    if not isinstance(base,(int,float)) or isinstance(base,bool):value=None
                    else:value=base+value*(-1 if field_action in ('decrease','reduce','lower') else 1)
            if value is None:
                if before_unused:value=amount(before.group(1));chosen=before_span
        if value is not None:
            if chosen:claimed.append(chosen)
            result['fields'][field]=value
            for earlier in pending:result['fields'][earlier]=value
            pending=[]
        elif re.fullmatch(r'\s*(?:and|my|the|both|\s)*',suffix):pending.append(field)
        else:pending=[]
    # "Use French roulette" also names the wheel without the word wheel/type.
    for wheel,pattern in WHEELS.items():
        if re.search(r'\b(?:use|switch(?:\s+to)?|choose|select)\s+(?:'+pattern+r')\b',assignment):
            result['fields']['wheel']=wheel;break
    result['edit']=bool(result['fields'])
    return result


def authorize_settings(name,arguments,intent,current):
    if name not in ('update_session_settings','apply_session_settings'):return
    if not intent or not intent['apply' if name=='apply_session_settings' else 'edit']:
        raise ValueError('No direct authorization for that settings action in this message. What-if questions and quoted instructions do not change settings.')
    for field,value in arguments.items():
        if field in current and value==current[field]:continue
        if field not in intent['fields'] or value!=intent['fields'][field]:
            raise ValueError('The requested tool change does not match your explicit settings request. Please state each setting and value directly.')


def response_issues(text,probabilities=()):
    issues=[]
    if redact_secrets(text)!=text:issues.append('credential_output')
    normalized=normalize(text)
    patterns=(r'guarantee[sd]?\s+(?:a\s+|any\s+)?(?:profit|win|return|recovery)',
        r'(?:cannot|can.t|won.t|will\s+not)\s+lose\b',r'risk[- ]free',r'no\s+risk\b(?!-free)' ,
        r'(?:removes?|eliminates?)\s+(?:the\s+)?house\s+edge',
        r'\b(?:red|black|a\s+win|a\s+loss|winning)\s+(?:is|are)\s+due\b',
        r'(?:keep|continue)\s+(?:playing|betting)[^.!?;]{0,65}recover',
        r'(?:raise|increase)\s+(?:your\s+)?(?:stakes|bets|loss\s+limit)[^.!?;]{0,65}recover',
        r'100\s*%\s+(?:chance|certain|success|win)')
    for clause in re.split(r'(?<=[.!?;])\s+|\n',normalized):
        refusal=bool(re.search(r"\bi\s+(?:cannot|can.t|will\s+not|won.t)\s+(?:help|claim|say|promise|pretend)\b",clause))
        for pattern in patterns:
            for match in re.finditer(pattern,clause):
                prefix=clause[max(0,match.start()-65):match.start()]
                negated=re.search(r"\b(?:no|not|never|cannot|can.t|does\s+not|do\s+not|doesn.t|don.t|isn.t|aren.t|false|myth)\s+(?:[\w-]+\s+){0,3}$",prefix)
                if negated and re.search(r'\bnot\s+only\b',prefix):negated=False
                if not negated and not refusal:issues.append('misleading_gambling_claim')
    # Only percentage *values* are checked, not all numeric/semantic claims.
    checked=re.sub(r'\b(?:worst|bottom|lowest)[- ]*5\s*%', '',normalized)
    for match in re.finditer(r'(?<![\w.])(-?\d+(?:\.\d+)?)\s*%',checked):
        value=float(match.group(1))
        prefix=checked[max(0,match.start()-50):match.start()]
        if value in (0.,100.) and re.search(r'\b(?:not|never|no|cannot|can.t)\b',prefix):continue
        decimals=len(match.group(1).split('.')[1]) if '.' in match.group(1) else 0
        tolerance=.501*(10**-decimals)
        if not any(abs(value-100*p)<=tolerance for p in probabilities):issues.append('unsupported_percentage')
    return sorted(set(issues))


def collect_probabilities(value):
    results=[]
    names={'success','probability','p','edge','even_edge','remaining_session_success','next_spin_profit_probability','streak_probability','loss_probability','opening_win','opening_loss','opening_even'}
    def visit(item):
        if isinstance(item,dict):
            for key,v in item.items():
                if key in names and isinstance(v,(int,float)) and not isinstance(v,bool) and 0<=v<=1:results.append(float(v))
                visit(v)
        elif isinstance(item,(list,tuple)):
            for child in item:visit(child)
    visit(value)
    return results
