import json
import os
import re

from google import genai

MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()
ROUTES = ["expectation_gap", "term_confusion", "pause_or_reduce", "failed_debit", "market_fall_worry", "unclear"]
EXPL = {
    "expectation_gap": "A SIP puts money in every month, so at month N most of your money has only been invested for a few months. A yearly percentage needs about a year of the full amount to show up, so early figures look small even when nothing is wrong. Values also move up and down with the market.",
    "term_confusion": "Absolute return is the plain gain on what you have put in so far. XIRR (annualised return) turns that into a yearly rate that accounts for when each instalment went in. Under about 12 months it can swing a lot on small amounts, so treat it as a rough signal, not a verdict.",
    "pause_or_reduce": "Many apps let you change the amount, skip an instalment or pause a SIP before cancelling. Options differ by app and fund house, so check the SIP details screen or the app's help centre. This is information, not a suggestion to do either.",
    "failed_debit": "A failed instalment is usually a bank or mandate issue, such as low balance on the debit date, a mandate limit or an expired mandate. Check your bank balance, the SIP status in the app, and the help centre for how to retry.",
    "market_fall_worry": "Fund values move up and down, and a fall in the early months shows as a lower figure even while your instalments keep buying units. This explains how it works. It does not predict what happens next or say what to do.",
}
HARD = re.compile(r"which fund|best fund|good fund|recommend|suggest|forecast|predict|will i (get|earn|make)|how much will|guarantee|\btax|nifty|which stock", re.I)
BANNED = re.compile(r"you should|i recommend|guarantee|will earn|will grow|hurry|last chance|miss out|act now|too late|\bbuy\b|\bsell\b|stop your sip|cancel your sip", re.I)
NUM = r"\d[\d,]*(?:\.\d+)?"
_CLIENTS = {}


def illustration(n, rates=(0.06, 0.08, 0.12)):
    """Gain % on money invested after n equal monthly instalments at a steady yearly rate, valued a month after the last one."""
    out = []
    for r in rates:
        m = (1 + r) ** (1 / 12) - 1
        out.append((r, sum((1 + m) ** a - 1 for a in range(1, n + 1)) / n))
    return out


def _gen(prompt, key, temp, json_mode=False):
    cfg = {"temperature": temp}
    if json_mode:
        cfg["response_mime_type"] = "application/json"
    if key not in _CLIENTS:
        _CLIENTS[key] = genai.Client(api_key=key)
    return _CLIENTS[key].models.generate_content(model=MODEL, contents=prompt, config=cfg).text.strip()

def route(text, key):
    """Returns (route, confidence). 'out_of_scope' is decided by rules before any model call."""
    if HARD.search(text):
        return "out_of_scope", 1.0
    p = f"""Classify an investor's worry about their SIP into exactly one of {ROUTES}.
expectation_gap: returns lower or slower than expected. term_confusion: confused by XIRR, absolute vs annualised, or other terms.
pause_or_reduce: wants to pause, skip, reduce or cancel, or cannot find how. failed_debit: instalment failed, missed alert, mandate problem.
market_fall_worry: worried because markets fell. unclear: none of these, or not about an existing SIP.
Return only JSON {{"route": "...", "confidence": 0 to 1}}.
Text: {json.dumps(text[:600], ensure_ascii=False)}"""
    d = json.loads(_gen(p, key, 0, True))
    d = d[0] if isinstance(d, list) else d
    rt = d.get("route") if d.get("route") in ROUTES else "unclear"
    return rt, float(d.get("confidence") or 0)


def explain(rt, facts, worry, key):
    """Returns (text, mode). AI text is used only if it passes the checks, else the vetted text."""
    base = EXPL[rt]
    try:
        p = f"""Write a short, warm, plain-English reply (under 110 words) for a first-time SIP investor.
Worry: {json.dumps(worry[:400], ensure_ascii=False)}
Use ONLY these numbers: {json.dumps(facts)}
Ground it in this vetted explanation and do not contradict it: {base}
Rules: no advice, no recommendations, no predictions of future returns, no urgency or fear, no fund names. Do not tell them to continue, stop or change anything."""
        t = _gen(p, key, 0.2)
        allowed = {round(float(x.replace(",", "")), 1) for x in re.findall(NUM, base + json.dumps(facts))}
        used = {round(float(x.replace(",", "")), 1) for x in re.findall(NUM, t)}
        if used <= allowed and not BANNED.search(t) and len(t.split()) <= 150:
            return t, "AI reply, passed number and language checks"
    except Exception:
        pass
    return base, "Vetted explainer (the AI reply was unavailable or failed a check)"
