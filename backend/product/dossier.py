"""
The referral dossier (Person B, investigation 4.4): one PDF an officer can hand to the investigating agency.

It pulls together what the case holds: the money trail, where it ended, suspected mules, every identifier, every request
and reply, the linked cases and the people the replies name, and an evidence checklist that separates RECORDS (what an
institution or the chain told us) from INFERENCES (our scores and links) from what is still MISSING.

It does not include the victim's name, phone or other personal details (they stay on the complaint record). It does not
say anyone is guilty. Any arrest or legal action is for the agency. Every reply in this demo is fictional, and the
dossier says so. A SHA-256 of the dossier's data is printed on every page and stored if the case is referred.
"""
import hashlib
import json
import time
from io import BytesIO
from typing import Dict, List, Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, SimpleDocTemplate, Spacer

from product import ledger, outcomes, people, reports, store
from product.notices import ist
from product.reports import BODY, H1, H2, MUTED, MUTED_P, SMALL, _p, _t, _table
from product.recommendations import amount

LIMITS = [
    "Exchange and entity labels come from a small public label list and are not independently verified.",
    "Risk scores, suspected-mule flags, links between cases and the people named are INFERENCES for an officer to check. They are not findings.",
    "A holder of a mule account is often a victim who was tricked or paid. Nothing here says that anyone is guilty.",
    "Only the replies of institutions and the transactions on the chain are records. Everything else is our reading of them.",
    "Letters were drafts with placeholder legal references, to be completed by the issuing officer.",
    "Any arrest, search, seizure or other legal action is for the investigating agency, under the law that applies.",
    "In this demo every reply from an institution is FICTIONAL and no request was transmitted.",
]


def data(case_id: str) -> Optional[Dict]:
    """Everything the dossier says, as plain data (also what the hash is taken over)."""
    trace, case = store.get_trace(case_id), store.get_case(case_id)
    if trace is None or case is None:
        return None
    requests = store.list_requests(case_id)
    replies = {r.request_id: store.get_reply(r.request_id) for r in requests}
    return {
        "case": case.model_dump(mode="json"), "evidence_hash": reports.evidence_hash(trace),
        "outcomes": [o.model_dump(mode="json") for o in outcomes.outcomes(case_id)],
        "mules": [m.model_dump(mode="json") for m in outcomes.mules(case_id)],
        "identifiers": [i.model_dump(mode="json") for i in store.list_identifiers(case_id)],
        "leads": [l.model_dump(mode="json") for l in ledger.leads(case_id)],
        "requests": [r.model_dump(mode="json", exclude={"letter_body"}) for r in requests],
        "replies": [rp.model_dump(mode="json", exclude={"received_at"}) for rp in replies.values() if rp],
        "people": people.case_people(case_id).model_dump(mode="json"),
    }


