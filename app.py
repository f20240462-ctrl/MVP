import json
import os

import pandas as pd
import streamlit as st

import core

st.set_page_config(page_title="SIP Checkin", layout="centered")
HERE = os.path.dirname(os.path.abspath(__file__))
SOURCES = "Official sources: AMFI investor corner (amfiindia.com), SEBI investor resources (sebi.gov.in), and your app's help centre."


def get_key():
    try:
        return st.secrets["GEMINI_API_KEY"]
    except Exception:
        return os.environ.get("GEMINI_API_KEY")


st.title("SIP Checkin")
st.caption("Explains what your own SIP numbers mean at your stage. Not investment advice: it does not recommend funds, "
           "predict returns or tell you what to do. Please do not enter account numbers, PAN or personal details.")
t1, t2 = st.tabs(["Check in", "Quality"])

with t1:
    a, b = st.columns(2)
    months = a.slider("Months since your first instalment", 1, 12, 6)
    amt = b.number_input("Monthly SIP amount (₹)", 100, 1000000, 2000, 100)
    current = a.number_input("Current value shown in your app (₹)", 0, 10000000, 12000, 100)
    hope = b.selectbox("Yearly return you had in mind", ["Not sure", "Below 6%", "6% to 12%", "12% to 15%", "Above 15%"])
    worry = st.text_area("What is on your mind? (optional)", max_chars=400, placeholder="For example: my returns look tiny, is something wrong?")
    st.session_state.setdefault("n", 0)
    if st.button("Check my SIP", type="primary"):
        invested = amt * months
        gain = current - invested
        pct = 100 * gain / invested if invested else 0
        facts = {"months": months, "monthly_amount": amt, "invested": invested, "current_value": current,
                 "gain_amount": gain, "gain_percent": round(pct, 1)}
        st.subheader("Your numbers")
        c = st.columns(3)
        c[0].metric("Invested so far", f"₹{invested:,.0f}")
        c[1].metric("Shown in app", f"₹{current:,.0f}")
        c[2].metric("Gain so far", f"{pct:.1f}%", f"₹{gain:,.0f}")
        st.caption("Assumes every monthly instalment went through.")
        st.subheader(f"Why the figure is small this early (month {months})")
        rows = [{"If a fund grew steadily at": f"{r:.0%} a year", f"You would see after {months} months": f"{g:.1%}",
                 f"On ₹{invested:,.0f} invested": f"₹{g * invested:,.0f}"} for r, g in core.illustration(months)]
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        st.caption("Arithmetic only, to show how monthly instalments work. Not a forecast or a promise: real funds rise and fall. "
                   f"Most of your money has been invested for only about {(months + 1) / 2:.1f} months on average."
                   + (f" You had {hope} a year in mind: a yearly rate needs about a year of the full amount to show up." if hope != "Not sure" else ""))
        if worry.strip():
            key = get_key()
            if st.session_state.n >= 10:
                st.warning("Demo limit reached for this session. Refresh the page to continue.")
            elif not key:
                st.error("No API key is set on the server.")
            else:
                st.session_state.n += 1
                try:
                    rt, conf = core.route(worry.strip(), key)
                except Exception:
                    rt, conf = "unclear", 0.0
                if rt in ("out_of_scope", "unclear") or conf < 0.7:
                    msg = ("I can't recommend funds, predict returns or advise on tax, and I can't tell you whether to stop or continue."
                           if rt == "out_of_scope" else "I'm not sure what you're asking, so I won't guess.")
                    st.info(f"{msg} {core.SOURCES if hasattr(core, 'SOURCES') else SOURCES}")
                else:
                    text, mode = core.explain(rt, facts, worry.strip(), key)
                    st.subheader("About your question")
                    st.write(text)
                    st.caption(f"Topic: {rt.replace('_', ' ')} (confidence {conf:.2f}). {mode}.")
        with st.expander("Options besides cancelling"):
            st.write(core.EXPL["pause_or_reduce"])

with t2:
    st.write("How the AI part is kept in check:")
    st.markdown("- **Rules before AI:** questions about fund picks, return predictions or tax are declined without calling the model.\n"
                "- **Router with a confidence gate:** below 0.70 or unclear, it says so and points to official sources.\n"
                "- **Output checks:** the AI reply is shown only if every number comes from your inputs or the vetted text and it has no advice or urgency language. Otherwise the vetted explainer is shown.\n"
                "- **Without AI** this would be a static FAQ the user has to navigate. The AI routes free-text worries, including Hinglish, to the right explainer and ties it to the user's own numbers.")
    p = os.path.join(HERE, "eval_results.json")
    if os.path.exists(p):
        e = json.load(open(p, encoding="utf-8"))
        st.subheader("Router accuracy on the golden set")
        st.metric("Correct", f"{e['accuracy']:.0%}", f"{e['n']} golden items with a matching topic")
        st.write(f"Fallback rate: {e['fallback_rate']:.0%}. Items skipped (no matching topic): {e['skipped']}.")
        st.dataframe(pd.DataFrame(e["rows"]), hide_index=True, use_container_width=True)
    else:
        st.info("Run eval_router.py to add golden set results.")
