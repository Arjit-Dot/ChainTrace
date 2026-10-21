"""
PDF evidence report for a case (Person B), built from the stored trace with ReportLab.

Sections: header, executive summary, fund-flow graph (matplotlib + networkx, same colors as the UI),
transaction table, attribution evidence, wallet risk, recommendations, methodology and limitations.
Every page footer carries the SHA-256 of the case data the report was built from (canonical JSON,
see evidence_hash), so anyone holding the case record can check the report against it.
"""
import hashlib
import json
import time
from io import BytesIO
from typing import List, Optional, Tuple
from xml.sax.saxutils import escape

import networkx as nx
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (Image, KeepTogether, ListFlowable, ListItem, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

from contract.schemas import CaseSummary, Node, TraceResponse
from product.notices import ist, utc
from product.recommendations import CHAIN_NAMES, amount

# Same legend as frontend/src/lib/colors.js. Unknown is white there; on paper it gets a dark outline.
NODE_COLORS = {"victim": "#9ca3af", "scam_wallet": "#ef4444", "intermediary": "#f97316", "bridge": "#3b82f6",
               "mixer": "#a855f7", "exchange": "#22c55e", "dex": "#14b8a6", "bank_account": "#eab308", "unknown": "#f8fafc"}
NODE_LABELS = {"victim": "Victim", "scam_wallet": "Scam wallet", "intermediary": "Intermediary", "bridge": "Bridge",
               "mixer": "Mixer", "exchange": "Exchange", "dex": "DEX (swap)", "bank_account": "Bank account", "unknown": "Unknown"}
NODE_SHAPES = {"exchange": "s", "bridge": "D", "mixer": "h", "dex": "p", "bank_account": "s"}
PATH_GREEN, IDLE_AMBER = "#16a34a", "#f59e0b"
RISK_COLORS = {"Low": "#16a34a", "Medium": "#d97706", "High": "#ea580c", "Critical": "#dc2626"}
SOURCE_TEXT = {
    "live": "LIVE: traced from on-chain data fetched for this case.",
    "cached": "CACHED: traced from on-chain data stored earlier; newer transfers may be missing.",
    "simulated": "SIMULATED: demo data. Addresses, exchanges and transfers are fictional.",
}
INK, MUTED, LINE = colors.HexColor("#111827"), colors.HexColor("#6b7280"), colors.HexColor("#d1d5db")

_ss = getSampleStyleSheet()
H1 = ParagraphStyle("h1", parent=_ss["Title"], fontSize=17, leading=21, alignment=TA_LEFT, spaceAfter=2)
H2 = ParagraphStyle("h2", parent=_ss["Heading2"], fontSize=12, leading=15, spaceBefore=10, spaceAfter=5,
                    textColor=INK)
BODY = ParagraphStyle("body", parent=_ss["BodyText"], fontSize=9, leading=12.5)
SMALL = ParagraphStyle("small", parent=BODY, fontSize=7.5, leading=9.5)
MUTED_P = ParagraphStyle("muted", parent=BODY, textColor=MUTED)
MONO = ParagraphStyle("mono", parent=SMALL, fontName="Courier", fontSize=6.8, leading=8.5)
CELL = ParagraphStyle("cell", parent=SMALL)


# ---------- helpers ----------
def evidence_hash(trace: TraceResponse) -> str:
    """SHA-256 of the case data the report is built from (JSON, sorted keys, no whitespace)."""
    canon = json.dumps(trace.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode()).hexdigest()


def _p(markup: str, style=BODY) -> Paragraph:
    """Paragraph from ReportLab markup (callers escape any data they put in it)."""
    return Paragraph(markup, style)


def _t(text, style=BODY) -> Paragraph:
    """Paragraph from plain text."""
    return Paragraph(escape(str(text)), style)


def _short(addr: str, n: int = 6) -> str:
    return addr if len(addr) <= 2 * n + 3 else f"{addr[:n]}...{addr[-4:]}"


def _who(node: Optional[Node], addr: str) -> str:
    """Address on one line, label below (for table cells)."""
    label = f"<br/><font color='#6b7280'>{escape(node.label)}</font>" if node and node.label else ""
    return f"<font name='Courier'>{escape(_short(addr, 8))}</font>{label}"


def _chain(c: str) -> str:
    return CHAIN_NAMES.get(c, c)


def _humanize(s: Optional[str]) -> str:
    return (s or "unknown").replace("_", " ").capitalize()


def _table(rows, widths, header=True, zebra=True) -> Table:
    t = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
    style = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("FONTSIZE", (0, 0), (-1, -1), 7.5),
             ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
             ("LINEBELOW", (0, 0), (-1, -1), 0.25, LINE)]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
                  ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("LINEBELOW", (0, 0), (-1, 0), 0.8, INK)]
    if zebra:
        style += [("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fafafa")])]
    t.setStyle(TableStyle(style))
    return t


