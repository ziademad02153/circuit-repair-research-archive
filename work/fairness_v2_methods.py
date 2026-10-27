"""Untuned frozen learner versus explicit, optimized, nonlearned rankings."""
from __future__ import annotations
import time
from decisive_engine import (ROOT, Deadline, check_time, load_model, full_inputs,
                             full_values, mismatch, cegis)
from circuit_pilot import apply, legal_edits, signals, lut
from local_repair_pilot import local_features
import numpy as np

RULES = ['local_improvement', 'local_after_error', 'sample_error']
METHODS = ['learned', *RULES, 'random', 'exhaustive', 'cegis']


def need_context(c, rows, target):
    """Same backward Boolean needs as frozen features; no feature matrix."""
    mask = (1 << len(rows)) - 1
    val = signals(c, rows)
    zero = [0] * len(val); one = [0] * len(val)
    for signal, t in zip(c.outputs, target):
        zero[signal] |= mask ^ t; one[signal] |= t
    for j in reversed(range(len(c.gates))):
        if j == c.stuck: continue
        z, o = zero[c.n+j], one[c.n+j]
        if not (z | o): continue
        a, b, table = c.gates[j]
        for parent, other, left in [(a, val[b], True), (b, val[a], False)]:
            out0 = lut(0, other, table, mask) if left else lut(other, 0, table, mask)
            out1 = lut(mask, other, table, mask) if left else lut(other, mask, table, mask)
            bad0 = (z & out0) | (o & (mask ^ out0))
            bad1 = (z & out1) | (o & (mask ^ out1))
            zero[parent] |= bad1 & (mask ^ bad0)
            one[parent] |= bad0 & (mask ^ bad1)
    return val, zero, one, mask


def local_rule_keys(c, edits, rows, target, start, budget):
    val, zero, one, mask = need_context(c, rows, target)
    # Use the exact floating operations of local_features for identical ties.
    improve = np.empty(len(edits)); afters = np.empty(len(edits)); distance = np.empty(len(edits))
    size = len(rows)
    for idx, (kind, j, slot, value) in enumerate(edits):
        if idx % 128 == 0: check_time(start, budget)
        a, b, table = c.gates[j]; z, o = zero[c.n+j], one[c.n+j]
        aa = val[value] if kind == 'wire' and slot == 0 else val[a]
        bb = val[value] if kind == 'wire' and slot == 1 else val[b]
        nt = value if kind == 'lut' else table
        new = lut(aa, bb, nt, mask)
        before = ((z & val[c.n+j]) | (o & (mask ^ val[c.n+j]))).bit_count()/size
        after = ((z & new) | (o & (mask ^ new))).bit_count()/size
        improve[idx] = before-after; afters[idx] = after
        distance[idx] = (table ^ nt).bit_count()/4
    return improve, afters, distance


def sample_error_keys(c, edits, rows, target, start, budget):
    """Exact sample errors; only reevaluate descendants of the edited gate.

    No global feature matrix and no complete truth table or gold circuit.
    This is a stronger implementation of the old global-sample greedy rule.
    """
    base = signals(c, rows); mask = (1 << len(rows))-1; cones = []
    for j in range(len(c.gates)):
        affected = {c.n+j}; cone = [j]
        for k in range(j+1, len(c.gates)):
            a, b, _ = c.gates[k]
            if k != c.stuck and (a in affected or b in affected):
                affected.add(c.n+k); cone.append(k)
        cones.append(cone)
    errors = np.empty(len(edits)); distance = np.empty(len(edits))
    for idx, edit in enumerate(edits):
        if idx % 32 == 0: check_time(start, budget)
        kind, j, slot, value = edit
        a, b, table = c.gates[j]; old_table = table
        if kind == 'lut': table = value
        elif slot == 0: a = value
        else: b = value
        vals = base.copy(); vals[c.n+j] = lut(vals[a], vals[b], table, mask)
        for k in cones[j][1:]:
            x, y, t = c.gates[k]; vals[c.n+k] = lut(vals[x], vals[y], t, mask)
        errors[idx] = sum((vals[o] ^ t).bit_count() for o, t in zip(c.outputs, target))
        distance[idx] = (old_table ^ table).bit_count()/4
    return errors, distance


