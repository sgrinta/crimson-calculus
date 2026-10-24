"""Deterministic roulette calculations. No model, network, or random outcomes."""
from collections import defaultdict
from dataclasses import asdict, dataclass
from functools import lru_cache
from hashlib import sha256
import json
import math
from pathlib import Path
import time

import numpy as np
from hosting import HOSTED_DEMO, one_calculation_at_a_time

ROOT = Path(__file__).resolve().parent
WHEELS = {"single":"European · 0", "french":"French · 0 · La Partage", "double":"American · 0 / 00", "triple":"Triple-zero · 0 / 00 / 000"}
EVEN_CHOICES = {"red":"Red","black":"Black","odd":"Odd","even":"Even","low":"Low (1–18)","high":"High (19–36)"}
LABELS = {
    "martingale": "Martingale", "grand_martingale": "Grand Martingale",
    "flat": "Flat betting", "dalembert": "D’Alembert",
    "reverse_dalembert": "Reverse D’Alembert", "fibonacci": "Fibonacci · 1, 1, 2…",
    "paroli": "Paroli · three wins", "1326": "1–3–2–6",
}
RULES = {
    "martingale": "Double after each loss; reset to the base after a win.",
    "grand_martingale": "After a loss, double and add one base unit; reset after a win.",
    "flat": "Repeat the same wager after every result.",
    "dalembert": "Add one base unit after a loss; subtract one after a win, with a one-unit floor.",
    "reverse_dalembert": "Add one base unit after a win; subtract one after a loss, with a one-unit floor.",
    "fibonacci": "Start at the first 1 in 1,1,2,3,5…; advance one on a loss and retreat two on a win.",
    "paroli": "Bet 1,2,4 base units on successive wins; reset on any loss or the third win.",
    "1326": "Advance through 1,3,2,6 base units after wins; reset after a loss or four wins.",
}