def _path_to_deposit(trace: TraceResponse) -> List[Tuple[str, str]]:
    if not trace.nearest_vasp:
        return []
    g = nx.DiGraph((e.source, e.target) for e in trace.graph.edges)
    try:
        path = nx.shortest_path(g, trace.wallet, trace.nearest_vasp.deposit_address)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return []
    return list(zip(path, path[1:]))


# ---------- graph image ----------
def graph_png(trace: TraceResponse) -> bytes:
    """Left-to-right fund-flow snapshot: columns by hop, colors and shapes as in the UI."""
    nodes = {n.id: n for n in trace.graph.nodes}
    g = nx.DiGraph()
    for n in nodes.values():
        g.add_node(n.id, hop=n.hop)
    for e in trace.graph.edges:  # parallel transfers between two wallets are drawn as one arrow
        if g.has_edge(e.source, e.target):
            g[e.source][e.target]["amount"] += e.amount
        else:
            g.add_edge(e.source, e.target, amount=e.amount, kind=e.edge_type)
    for a, b in g.edges:  # a wallet missing from the node list still gets drawn
        for x in (a, b):
            g.nodes[x].setdefault("hop", 0)

    columns = max(len({d["hop"] for _, d in g.nodes(data=True)}), 1)
    rows = max((sum(1 for _, d in g.nodes(data=True) if d["hop"] == h)
                for h in {d["hop"] for _, d in g.nodes(data=True)}), default=1)
    fig = Figure(figsize=(max(7.5, 1.7 * columns), max(3.2, 0.95 * rows + 1.0)), dpi=200)
    ax = fig.add_subplot()
    ax.set_axis_off()
    pos = nx.multipartite_layout(g, subset_key="hop", align="vertical", scale=1)
    pos = {k: (x, -y) for k, (x, y) in pos.items()}

    path = set(_path_to_deposit(trace))
    top = max((d["amount"] for *_, d in g.edges(data=True)), default=1) or 1
    for (a, b), d in ((edge[:2], edge[2]) for edge in g.edges(data=True)):
        on_path = (a, b) in path
        nx.draw_networkx_edges(
            g, pos, ax=ax, edgelist=[(a, b)], width=0.8 + 3.2 * d["amount"] / top,
            edge_color=PATH_GREEN if on_path else ("#3b82f6" if d["kind"] == "bridge" else "#9ca3af"),
            style="dashed" if d["kind"] in ("bridge", "mixer_in") else "solid",
            arrowsize=9, node_size=520, connectionstyle="arc3,rad=0.04")
    nx.draw_networkx_edge_labels(
        g, pos, ax=ax, edge_labels={(a, b): amount(d["amount"]) for a, b, d in g.edges(data=True)},
        font_size=5.5, font_color="#374151", bbox={"boxstyle": "round,pad=0.15", "fc": "white", "ec": "none"},
        rotate=False, label_pos=0.5)

    for ntype in NODE_COLORS:
        ids = [i for i in g.nodes if (nodes[i].type if i in nodes else "unknown") == ntype]
        if not ids:
            continue
        idle = [i in nodes and nodes[i].idle_balance > 0 for i in ids]
        nx.draw_networkx_nodes(
            g, pos, ax=ax, nodelist=ids, node_shape=NODE_SHAPES.get(ntype, "o"), node_size=520,
            node_color=NODE_COLORS[ntype],
            edgecolors=[IDLE_AMBER if i else ("#374151" if ntype == "unknown" else "white") for i in idle],
            linewidths=[2.6 if i else 0.8 for i in idle])

    for i, (x, y) in pos.items():
        n = nodes.get(i)
        name = "Reported" if n and n.hop == 0 else (n.label.split(" (")[0] if n and n.label else NODE_LABELS[
            n.type if n else "unknown"])
        ax.annotate(f"{name}\n{_short(i, 5)}", (x, y), xytext=(0, -15), textcoords="offset points",
                    ha="center", va="top", fontsize=5.5, color="#111827", linespacing=1.1)

    present = {nodes[i].type if i in nodes else "unknown" for i in g.nodes}
    handles = [Line2D([], [], marker=NODE_SHAPES.get(t, "o"), ls="", markersize=6, color=NODE_COLORS[t],
                      markeredgecolor="#374151" if t == "unknown" else NODE_COLORS[t], label=NODE_LABELS[t])
               for t in NODE_COLORS if t in present]
    if path:
        handles.append(Line2D([], [], color=PATH_GREEN, lw=2, label="Route to Nearest VASP"))
    if any(n.idle_balance > 0 for n in nodes.values()):
        handles.append(Line2D([], [], marker="o", ls="", markersize=6, color="white", markeredgecolor=IDLE_AMBER,
                              markeredgewidth=2, label="Idle funds"))
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.02), ncol=min(len(handles), 5),
              fontsize=6, frameon=False)
    ax.margins(x=0.08, y=0.18)
    fig.tight_layout(pad=0.4)

    buf = BytesIO()
    fig.savefig(buf, format="png", facecolor="white")
    return buf.getvalue()