def ranking(c, edits, rows, target, seed, method, model, start, budget):
    """Deliberately has no gold, complete target or repair-label arguments."""
    times = {}; t = time.perf_counter()
    tie = np.random.default_rng(seed+17).random(len(edits))
    if method == 'learned':
        X = local_features(c, edits, rows, target); check_time(start, budget)
        times['feature_seconds'] = time.perf_counter()-t; t = time.perf_counter()
        scores = model.predict_proba(X)[:, 1]; check_time(start, budget)
        times['inference_seconds'] = time.perf_counter()-t; t = time.perf_counter()
        order = np.lexsort((tie, -scores))
    elif method in ['local_improvement', 'local_after_error']:
        improve, after, distance = local_rule_keys(c, edits, rows, target, start, budget)
        times['feature_seconds'] = time.perf_counter()-t; t = time.perf_counter()
        order = np.lexsort((tie, distance, -improve if method == 'local_improvement' else after))
    elif method == 'sample_error':
        errors, distance = sample_error_keys(c, edits, rows, target, start, budget)
        times['feature_seconds'] = time.perf_counter()-t; t = time.perf_counter()
        order = np.lexsort((tie, distance, errors))
    elif method == 'random': order = np.argsort(tie)
    else: raise ValueError(method)
    times['sorting_seconds'] = time.perf_counter()-t; check_time(start, budget)
    return order, times


def run_method(payload, method, model, start, budget, emit, z3):
    if method == 'cegis': return cegis(payload, start, budget, emit, z3)
    c = payload['c']; metrics = {}
    if method == 'exhaustive': candidates = legal_edits(c)
    else:
        t = time.perf_counter(); edits = list(legal_edits(c)); check_time(start, budget)
        metrics['candidate_generation_seconds'] = time.perf_counter()-t
        order, times = ranking(c, edits, payload['rows'], payload['sample_target'], payload['seed'], method, model, start, budget)
        metrics.update(times); metrics['candidate_count'] = len(edits)
        emit({'phase':'ranked', **metrics})
        candidates = (edits[int(i)] for i in order)
    check_start = time.perf_counter(); checks = 0
    for edit in candidates:
        check_time(start, budget); new = apply(c, edit); checks += 1
        passed = mismatch(new, payload['target_full']) is None
        check_time(start, budget)
        if passed:
            return {'status':'accepted', 'edit':edit, 'checks':checks,
                    'checking_seconds':time.perf_counter()-check_start, **metrics}
        if checks % 64 == 0: emit({'phase':'checking', 'checks':checks})
    return {'status':'exhausted', 'checks':checks,
            'checking_seconds':time.perf_counter()-check_start, **metrics}


def independent_values(c):
    """Independent NumPy truth-vector evaluator, no packed LUT implementation."""
    rows = np.arange(1 << c.n, dtype=np.uint32)
    vals = [((rows >> i) & 1).astype(np.uint8) for i in range(c.n)]
    for j, (a, b, table) in enumerate(c.gates):
        if j == c.stuck: v = np.full(len(rows), c.stuck_value, dtype=np.uint8)
        else: v = ((table >> (vals[a]+2*vals[b])) & 1).astype(np.uint8)
        vals.append(v)
    return tuple(int.from_bytes(np.packbits(vals[o], bitorder='little').tobytes(), 'little') for o in c.outputs)


def worker(pipe):
    import gc, traceback, z3
    started = time.perf_counter(); model = load_model()
    for n in [4,6,10,12,16]: full_inputs(n)
    pipe.send({'event':'ready', 'model_and_input_warmup_seconds':time.perf_counter()-started,
               'z3_version':z3.get_version_string()})
    while True:
        command = pipe.recv()
        if command is None: return
        payload, method, budget = command; gc.collect()
        pipe.send({'event':'started'})  # Before timer; no progress IPC inside timed work.
        events = []; start = time.perf_counter()
        def emit(d): events.append({'elapsed':time.perf_counter()-start, **d})
        try: result = run_method(payload, method, model, start, budget, emit, z3)
        except Deadline: result = {'status':'timeout', 'last_progress':events[-1] if events else {}}
        except Exception as exc: result = {'status':'error', 'error':repr(exc), 'traceback':traceback.format_exc()}
        elapsed = time.perf_counter()-start
        if elapsed > budget and result['status'] != 'error':
            result = {'status':'timeout', 'over_budget_result':result}
        pipe.send({'event':'result', 'elapsed':elapsed, 'progress_events':events, **result})