@dataclass(frozen=True)
class Scenario:
    bankroll: int = 1000
    target: int = 200
    loss_limit: int = 1000
    minimum: int = 5
    maximum: int = 500
    chip: int = 5
    spins: int = 280
    wheel: str = "single"

    def __post_init__(self):
        for name in ("bankroll", "target", "loss_limit", "minimum", "maximum", "chip", "spins"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value != int(value) or value <= 0:
                raise ValueError(f"{name.replace('_', ' ').capitalize()} must be a positive whole number.")
            object.__setattr__(self, name, int(value))
        if self.wheel not in WHEELS:
            raise ValueError("Choose European, French (La Partage), American, or triple-zero roulette.")
        if self.loss_limit > self.bankroll:
            raise ValueError("Loss limit cannot exceed the bankroll.")
        if not self.chip <= self.minimum <= self.maximum:
            raise ValueError("Use chip ≤ minimum bet ≤ maximum total wager.")
        if self.loss_limit < self.minimum:
            raise ValueError("The loss limit must allow at least one minimum bet.")
        if any(getattr(self, n) % self.chip for n in ("bankroll", "target", "loss_limit", "minimum", "maximum")):
            raise ValueError("All dollar amounts must be multiples of the chip size.")
        if self.spins > 500:
            raise ValueError("Use at most 500 spins for an interactive calculation.")
        risk_chips=(self.loss_limit+self.target)//self.chip
        wager_chips=self.maximum//self.chip
        if risk_chips > 2000 or wager_chips > 2000:
            raise ValueError(f"These settings need {risk_chips:,} loss-plus-target chips and {wager_chips:,} maximum-wager chips. The interactive limit is 2,000 of each. Increase chip size or reduce those amounts.")
        if HOSTED_DEMO and (risk_chips > 600 or wager_chips > 500):
            raise ValueError("The free online demo supports at most 600 loss-plus-target chips and 500 maximum-wager chips. Increase chip size or reduce the amounts. The downloadable local app retains its larger limits.")

    @property
    def pockets(self):
        return {"single":37,"french":37,"double":38,"triple":39}[self.wheel]

    @property
    def p(self):
        return 18 / self.pockets

    @property
    def edge(self):
        return (self.pockets - 36) / self.pockets

    @property
    def even_edge(self):
        return 1/74 if self.wheel == "french" else self.edge

    @property
    def cash_unit(self):
        return self.chip/2 if self.wheel == "french" else self.chip

    @property
    def zero_rule(self):
        if self.wheel == "french":
            return "La Partage: zero loses half of even-money stakes. A half-loss advances named progressions as a loss. Inside and dozen/column bets get no half refund. En Prison is not modeled. Half-chip cash is tracked exactly; new wagers still use whole chips."
        return "All zero pockets fully lose even-money wagers. Standard payouts; no La Partage or En Prison."


def scenario(data=None):
    return Scenario(**(data or {}))


def structure(name, base, s):
    cap = s.maximum // base
    if name in ("flat", "dalembert", "reverse_dalembert"):
        stakes = np.array([1]) if name == "flat" else np.arange(1, cap + 2)
        j = np.arange(len(stakes))
        if name == "flat":
            return stakes, j, j
        down, up = np.maximum(0, j - 1), np.minimum(len(j) - 1, j + 1)
        return (stakes, up, down) if name == "reverse_dalembert" else (stakes, down, up)
    if name == "fibonacci":
        stakes = [1, 1]
        while stakes[-1] <= cap:
            stakes.append(stakes[-1] + stakes[-2])
        j = np.arange(len(stakes))
        return np.array(stakes), np.maximum(0, j - 2), np.minimum(len(j) - 1, j + 1)
    if name in ("paroli", "1326"):
        stakes = np.array([1, 2, 4] if name == "paroli" else [1, 3, 2, 6])
        j = np.arange(len(stakes))
        return stakes, (j + 1) % len(j), np.zeros(len(j), dtype=int)
    stakes = [1]
    while stakes[-1] <= cap:
        stakes.append(2 * stakes[-1] + (name == "grand_martingale"))
    j = np.arange(len(stakes))
    return np.array(stakes), np.zeros(len(j), dtype=int), np.minimum(len(j) - 1, j + 1)


def value_structure(s,name,base):
    """Remove progression levels unreachable within this session, without capping bets."""
    stakes,wi,li=structure(name,base,s)
    if name in ('dalembert','reverse_dalembert'):
        count=min(len(stakes),s.spins+1)
        if s.wheel!='french':
            # With q stake units and k profit units, k+q(q-1)/2 equals
            # wins for D'Alembert; k-q(q-1)/2 equals minus losses for reverse.
            # Wins/losses cannot exceed the horizon. Include one boundary level.
            bound=(s.loss_limit//base if name=='dalembert' else math.ceil(s.target/base)-1)+s.spins
            q=(1+math.isqrt(1+8*bound))//2
            count=min(count,q+1)
        stakes=stakes[:count]
        wi=np.minimum(wi[:count],count-1)
        li=np.minimum(li[:count],count-1)
    return stakes,wi,li


def classic_value(s, name, base):
    if s.wheel == "french":
        return french_classic_value(s,name,base)
    stakes, wi, li = value_structure(s, name, base)
    count = len(stakes)
    low, high = -(s.loss_limit // base), math.ceil(s.target / base) - 1
    k = np.arange(low, high + 1)[:, None]
    stake = stakes[None, :]
    shape = (len(k), count)
    profit = np.broadcast_to(k * base, shape).ravel()
    valid = np.broadcast_to((stake * base <= s.maximum) & (stake * base <= s.loss_limit + k * base), shape).ravel()
    kw, kl = np.broadcast_to(k + stake, shape), np.broadcast_to(k - stake, shape)
    hit = (kw * base >= s.target).ravel()
    widx = ((np.clip(kw, low, high) - low) * count + wi[None, :]).ravel().astype(int)
    lidx = ((np.clip(kl, low, high) - low) * count + li[None, :]).ravel().astype(int)
    v, mean = np.zeros(len(profit)), profit.astype(float)
    for _ in range(s.spins):
        next_v = np.where(valid, s.p * np.where(hit, 1., v[widx]) + (1 - s.p) * v[lidx], 0.)
        next_mean = np.where(valid, s.p * np.where(hit, (kw * base).ravel(), mean[widx]) + (1 - s.p) * mean[lidx], profit)
        if np.array_equal(next_v,v) and np.array_equal(next_mean,mean):break
        v,mean=next_v,next_mean
    idx = -low * count
    return float(v[idx]), float(mean[idx])


def french_classic_value(s,name,base):
    """Half-base profit lattice; zero is a separate half-loss/progression-loss branch."""
    stakes,wi,li=value_structure(s,name,base)
    unit=base/2
    low,high=-math.floor(s.loss_limit/unit),math.ceil(s.target/unit)-1
    k=np.arange(low,high+1)[:,None];count=len(stakes);shape=(len(k),count)
    dollars=stakes[None,:]*base
    profit=np.broadcast_to(k*unit,shape).ravel()
    valid=np.broadcast_to((dollars<=s.maximum)&(dollars<=s.loss_limit+k*unit),shape).ravel()
    branches=[]
    for delta,next_i,prob in [(2*stakes,wi,18/37),(-2*stakes,li,18/37),(-stakes,li,1/37)]:
        dest=np.broadcast_to(k+delta[None,:],shape)
        index=((np.clip(dest,low,high)-low)*count+next_i[None,:]).ravel().astype(int)
        branches.append((index,(dest*unit>=s.target).ravel(),(dest*unit).ravel(),prob))
    v=np.zeros(len(profit));mean=profit.copy()
    for _ in range(s.spins):
        next_v=np.where(valid,sum(prob*np.where(hit,1.,v[index]) for index,hit,net,prob in branches),0.)
        next_mean=np.where(valid,sum(prob*np.where(hit,net,mean[index]) for index,hit,net,prob in branches),profit)
        if np.array_equal(next_v,v) and np.array_equal(next_mean,mean):break
        v,mean=next_v,next_mean
    return float(v[-low*count]),float(mean[-low*count])


def summarize(pmf, s, spins, turnover, blocked=0., horizon=0., expected_loss=None):
    """Summarize terminal cash outcomes and separately supplied stopping reasons.

    blocked means a prescribed wager cannot be placed before the spin horizon;
    horizon means spins ended below target. ruin is terminal zero cash, which
    may overlap either reason and is not an additional stopping category.
    """
    total = sum(pmf.values())
    mean = sum(net * prob for net, prob in pmf.items())
    expected_loss=s.even_edge*turnover if expected_loss is None else expected_loss
    if abs(total - 1) > 1e-9 or abs(mean + expected_loss) > 1e-6:
        raise ArithmeticError("Probability/expected-value verification failed.")
    left, tail = .05, 0.
    for net, prob in sorted(pmf.items()):
        take = min(left, prob)
        tail += take * net
        left -= take
        if left < 1e-16:
            break
    return dict(success=float(sum(p for net, p in pmf.items() if net >= s.target)), mean=float(mean),
                max_loss=float(max(0, -min(pmf))), worst5=float(tail / .05),
                ruin=float(pmf.get(-s.bankroll, 0.)), blocked=float(blocked), horizon=float(horizon),
                expected_spins=float(spins), expected_turnover=float(turnover),
                distribution=[{"net": float(net), "probability": float(p)} for net, p in sorted(pmf.items())])


def classic_profile(s, name, base, start_profit=0, start_index=0, spins_left=None):
    stakes, wi, li = structure(name, base, s)
    active, pmf = {(start_profit, start_index): 1.}, defaultdict(float)
    spins = turnover = blocked = 0.
    for _ in range(s.spins if spins_left is None else spins_left):
        nxt = defaultdict(float)
        for (profit, i), mass in active.items():
            bet = int(stakes[i]) * base
            if profit >= s.target:
                pmf[profit] += mass
            elif bet > s.maximum or bet > s.loss_limit + profit:
                pmf[profit] += mass
                blocked += mass
            else:
                spins += mass
                turnover += mass * bet
                nxt[(profit + bet, int(wi[i]))] += mass * s.p
                nxt[(profit - bet, int(li[i]))] += mass * (18/37 if s.wheel=="french" else 1-s.p)
                if s.wheel=="french":
                    nxt[(profit-bet/2,int(li[i]))] += mass/37
        active = nxt
    horizon = 0.
    for (profit, i), mass in active.items():
        pmf[profit] += mass
        if profit < s.target:
            # No next wager is attempted after the last allowed spin. This
            # matches the session tracker, which stops at the horizon first.
            horizon += mass
    return summarize(pmf, s, spins, turnover, blocked, horizon,expected_loss=s.even_edge*turnover-start_profit)


def action_pool(s, group_sizes, prune_dominated=False):
    result = {}
    unit=s.cash_unit if s.wheel=="french" and any(k==18 for k,m in group_sizes) else s.chip
    factor=round(s.chip/unit)
    cap=s.maximum//s.chip
    target_chips=(s.loss_limit+s.target)//s.chip
    for k, groups in group_sizes:
        gross=36//k
        for m in range(1, groups + 1):
            each_cap=cap//m
            if prune_dominated:
                # If a >= ceil(target/gross), every affordable win reaches
                # the target: bank >= m*a and win gain = (gross-m)*a.
                # Larger a only increases losses. Preserve the position minimum.
                each_cap=min(each_cap,max(s.minimum//s.chip,(target_chips+gross-1)//gross))
            for a in range(s.minimum//s.chip,each_cap+1):
                cost, gain, count = m*a,(gross-m)*a,m*k
                if gain<=0:continue
                deltas=[gain*factor,-cost*factor];counts=[count,s.pockets-count]
                if s.wheel=="french" and k==18:
                    deltas.append(-cost*factor//2);counts=[18,18,1]
                # A French half-refund differs from an inside portfolio with
                # the same coverage and total. Deduplicate full payout laws.
                result.setdefault((cost,tuple(deltas),tuple(counts)),dict(total=cost*factor,deltas=deltas,counts=counts,_unit=unit,
                    description={"group_size":k,"positions":m,"each":a*s.chip}))
    return list(result.values())


def portfolio_profile(s, actions, policy, bankroll=None, spins_left=None):
    unit=actions[0].get('_unit',s.chip)
    target = round((s.loss_limit + s.target) / unit)
    initial = round(s.loss_limit / unit)
    mass = np.zeros(target)
    mass[initial if bankroll is None else round((bankroll-(s.bankroll-s.loss_limit))/unit)] = 1.
    pmf = defaultdict(float)
    spins = turnover = blocked = expected_loss = 0.
    for left in range(s.spins if spins_left is None else spins_left, 0, -1):
        nxt = np.zeros(target)
        for bank in np.flatnonzero(mass):
            a = actions[int(policy[left, bank])]
            if a["total"] > bank:
                pmf[(bank-initial)*unit] += float(mass[bank])
                blocked += mass[bank]
                continue
            spins += mass[bank]
            turnover += mass[bank] * a["total"] * unit
            expected_loss -= mass[bank]*sum(d*c for d,c in zip(a['deltas'],a['counts']))*unit/s.pockets
            for delta, count in zip(a["deltas"], a["counts"]):
                dest, prob = bank + delta, mass[bank] * count / s.pockets
                if dest >= target:
                    pmf[(dest-initial)*unit] += float(prob)
                else:
                    # Keep depleted loss allowances until the next decision.
                    # With spins left they are blocked (even when cash remains
                    # in a protected reserve); on the final spin they hit the
                    # horizon. Terminal zero-cash probability is also reported
                    # independently as ruin by summarize().
                    nxt[dest] += prob
        mass = nxt
    horizon = float(mass.sum())
    for bank in np.flatnonzero(mass):
        pmf[(bank-initial)*unit] += float(mass[bank])
    return summarize(pmf,s,float(spins),float(turnover),float(blocked),horizon,float(expected_loss)-(0 if bankroll is None else bankroll-s.bankroll))


@one_calculation_at_a_time
@lru_cache(maxsize=4 if HOSTED_DEMO else 12)
def adaptive(s, kind):
    if kind == "research":
        if s != Scenario():
            raise ValueError("The custom optimized betting plan applies only to the original single-zero $1,000/$200 scenario.")
        actions = json.loads((ROOT / "data/portfolio_actions.json").read_text())
        policy = np.fromfile(ROOT / "data/portfolio_policy.bin", dtype="<i4").reshape(281, 240)
    else:
        groups = {"even": [(18, 1)], "dozen": [(12, 1)], "sixline": [(6, 1)],
                  "groups": [(1, 35), (2, 17), (3, 11), (4, 6), (6, 5), (12, 2), (18, 1)]}[kind]
        actions = action_pool(s,groups,prune_dominated=True)
        unit=actions[0].get('_unit',s.chip)
        target,initial=round((s.loss_limit+s.target)/unit),round(s.loss_limit/unit)
        budget=6_000_000_000 if kind=='groups' else 800_000_000
        if HOSTED_DEMO:
            budget=min(budget,240_000_000)
        if target * len(actions) * s.spins > budget:
            raise ValueError("This candidate search exceeds the interactive compute budget. Increase the chip size or lower the spin limit. Other supported systems are still compared.")
        branch_count=max(len(a['deltas']) for a in actions)
        estimated_bytes=target*len(actions)*(1+4*branch_count)+128*len(actions)*48+4*(s.spins+1)*target
        memory_mb=120 if HOSTED_DEMO else 320
        if estimated_bytes>memory_mb*1024*1024:
            raise ValueError("This search exceeds the calculation memory budget. Increase chip size or reduce the loss limit; other supported systems are still compared.")
        bank = np.arange(target,dtype=np.int32)[:, None]
        costs = np.array([a["total"] for a in actions],dtype=np.int32)
        legal = costs[None, :] <= bank
        branches=[]
        for j in range(max(len(a['deltas']) for a in actions)):
            deltas=np.array([a['deltas'][j] if j<len(a['deltas']) else 0 for a in actions],dtype=np.int32)
            probs=np.array([a['counts'][j]/s.pockets if j<len(a['counts']) else 0 for a in actions])
            branches.append((np.clip(bank+deltas[None,:],0,target),probs))
        v = np.zeros(target + 1)
        v[target] = 1.
        policy = np.zeros((s.spins + 1, target), dtype=np.int32)
        for left in range(1, s.spins + 1):
            next_v=np.zeros(target)
            # Work in small row blocks to bound temporary arrays/cache traffic.
            # Every block reads the same previous horizon; update v only afterward.
            for start in range(0,target,128):
                end=min(start+128,target)
                scores=np.where(legal[start:end],sum(probs*v[dest[start:end]] for dest,probs in branches),-1.)
                chosen=np.argmax(scores,axis=1)
                policy[left,start:end]=chosen
                next_v[start:end]=np.maximum(0,scores[np.arange(end-start),chosen])
            v[:target]=next_v
    profile = portfolio_profile(s, actions, policy)
    label = {"research": "Custom optimized betting plan", "even": "Adaptive even-money",
             "dozen": "Adaptive dozen / column", "sixline": "Adaptive six-line",
             "groups": "Adaptive equal-group portfolios"}[kind]
    profile.update(key=kind, label=label, base=None, method="Verified research policy" if kind == "research" else "Finite-horizon candidate optimization",
                   scope="Best within the tested candidate set; not a global roulette optimum.")
    return profile, actions, policy


@one_calculation_at_a_time
@lru_cache(maxsize=4 if HOSTED_DEMO else 12)
def compare(s=Scenario()):
    began = time.perf_counter()
    rows, curves, notices = [], {}, []
    one_bet = max(s.minimum, s.target)
    if one_bet <= min(s.maximum, s.loss_limit):
        pmf={one_bet:s.p,-one_bet:18/37 if s.wheel=='french' else 1-s.p}
        if s.wheel=='french':pmf[-one_bet/2]=1/37
        profile = summarize(pmf,s,1.,one_bet)
        profile.update(key="oneshot",label="One-shot even-money",base=one_bet,
                       method="One wager, then stop",scope="Stop after the first settled spin, whether it wins or loses.")
        rows.append(profile)
    for name, label in LABELS.items():
        values = []
        for base in range(s.minimum, min(s.maximum, s.loss_limit) + 1, s.chip):
            success, mean = classic_value(s, name, base)
            values.append(dict(base=base, success=success, mean=mean))
        best_p = max(r["success"] for r in values)
        winner = max((r for r in values if abs(r["success"] - best_p) < 1e-13), key=lambda r: r["mean"])
        profile = classic_profile(s, name, winner["base"])
        if abs(profile["success"] - winner["success"]) > 1e-10:
            raise ArithmeticError("Independent probability calculations disagree.")
        profile.update(key=name, label=label, base=winner["base"], method="All legal base bets evaluated", scope=RULES[name])
        rows.append(profile)
        curves[name] = values
    for kind in (["even", "dozen", "sixline", "research"] if s == Scenario() else ["even", "dozen", "sixline", "groups"]):
        try:
            rows.append(adaptive(s, kind)[0])
        except ValueError as exc:
            notices.append(f"{dict(even='Adaptive even-money',dozen='Adaptive dozen / column',sixline='Adaptive six-line',groups='Adaptive equal-group portfolios',research='Custom optimized betting plan')[kind]}: {exc}")
    rows.sort(key=lambda r: r["success"], reverse=True)
    payload = dict(scenario=asdict(s), rows=rows, curves=curves, notices=notices,
                   elapsed_seconds=time.perf_counter() - began,
                   assumptions=s.zero_rule+" Independent spins. Target is at least the requested net profit. Stop at the spin limit, or when the next prescribed total wager violates the table or loss limit. Minimum applies per occupied position.")
    payload["id"] = sha256(json.dumps(asdict(s), sort_keys=True).encode()).hexdigest()[:12]
    return payload


def cycle(s, name, base):
    if name not in LABELS or base < s.minimum or base > s.maximum or base % s.chip:
        raise ValueError("Choose a legal base bet and a named progression.")
    stakes, _, li = structure(name, base, s)
    i = 0
    losses = 0
    rows = []
    for n in range(1, min(s.spins, 20) + 1):
        bet = int(stakes[i]) * base
        if bet > s.maximum or losses + bet > s.loss_limit:
            reason = "Table maximum" if bet > s.maximum else "Loss limit / bankroll"
            return dict(rows=rows, stop=f"Next required wager ${bet:,} is blocked by the {reason.lower()}.")
        rows.append(dict(step=n, bet=bet, losses_before=losses, profit_if_win=bet - losses, loss_if_lose=losses + bet))
        losses += bet
        i = int(li[i])
    return dict(rows=rows, stop="Spin limit reached." if s.spins <= 20 else "Showing the first 20 consecutive-loss steps.")


def betting_positions():
    result = {}
    def add(key, label, nums):
        result[key] = dict(label=label, numbers=list(nums), multiplier=36 // len(nums))
    for i in range(37):
        add(f"straight:{i}", f"Straight · {i}", [i])
    for row in range(12):
        add(f"street:{row}", f"Street · {row*3+1}–{row*3+3}", range(row*3+1, row*3+4))
        for col in range(2):
            a = row*3+col+1
            add(f"split:h:{row}:{col}", f"Split · {a}/{a+1}", [a, a+1])
        if row < 11:
            add(f"sixline:{row}", f"Six-line · {row*3+1}–{row*3+6}", range(row*3+1, row*3+7))
            for col in range(3):
                a = row*3+col+1
                add(f"split:v:{row}:{col}", f"Split · {a}/{a+3}", [a, a+3])
            for col in range(2):
                a = row*3+col+1
                add(f"corner:{row}:{col}", f"Corner · {a}/{a+1}/{a+3}/{a+4}", [a,a+1,a+3,a+4])
    for i in (1,2,3):
        add(f"split:zero:{i}", f"Split · 0/{i}", [0,i])
    add("trio:012", "Trio · 0/1/2", [0,1,2])
    add("trio:023", "Trio · 0/2/3", [0,2,3])
    add("firstfour", "First four · 0/1/2/3", [0,1,2,3])
    red = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
    for key, nums in [("red", red), ("black", set(range(1,37))-red), ("odd",range(1,37,2)), ("even",range(2,37,2)), ("low",range(1,19)), ("high",range(19,37))]:
        add(key, key.title(), sorted(nums))
    for i in range(3):
        add(f"dozen:{i}", f"Dozen {i+1}", range(i*12+1,i*12+13))
        add(f"column:{i}", f"Column {i+1}", range(i+1,37,3))
    return result


POSITIONS = betting_positions()


def inspect_policy(s, kind, bankroll, spins_left):
    for value in (bankroll,spins_left):
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
            raise ValueError("Use a finite remaining bankroll and spin count.")
    if bankroll % s.cash_unit or spins_left!=int(spins_left) or not 0<=spins_left<=s.spins:
        raise ValueError("Remaining bankroll must match the cash settlement unit; remaining spins must be whole and fit the scenario.")
    reserve = s.bankroll - s.loss_limit
    if bankroll < reserve:
        raise ValueError("This bankroll would breach the protected loss limit.")
    if bankroll >= s.bankroll+s.target:
        return dict(stop="Profit target already reached.")
    if bankroll-reserve < s.minimum or spins_left == 0:
        return dict(stop="No legal wager remains, or the spin limit has been reached.")
    _, actions, policy = adaptive(s,kind)
    unit=actions[0].get('_unit',s.chip)
    if (bankroll-reserve)%unit:
        raise ValueError(f"This policy's reachable bankrolls use ${unit:g} settlement units. Use the same strategy from the start of the scenario.")
    a=actions[int(policy[int(spins_left),round((bankroll-reserve)/unit)])]
    if a['total']*unit > bankroll-reserve:
        return dict(stop="The next wager is blocked by the loss limit.")
    desc=a['description']
    if 'numbers' in desc:
        amounts=[units*s.chip for units in desc['stakes_units']] if 'stakes_units' in desc else desc['stakes']
        entries=[dict(numbers=nums,amount=amount) for nums,amount in zip(desc['numbers'],amounts)]
    else:
        k,m=desc['group_size'],desc['positions']
        groups={1:[[i] for i in range(36)],2:[[b+c,b+c+3] for b in range(1,36,6) for c in range(3)],
                3:[list(range(b,b+3)) for b in range(1,36,3)],4:[[b,b+1,b+3,b+4] for b in range(1,36,6)],
                6:[list(range(b,b+6)) for b in range(1,36,6)],12:[list(range(b,b+12)) for b in [1,13,25]],18:[POSITIONS['red']['numbers']]}
        entries=[dict(numbers=nums,amount=desc['each']) for nums in groups[k][:m]]
    return dict(total=a['total']*unit,entries=entries,
        outcomes=[dict(net=d*unit,probability=c/s.pockets,bankroll=bankroll+d*unit) for d,c in zip(a['deltas'],a['counts'])],
        note="Equivalent numbered layouts can have the same probability. This is a conditional policy lookup, not a prediction of the next result.")


def custom_portfolio(s, entries):
    if s.wheel not in ('single','french'):
        raise ValueError("The custom numbered-layout builder supports European and French single-zero layouts. All four wheels support named strategies and adaptive standard bets; 00/000 custom layouts are not modeled.")
    if not entries or len(entries) > 12:
        raise ValueError("Add between 1 and 12 positions.")
    amounts = defaultdict(int)
    for entry in entries:
        if entry.get("position") not in POSITIONS:
            raise ValueError("Unknown betting position.")
        amount = entry.get("amount")
        if not isinstance(amount, (int, float)) or isinstance(amount, bool) or not math.isfinite(amount) or amount != int(amount) or amount < s.minimum or amount % s.chip:
            raise ValueError("Each position must meet the minimum and use whole chips.")
        amounts[entry["position"]] += int(amount)
    cost = sum(amounts.values())
    if cost > min(s.maximum, s.loss_limit):
        raise ValueError("Total portfolio wager exceeds the table maximum or loss limit.")
    unit=s.cash_unit
    returns = np.zeros(s.pockets, dtype=float)
    for key, amount in amounts.items():
        p = POSITIONS[key]
        returns[p["numbers"]] += amount * p["multiplier"]
        if s.wheel=='french' and len(p['numbers'])==18:
            returns[0]+=amount/2
    net = returns - cost
    deltas, counts = np.unique(np.rint(net/unit).astype(int),return_counts=True)
    target=round((s.loss_limit+s.target)/unit)
    action=dict(total=round(cost/unit),deltas=[int(d) for d in deltas],counts=[int(c) for c in counts],_unit=unit)
    profile = portfolio_profile(s, [action], np.zeros((s.spins+1, target), dtype=np.int32))
    return dict(total=cost, outcomes=[dict(number=str(i),net=float(n)) for i,n in enumerate(net)],
                one_spin_profit=float(np.mean(net>0)), one_spin_mean=float(net.mean()), profile=profile,
                policy="Repeat this exact portfolio after each spin; stop if its full wager cannot be placed.")


def policy_snapshot(s, kind, bankroll, spins_left):
    """Conditional final-session results following the same policy from this state."""
    decision=inspect_policy(s,kind,bankroll,spins_left)
    if decision.get('stop'):
        profit=bankroll-s.bankroll
        stats=summarize({profit:1.},s,0.,0.,expected_loss=-profit)
    else:
        _,actions,policy=adaptive(s,kind)
        stats=portfolio_profile(s,actions,policy,bankroll,int(spins_left))
    return dict(**decision,stats=stats,bankroll=bankroll,spins_left=spins_left,
                net_profit=bankroll-s.bankroll,target_remaining=max(0,s.bankroll+s.target-bankroll),
                loss_room=bankroll-(s.bankroll-s.loss_limit))


def settle_policy(s,kind,bankroll,spins_left,outcome_index):
    """Record one user-reported payout; never sample or place a wager."""
    decision=inspect_policy(s,kind,bankroll,spins_left)
    if decision.get('stop'):
        raise ValueError(decision['stop'])
    if isinstance(outcome_index,bool) or not isinstance(outcome_index,int) or not 0<=outcome_index<len(decision['outcomes']):
        raise ValueError('Choose one of the displayed outcomes.')
    outcome=decision['outcomes'][outcome_index]
    return outcome['bankroll'],int(spins_left)-1,outcome['net']


def record_policy_step(s,kind,bankroll,spins_left,outcome_index,history):
    bank,left,net=settle_policy(s,kind,bankroll,spins_left,outcome_index)
    history=list(history or [])
    if history and not can_undo_policy(s,kind,bankroll,spins_left,history):
        history=[]
    decision=inspect_policy(s,kind,bankroll,spins_left)
    loss_probability=sum(o['probability'] for o in decision['outcomes'] if o['net']<0)
    history.append(dict(scenario=asdict(s),kind=kind,before=[bankroll,spins_left],after=[bank,left],net=net,loss_probability=loss_probability))
    return bank,left,net,history


def can_undo_policy(s,kind,bankroll,spins_left,history):
    return bool(history and history[-1]['scenario']==asdict(s) and history[-1]['kind']==kind
                and history[-1]['after']==[bankroll,spins_left])


def undo_policy_step(s,kind,bankroll,spins_left,history):
    if not can_undo_policy(s,kind,bankroll,spins_left,history):
        raise ValueError('No recorded result to undo for the current tracker state.')
    bank,left=history[-1]['before']
    return bank,left,list(history[:-1])

def policy_loss_stats(history):
    """Probability of negative-net spins along this realized policy path."""
    history=list(history or [])
    losses=[h for h in history if h['net']<0]
    streak=[]
    for h in reversed(history):
        if h['net']>=0:break
        streak.append(h)
    return dict(recorded_spins=len(history),losing_spins=len(losses),
                gross_losses=-sum(h['net'] for h in losses),
                streak=len(streak),streak_loss=-sum(h['net'] for h in streak),
                streak_probability=math.prod(h['loss_probability'] for h in streak) if streak else None)