# ---------- sections ----------
def _header(trace: TraceResponse, case: Optional[CaseSummary], generated: int) -> list:
    meta = [
        ["Case ID", trace.case_id, "Complaint ID", trace.complaint_id],
        ["Reported wallet", _p(f"<font name='Courier'>{escape(trace.wallet)}</font>", CELL), "Chain",
         _chain(trace.chain)],
        ["Report generated", ist(generated), "Trace generated", ist(trace.generated_at)],
        ["Data source", trace.source.upper(), "Case status", _humanize(case.status) if case else "-"],
    ]
    t = Table(meta, colWidths=[28 * mm, 62 * mm, 28 * mm, 62 * mm])
    t.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 8), ("TEXTCOLOR", (0, 0), (0, -1), MUTED),
                           ("TEXTCOLOR", (2, 0), (2, -1), MUTED), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    out = [_t("ChainTrace Evidence Report", H1),
           _t("Crypto fraud fund-flow trace and exchange attribution", MUTED_P), Spacer(1, 6), t]
    out.append(Spacer(1, 4))
    out.append(_p(f"<b>{escape(SOURCE_TEXT[trace.source])}</b>",
                  ParagraphStyle("src", parent=SMALL, textColor=colors.HexColor(
                      "#a21caf" if trace.source == "simulated" else "#0369a1"))))
    if trace.notes:
        out.append(_t(f"Note: {trace.notes}", SMALL))
    return out


def _summary(trace: TraceResponse, case: Optional[CaseSummary]) -> list:
    s, v = trace.summary, trace.nearest_vasp
    lost = case.amount_lost if case else trace.amount_lost
    tiles = [("Amount lost", f"{amount(lost)} USDT" if lost is not None else "-"),
             ("Total traced", f"{amount(s.total_traced)} USDT"),
             ("Idle funds", f"{amount(s.idle_funds)} USDT"),
             ("Hops / wallets", f"{s.hops} / {s.nodes}")]
    t = Table([[_p(f"<font color='#6b7280' size='7'>{k.upper()}</font><br/><b>{escape(val)}</b>",
                   ParagraphStyle("tile", parent=BODY, fontSize=11, leading=14)) for k, val in tiles]],
              colWidths=[45 * mm] * 4)
    t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, LINE), ("INNERGRID", (0, 0), (-1, -1), 0.5, LINE),
                           ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))

    if v:
        finding = (f"Funds from the reported wallet reached <b>{escape(v.vasp)}</b> in {v.hops} hop"
                   f"{'s' if v.hops != 1 else ''}: {amount(v.amount)} USDT arrived at deposit address "
                   f"<font name='Courier'>{escape(v.deposit_address)}</font> on {ist(v.timestamp)}. "
                   f"Attribution confidence <b>{v.confidence:.0%}</b> ({v.method}).")
    else:
        finding = ("No exchange (VASP) was identified in the traced flow. The case stays open for monitoring "
                   "and a re-trace when the funds move.")
    extra = [f"Fraud type: {_humanize(case.fraud_type if case else trace.fraud_type)}",
             f"Typology (engine): {_humanize(trace.typology)}"]
    if trace.urgency:
        extra.append(f"Urgency: {_humanize(trace.urgency)}")
    if case and case.state and case.state != "Unknown":
        extra.append(f"State: {case.state}")
    if s.time_to_attribution_sec is not None:
        extra.append(f"Time to attribution: {s.time_to_attribution_sec:.1f} s")
    out = [_t("1. Executive summary", H2), t, Spacer(1, 6), _p(finding), Spacer(1, 3),
           _p(" &nbsp;|&nbsp; ".join(escape(x) for x in extra), MUTED_P)]
    if trace.urgency_reasons:
        out.append(_t("Why: " + "; ".join(trace.urgency_reasons), SMALL))
    return out


