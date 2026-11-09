"""Run the router on the hand-labelled golden set. Usage: python eval_router.py path/to/golden_labeled.csv
Writes eval_results.json, which the Quality tab reads. Needs GEMINI_API_KEY in .env"""
import json, os, sys, time
import pandas as pd
from dotenv import load_dotenv
load_dotenv()
import core

MAP = {"expectation_mismatch": "expectation_gap", "uncertainty": "term_confusion",
       "mandate_failure": "failed_debit", "cash_flow": "pause_or_reduce"}
g = pd.read_csv(sys.argv[1] if len(sys.argv) > 1 else "golden_labeled.csv")
g = g[g["gold_relevant"].astype(str).str.lower() == "true"]
rows, skipped = [], 0
for _, r in g.iterrows():
    exp = MAP.get(str(r.get("gold_reason_category")))
    if not exp:
        skipped += 1
        continue
    rt, conf = core.route(str(r["text"]), os.environ["GEMINI_API_KEY"])
    rows.append({"item": r["item_id"], "expected": exp, "got": rt, "confidence": round(conf, 2), "correct": rt == exp})
    time.sleep(6)
n = len(rows)
res = {"n": n, "skipped": skipped,
       "accuracy": sum(x["correct"] for x in rows) / n if n else 0,
       "fallback_rate": sum(x["got"] in ("unclear", "out_of_scope") or x["confidence"] < 0.7 for x in rows) / n if n else 0,
       "rows": rows}
json.dump(res, open("eval_results.json", "w"), indent=2)
print({k: v for k, v in res.items() if k != "rows"})