def dossier_hash(d: Dict) -> str:
    return hashlib.sha256(json.dumps(d, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def checklist(case_id: str, d: Dict) -> Dict[str, List[str]]:
    """Records, inferences, and what is still missing."""
    trace = store.get_trace(case_id)
    records = [f"On-chain transfers: {len(trace.graph.edges)} transfers between {len(trace.graph.nodes)} wallets ({trace.source.upper()} data)."]
    inferences = []
    if trace.nearest_vasp:
        v = trace.nearest_vasp
        inferences.append(f"Exchange attribution: {v.vasp}, {v.method}, confidence {v.confidence:.0%} (labels unverified).")
    mules = [m for m in d["mules"] if m["kind"] == "wallet"]
    if mules:
        inferences.append(f"{len(mules)} wallet(s) scored as suspected mules by a model trained on synthetic data.")
    reqs = {r["request_id"]: r for r in d["requests"]}
    for rp in d["replies"]:
        r = reqs[rp["request_id"]]
        records.append(f"{r['holder']}: reply to the {r['kind'].replace('_', ' ')} ({rp['summary']}) [FICTIONAL in this demo].")
    cluster = d["people"]["cluster"]
    if cluster:
        inferences.append(f"Linked to {len(cluster['case_ids']) - 1} other case(s) through {len(cluster['shared'])} shared identifier(s).")
    for p in d["people"]["people"]:
        inferences.append(f"{p['name']} ({'suspected operator' if p['role'] == 'operator_suspected' else 'mule account holder'}): {p['basis']}, confidence {p['confidence']:.0%}.")
    missing = []
    asked = {(r["lead_id"]) for r in d["requests"]}
    for l in d["leads"]:
        if l["lead_id"] not in asked:
            missing.append(f"No request yet to {l['holder']} about the {l['choke_point'].replace('_', ' ')} lead ({l['priority']}).")
    for r in d["requests"]:
        if r["status"] in ("draft", "approved", "sent", "acknowledged"):
            missing.append(f"Request {r['request_id']} to {r['holder']} is {r['status']}: no reply yet.")
    if not any(p["role"] == "operator_suspected" for p in d["people"]["people"]):
        missing.append("No institution has yet named a person behind this case.")
    return {"records": records, "inferences": inferences, "missing": missing}


def build(case_id: str, generated_at: Optional[int] = None) -> Optional[bytes]:
    d = data(case_id)
    if d is None:
        return None
    trace, case = store.get_trace(case_id), store.get_case(case_id)
    digest, generated = dossier_hash(d), generated_at or int(time.time())
    check = checklist(case_id, d)
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=16 * mm, bottomMargin=20 * mm,
                            title=f"ChainTrace referral dossier {case_id}", author="ChainTrace", subject=f"Complaint {trace.complaint_id}",
                            keywords=f"sha256:{digest}")

    def chrome(canvas, dc):
        canvas.saveState()
        w, _ = A4
        canvas.setStrokeColor(reports.LINE)
        canvas.line(15 * mm, 14 * mm, w - 15 * mm, 14 * mm)
        canvas.setFont("Helvetica", 6.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(15 * mm, 10 * mm, f"ChainTrace referral dossier | Case {case_id} | Complaint {trace.complaint_id} | DEMO: replies are fictional")
        canvas.drawRightString(w - 15 * mm, 10 * mm, f"Page {dc.page}")
        canvas.setFont("Courier", 6)
        canvas.drawString(15 * mm, 6.5 * mm, f"SHA-256 (dossier data): {digest}")
        canvas.restoreState()

    S = reports.escape
    story = [_t("Referral dossier", H1), _t("Prepared for the investigating agency. Contains inferences: see the limits at the end.", MUTED_P), Spacer(1, 6),
             _table([["Case", case_id, "Complaint", trace.complaint_id], ["Generated", ist(generated), "Data source", trace.source.upper()],
                     ["Amount lost", f"{amount(case.amount_lost)} USDT", "Fraud type", (case.fraud_type or "-").title()],
                     ["Traced", f"{amount(trace.summary.total_traced)} USDT", "Idle funds", f"{amount(trace.summary.idle_funds)} USDT"]],
                    [28 * mm, 62 * mm, 28 * mm, 62 * mm], header=False, zebra=False)]
    story.append(_p("<b>The victim's name, phone and other personal details are not part of this dossier; they stay on the complaint record.</b>", SMALL))

    story += [_t("1. Where the money went", H2)]
    story.append(_table([["Kind", "What", "Status", "Amount"]] + [
        [_t(o["kind"].replace("_", " "), reports.CELL), _t(o["title"], reports.CELL), _t(o["status"].replace("_", " "), reports.CELL),
         amount(o["amount"]) + " USDT" if o["amount"] else "-"] for o in d["outcomes"]], [26 * mm, 100 * mm, 28 * mm, 26 * mm]))

    story += reports._graph(trace, doc.width)

    story += [_t("3. Suspected mules (suspected only)", H2)]
    mules = d["mules"]
    story.append(_table([["Account", "Type", "Risk", "Received", "Passed on", "Sent to"]] + [
        [_t(m["value"], reports.MONO), _t("Bank account" if m["kind"] == "bank_account" else "Wallet", reports.CELL), m["risk"] or "-",
         amount(m["received"]), amount(m["forwarded"]), ", ".join(m["onward"]) or "-"] for m in mules], [58 * mm, 24 * mm, 18 * mm, 24 * mm, 24 * mm, 32 * mm])
        if mules else _t("No suspected mules.", MUTED_P))

    story += [_t("4. Identifiers", H2)]
    story.append(_table([["Kind", "Value", "Role", "Source", "Confidence"]] + [
        [_t(i["kind"].replace("_", " "), reports.CELL), _t(i["value"] + (f" ({i['label']})" if i["label"] else ""), reports.MONO),
         _t(i["role"].replace("_", " "), reports.CELL), i["source"], f"{round(i['confidence'] * 100)}%"] for i in d["identifiers"]],
        [24 * mm, 76 * mm, 30 * mm, 24 * mm, 24 * mm]))

    story += [_t("5. Requests and replies", H2)]
    if d["requests"]:
        replies = {r["request_id"]: r for r in d["replies"]}
        rows = [["Request", "To", "Kind", "About", "Status"]]
        for r in d["requests"]:
            rows.append([r["request_id"], _t(r["holder"], reports.CELL), _t(r["kind"].replace("_", " "), reports.CELL), _t(r["subject"], reports.MONO), r["status"]])
        story.append(_table(rows, [24 * mm, 42 * mm, 36 * mm, 52 * mm, 24 * mm]))
        for r in d["requests"]:
            rp = replies.get(r["request_id"])
            if rp:
                facts = "; ".join(f"{f['label']}: {f['value']}" for f in rp["fields"])
                story.append(KeepTogether([Spacer(1, 3), _p(f"<b>{S(r['holder'])} replied</b> (FICTIONAL DEMO DATA). {S(rp['summary'])}", SMALL), _t(facts, SMALL)]))
    else:
        story.append(_t("No requests have been sent.", MUTED_P))

    story += [_t("6. Linked cases and suspected people", H2)]
    pe = d["people"]
    if pe["cluster"]:
        c = pe["cluster"]
        story.append(_t(c["summary"] + f". Together: {amount(c['total_lost'])} USDT lost in {', '.join(c['states']) or 'unknown states'}.", BODY))
        story.append(_table([["Shared identifier", "Strength", "Cases"]] + [[_t(f"{s['kind'].replace('_', ' ')}: {s['value']}", reports.CELL), s["strength"], ", ".join(s["case_ids"])] for s in c["shared"]],
                            [90 * mm, 24 * mm, 64 * mm]))
    else:
        story.append(_t("This case shares no identifier with another case.", MUTED_P))
    for p in pe["people"]:
        ev = "; ".join(f"{e['institution']} ({e['field']}, case {e['case_id']})" for e in p["evidence"])
        role = "Suspected operator" if p["role"] == "operator_suspected" else "Holder of a mule account"
        story.append(KeepTogether([Spacer(1, 3), _p(f"<b>{S(p['name'])}</b>: {role}, confidence {round(p['confidence'] * 100)}%. {S(p['basis'])}.", BODY),
                                   _t("Named by: " + ev, SMALL), _t("Linked identifiers: " + (", ".join(p["identifiers"]) or "-"), SMALL)]))

    story += [_t("7. Evidence checklist", H2)]
    for title, key in (("Records: what an institution or the chain told us", "records"), ("Inferences: our reading, to be checked", "inferences"),
                       ("Still missing", "missing")):
        story.append(_p(f"<b>{title}</b>", BODY))
        for line in check[key] or ["None."]:
            story.append(_t("- " + line, SMALL))
        story.append(Spacer(1, 3))

    story += [_t("8. Limits and cautions", H2)] + [_t("- " + x, SMALL) for x in LIMITS]
    doc.build(story, onFirstPage=chrome, onLaterPages=chrome)
    return buf.getvalue()