def _graph(trace: TraceResponse, width: float) -> list:
    png = graph_png(trace)
    img = Image(BytesIO(png))
    scale = width / img.imageWidth
    img.drawWidth, img.drawHeight = width, img.imageHeight * scale
    if img.drawHeight > 120 * mm:  # very tall graphs: keep the aspect ratio, fit the height
        img.drawWidth, img.drawHeight = img.drawWidth * 120 * mm / img.drawHeight, 120 * mm
    return [KeepTogether([_t("2. Fund-flow graph", H2), img,
                          _t("Columns are hops from the reported wallet (victims on the left). Arrow width scales "
                             "with amount; dashed arrows are bridge or mixer transfers.", SMALL)])]


def _transactions(trace: TraceResponse) -> list:
    nodes = {n.id: n for n in trace.graph.nodes}
    rows = [["#", "Tx hash", "From", "To", "Amount", "Time (IST / UTC)", "Type"]]
    for i, e in enumerate(sorted(trace.graph.edges, key=lambda e: (e.timestamp, e.tx_hash)), 1):
        rows.append([str(i), _p(escape(e.tx_hash), MONO), _p(_who(nodes.get(e.source), e.source), CELL),
                     _p(_who(nodes.get(e.target), e.target), CELL), _p(f"{amount(e.amount)} {escape(e.token)}", CELL),
                     _p(f"{ist(e.timestamp)}<br/><font color='#6b7280'>{utc(e.timestamp)}</font>", CELL),
                     _t(_humanize(e.edge_type), CELL)])
    t = _table(rows, [7 * mm, 37 * mm, 31 * mm, 31 * mm, 20 * mm, 38 * mm, 16 * mm])
    t.setStyle(TableStyle([("ALIGN", (4, 1), (4, -1), "RIGHT")]))
    return [_t("3. Transactions", H2),
            _t(f"{len(trace.graph.edges)} transfers in the traced graph, oldest first. Full transaction hashes "
               f"can be checked on a {_chain(trace.chain)} block explorer.", MUTED_P), Spacer(1, 3), t]


def _attribution(trace: TraceResponse) -> list:
    v = trace.nearest_vasp
    out = [_t("4. Attribution evidence", H2)]
    if v is None:
        return out + [_t("No exchange was identified, so there is nothing to attribute or freeze yet.")]
    rows = [["Exchange (VASP)", v.vasp], ["Deposit address", _p(f"<font name='Courier'>{escape(v.deposit_address)}"
                                                                f"</font>", CELL)],
            ["Amount received", f"{amount(v.amount)} USDT"], ["Received at", f"{ist(v.timestamp)} ({utc(v.timestamp)})"],
            ["Hops from reported wallet", str(v.hops)], ["Confidence", f"{v.confidence:.0%}"],
            ["Method", "Deterministic: the address matches a labeled exchange wallet" if v.method == "deterministic"
             else "Heuristic: behavioural pattern of an exchange deposit address (confidence below 90%)"],
            ["Compliance contact", v.contact or "-"]]
    t = _table(rows, [45 * mm, 135 * mm], header=False, zebra=False)
    t.setStyle(TableStyle([("TEXTCOLOR", (0, 0), (0, -1), MUTED), ("FONTSIZE", (0, 0), (-1, -1), 8)]))
    bullets = ListFlowable([ListItem(_t(x), leftIndent=10, value="circle") for x in v.evidence],
                           bulletType="bullet", start="-", leftIndent=10, bulletFontSize=7)
    return out + [t, Spacer(1, 5), _p("<b>Evidence</b>"), bullets]


def _risk(trace: TraceResponse) -> list:
    scored = sorted((n for n in trace.graph.nodes if n.risk is not None and n.type != "victim"),
                    key=lambda n: (n.hop, -(n.risk_score or 0)))
    out = [_t("5. Wallet risk", H2)]
    if not scored:
        return out + [_t("No downstream wallets were scored.", MUTED_P)]
    rows = [["Wallet", "Type", "Hop", "Risk", "Score", "Typology", "Reasons"]]
    for n in scored:
        rows.append([_p(_who(n, n.id), CELL), _t(NODE_LABELS[n.type], CELL), str(n.hop),
                     _p(f"<font color='{RISK_COLORS[n.risk]}'><b>{n.risk}</b></font>", CELL),
                     f"{n.risk_score:.2f}" if n.risk_score is not None else "-", _t(_humanize(n.typology), CELL),
                     _p("<br/>".join(escape(r) for r in n.reasons) or "-", CELL)])
    return out + [_t("The reported wallet is not scored: it is the subject of the complaint. Scores are for "
                     "downstream wallets.", MUTED_P), Spacer(1, 3),
                  _table(rows, [38 * mm, 20 * mm, 9 * mm, 15 * mm, 11 * mm, 22 * mm, 65 * mm])]


def _recommendations(trace: TraceResponse) -> list:
    out = [_t("6. Recommended actions", H2)]
    if not trace.recommendations:
        return out + [_t("None.", MUTED_P)]
    tone = {"urgent": "#dc2626", "high": "#ea580c", "normal": "#6b7280"}
    rows = [["Priority", "Action", "Detail"]] + [
        [_p(f"<font color='{tone[r.priority]}'><b>{r.priority.upper()}</b></font>", CELL), _p(f"<b>{escape(r.action)}"
                                                                                             f"</b>", CELL),
         _t(r.detail, CELL)] for r in trace.recommendations]
    return out + [_table(rows, [18 * mm, 55 * mm, 107 * mm])]


def _methodology(trace: TraceResponse, digest: str) -> list:
    points = [
        "Forward trace: starting at the reported wallet, USDT transfers are followed hop by hop. Victim payments "
        "into the reported wallet are shown for context.",
        "Attribution: a wallet is attributed to an exchange either by matching a labeled exchange address "
        "(deterministic) or by the deposit-address pattern of many senders swept to a labeled hot wallet "
        "(heuristic, confidence below 90%).",
        "The label database is small. An unlabeled wallet is not proof that no exchange was involved.",
        "Risk scores come from a model trained on synthetic and seed data plus rule checks. They help prioritise; "
        "they are not evidence on their own. The reasons listed are the factors behind each score.",
        "The tool identifies the exchange account that received the funds. Linking that account to a person "
        "needs the exchange's KYC records, obtained through legal process.",
        "Mixers are flagged, not de-anonymised: funds leaving a mixer cannot be followed reliably.",
        "Bridges move funds to another chain. The trace continues only where the destination is known.",
        "NCRP and SAHYOG integrations in this build are simulated.",
    ]
    if trace.source == "simulated":
        points.insert(0, "This report was built from SIMULATED demo data. All names, addresses and transfers are "
                         "fictional.")
    items = ListFlowable([ListItem(_t(x, SMALL), leftIndent=10) for x in points], bulletType="bullet",
                         start="-", leftIndent=10, bulletFontSize=7)
    return [_t("7. Methodology and limitations", H2), items, Spacer(1, 6),
            _p("<b>Integrity.</b> The SHA-256 below is computed over the case data this report was built from "
               "(the stored trace as JSON with sorted keys and no whitespace). Recomputing it from the case "
               "record shows whether the report matches the data.", SMALL),
            _p(f"<font name='Courier'>{digest}</font>", MONO)]


# ---------- document ----------
def build_report(trace: TraceResponse, case: Optional[CaseSummary] = None, generated_at: Optional[int] = None) -> bytes:
    generated = generated_at or int(time.time())
    digest = evidence_hash(trace)
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=16 * mm,
                            bottomMargin=20 * mm, title=f"ChainTrace evidence report {trace.case_id}",
                            author="ChainTrace", subject=f"Complaint {trace.complaint_id}",
                            keywords=f"sha256:{digest}")

    def chrome(canvas, d):
        canvas.saveState()
        w, _ = A4
        canvas.setStrokeColor(LINE)
        canvas.line(15 * mm, 14 * mm, w - 15 * mm, 14 * mm)
        canvas.setFont("Helvetica", 6.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(15 * mm, 10 * mm, f"ChainTrace evidence report | Case {trace.case_id} | "
                                            f"Complaint {trace.complaint_id} | {trace.source.upper()} data")
        canvas.drawRightString(w - 15 * mm, 10 * mm, f"Page {d.page}")
        canvas.setFont("Courier", 6)
        canvas.drawString(15 * mm, 6.5 * mm, f"SHA-256 (case data): {digest}")
        canvas.restoreState()

    story = (_header(trace, case, generated) + _summary(trace, case) + _graph(trace, doc.width)
             + _transactions(trace) + _attribution(trace) + _risk(trace) + _recommendations(trace)
             + _methodology(trace, digest))
    doc.build(story, onFirstPage=chrome, onLaterPages=chrome)
    return buf.getvalue()
