"""
ChainTrace API contract (single source of truth).

Person A (engine) returns these models. Person B (product) consumes them.
Do not change a field without telling the other person and bumping CONTRACT_VERSION.
Conventions: timestamps = Unix epoch SECONDS (UTC); amounts = token units (e.g. 7850.0 USDT).
"""
from typing import List, Literal, Optional
from pydantic import BaseModel, Field

CONTRACT_VERSION = "1.2.0"

NodeType = Literal["victim", "scam_wallet", "intermediary", "bridge", "mixer", "exchange", "dex", "bank_account", "unknown"]
RiskLevel = Literal["Low", "Medium", "High", "Critical"]
Urgency = Literal["act_now", "act_soon", "preserve"]   # set by B (recommendations.py); the engine returns None
MonitorStatus = Literal["live", "stale", "off"]   # stale: last check older than ~2x the poll interval
Source = Literal["live", "cached", "simulated"]
Method = Literal["deterministic", "heuristic"]
EdgeType = Literal["transfer", "bridge", "swap", "mixer_in"]
Typology = Literal["investment_scam", "task_scam", "sextortion", "ransomware", "phishing", "darknet", "unknown"]
Chain = Literal["tron", "ethereum", "bsc", "polygon", "bitcoin", "solana"]


# ---------- Requests ----------
class TraceRequest(BaseModel):
    complaint_id: str
    wallet: str
    chain: Optional[Chain] = None            # auto-detected when missing
    amount: Optional[float] = None
    currency: Optional[str] = "USDT"
    tx_hash: Optional[str] = None
    fraud_type: Optional[str] = None
    state: Optional[str] = None
    reported_at: Optional[int] = None


# ---------- Graph ----------
class Node(BaseModel):
    id: str                                   # the wallet address
    chain: Chain = "tron"
    type: NodeType
    label: Optional[str] = None               # e.g. "Example Exchange A (hot wallet)"
    hop: int = 0                              # distance from the reported wallet
    risk: Optional[RiskLevel] = "Low"         # None for the reported wallet (hop 0, labeled "Reported"): risk is for downstream wallets
    risk_score: Optional[float] = Field(0.0, ge=0, le=1)
    reasons: List[str] = []                   # top SHAP / rule reason codes
    typology: Typology = "unknown"
    idle_balance: float = 0.0                 # funds still sitting here (act now if > 0)


class Edge(BaseModel):
    source: str
    target: str
    tx_hash: str
    amount: float
    token: str = "USDT"
    timestamp: int
    edge_type: EdgeType = "transfer"


class Graph(BaseModel):
    nodes: List[Node]
    edges: List[Edge]


# ---------- Findings ----------
class NearestVASP(BaseModel):
    vasp: str
    deposit_address: str
    hops: int
    amount: float
    timestamp: int
    confidence: float = Field(ge=0, le=1)
    method: Method
    evidence: List[str]
    contact: Optional[str] = None


class Recommendation(BaseModel):
    priority: Literal["urgent", "high", "normal"]
    action: str
    detail: str


class TraceSummary(BaseModel):
    hops: int
    nodes: int
    total_traced: float
    idle_funds: float
    time_to_attribution_sec: Optional[float] = None


class Monitoring(BaseModel):
    """Live monitoring of the case's leaf and idle wallets (set by B's watcher; the engine returns None)."""
    status: MonitorStatus
    last_checked_at: Optional[int] = None     # epoch seconds of the last successful chain check
    poll_interval_sec: float = 30


class TraceResponse(BaseModel):
    contract_version: str = CONTRACT_VERSION
    case_id: str
    complaint_id: str
    wallet: str
    chain: Chain = "tron"
    fraud_type: Optional[str] = None
    amount_lost: Optional[float] = None
    risk: Optional[RiskLevel] = None          # mirrors the reported wallet, so None (see Node.risk)
    risk_score: Optional[float] = None
    urgency: Optional[Urgency] = None         # engine returns None; B sets it in recommendations.py
    urgency_reasons: List[str] = []           # the triggers that fired
    urgency_as_of: Optional[int] = None       # time of the last successful chain check, not of the last change
    monitoring: Optional[Monitoring] = None
    typology: Typology = "unknown"
    graph: Graph
    nearest_vasp: Optional[NearestVASP] = None
    summary: TraceSummary
    recommendations: List[Recommendation] = []
    source: Source
    generated_at: int
    notes: Optional[str] = None


class WalletRisk(BaseModel):
    address: str
    risk: RiskLevel
    risk_score: float
    reasons: List[str]
    typology: Typology = "unknown"


# ---------- Cases, dashboard, network ----------
class CaseSummary(BaseModel):
    case_id: str
    complaint_id: str
    wallet: str
    amount_lost: float
    fraud_type: str
    state: str
    risk: Optional[RiskLevel] = None          # None: mirrors the reported wallet
    urgency: Optional[Urgency] = None
    urgency_reasons: List[str] = []
    urgency_as_of: Optional[int] = None
    monitoring: Optional[Monitoring] = None
    status: Literal["tracing", "attributed", "notice_drafted", "notice_sent", "unresolved"]
    vasp: Optional[str] = None
    time_to_attribution_sec: Optional[float] = None
    network_id: Optional[str] = None
    reported_at: int


class CountItem(BaseModel):
    name: str
    count: int
    amount: float = 0.0


class DashboardStats(BaseModel):
    total_cases: int
    total_amount_lost: float
    total_amount_traced: float
    vasp_identified_pct: float
    avg_time_to_attribution_sec: float
    idle_funds_flagged: float
    by_fraud_type: List[CountItem]
    top_vasps: List[CountItem]
    by_state: List[CountItem]


class NetworkNode(BaseModel):
    id: str
    type: Literal["complaint", "wallet", "exchange"]
    label: str


class NetworkEdge(BaseModel):
    source: str
    target: str


class Network(BaseModel):
    network_id: str
    complaint_ids: List[str]
    victim_count: int
    total_amount: float
    states: List[str]
    vasp: Optional[str] = None
    nodes: List[NetworkNode]
    edges: List[NetworkEdge]


# ---------- Alerts ----------
class Alert(BaseModel):
    id: str
    type: Literal["FUNDS_MOVED", "REACHED_VASP", "ENTERED_MIXER", "NEW_COMPLAINT_LINKED", "HIGH_RISK_WALLET", "URGENCY_CHANGED",
                  "COMPLAINT_RECEIVED", "REPLY_RECEIVED"]
    severity: Literal["info", "warning", "critical"]
    case_id: Optional[str] = None             # None for an alert about a complaint that has no case yet
    complaint_id: Optional[str] = None
    message: str
    timestamp: int


# ---------- Complaints (portal intake) ----------
# A citizen files a complaint; an officer reviews it and triggers the trace, which creates the case. The citizen can
# follow only a coarse stage by complaint ID (ComplaintStatusView): never the wallet, the exchange or how it is handled.
ComplaintStage = Literal["received", "under_review", "investigating", "action_initiated", "closed"]


HandlePlatform = Literal["telegram", "whatsapp", "instagram", "facebook", "x", "other"]


class LureChannels(BaseModel):
    """Optional details a victim can give about HOW the scammer reached them and WHERE they paid. Each one is an
    identifier an officer can follow to the institution that holds the person behind it."""
    scammer_phone: Optional[str] = Field(default=None, pattern=r"^[+0-9 ()-]{6,20}$")
    scammer_handle: Optional[str] = Field(default=None, max_length=80)
    scammer_handle_platform: Optional[HandlePlatform] = None
    scam_website: Optional[str] = Field(default=None, max_length=300)
    scam_app: Optional[str] = Field(default=None, max_length=120)
    paid_to_upi: Optional[str] = Field(default=None, pattern=r"^[\w.\-]{2,64}@[\w.\-]{2,64}$")
    paid_to_bank_account: Optional[str] = Field(default=None, pattern=r"^\d{6,20}$")
    paid_to_ifsc: Optional[str] = Field(default=None, pattern=r"^[A-Za-z]{4}0[A-Za-z0-9]{6}$")


class ComplaintRequest(LureChannels):
    """What a citizen submits."""
    wallet: str = Field(min_length=1, max_length=120)
    chain: Optional[Chain] = None
    amount: Optional[float] = Field(default=None, ge=0)
    currency: str = "USDT"
    tx_hash: Optional[str] = Field(default=None, max_length=120)
    fraud_type: Optional[str] = Field(default=None, max_length=40)
    state: Optional[str] = Field(default=None, max_length=60)
    description: Optional[str] = Field(default=None, max_length=2000)
    reporter_name: str = Field(min_length=1, max_length=80)
    reporter_mobile: str = Field(pattern=r"^\d{10}$")


class ComplaintEvent(BaseModel):
    at: int
    stage: ComplaintStage
    note: str                                  # the officer's view of what happened


class Complaint(LureChannels):
    """The stored complaint (officer view only)."""
    complaint_id: str
    wallet: str
    chain: Optional[Chain] = None
    amount: Optional[float] = None
    currency: str = "USDT"
    tx_hash: Optional[str] = None
    fraud_type: Optional[str] = None
    state: Optional[str] = None
    description: Optional[str] = None
    reporter_name: str
    reporter_mobile: str
    stage: ComplaintStage = "received"
    case_id: Optional[str] = None              # set once an officer has triggered the trace
    created_at: int
    updated_at: int
    history: List[ComplaintEvent] = []


class ComplaintReceipt(BaseModel):
    """What the citizen gets back when filing."""
    complaint_id: str
    stage: ComplaintStage
    message: str


class ComplaintTimelineItem(BaseModel):
    stage: ComplaintStage
    label: str
    message: str
    at: int


class ComplaintStatusView(BaseModel):
    """The ONLY thing a citizen can see about a complaint: a coarse stage and generic messages."""
    complaint_id: str
    stage: ComplaintStage
    label: str
    message: str
    updated_at: int
    timeline: List[ComplaintTimelineItem]


# ---------- Notices and integrations ----------
class FreezeNotice(BaseModel):
    case_id: str
    to_vasp: str
    to_email: Optional[str] = None
    subject: str
    body: str
    requested_actions: List[str]
    status: Literal["draft", "approved", "sent"] = "draft"


class SahyogNoticeRequest(BaseModel):
    case_id: str
    to_vasp: str
    subject: str
    body: str


class IntegrationAck(BaseModel):
    ack_id: str
    status: Literal["received", "queued", "acknowledged_by_vasp"]
    received_at: int
    case_id: Optional[str] = None


# ---------- Identifiers and leads (investigation) ----------
# Every case keeps a ledger of identifiers: wallets, bank accounts, UPI IDs, phones, handles, domains, apps. For each one
# the system suggests the institution that holds the identity behind it and the request to send. A reply adds new
# identifiers, which open new leads. Everything is "suspected" until an officer confirms it.
IdentifierKind = Literal["wallet", "bank_account", "upi_id", "phone", "email", "device", "ip_address", "social_handle", "domain", "app"]
IdentifierSource = Literal["complaint", "trace", "reply", "officer"]
IdentifierRole = Literal["reported", "mule_suspect", "vasp_deposit", "lure", "payment", "other"]
ChokePoint = Literal["exchange", "bank", "payment_app", "p2p_desk", "telecom", "messaging_platform", "domain_host", "app_store", "issuer"]
RequestKind = Literal["kyc_request", "account_details_request", "freeze_request", "subscriber_request", "platform_data_request",
                      "registrant_request", "developer_request", "takedown_request", "preservation_notice", "issuer_hold"]


class IdentifierRequest(BaseModel):
    """An officer adds an identifier by hand (for example from a phone call)."""
    kind: IdentifierKind
    value: str = Field(min_length=1, max_length=300)
    label: Optional[str] = Field(default=None, max_length=120)
    role: IdentifierRole = "other"


class Identifier(BaseModel):
    identifier_id: str
    case_id: str
    kind: IdentifierKind
    value: str                                 # normalised, so the same phone or domain is never listed twice
    label: Optional[str] = None                # for example the platform of a handle, or the bank of an account
    role: IdentifierRole = "other"
    source: IdentifierSource
    source_ref: Optional[str] = None           # for example the complaint ID, or the reply it came from
    confidence: float = Field(ge=0, le=1)      # how sure we are that this identifier matters to the case
    added_at: int


class Lead(BaseModel):
    """A suggested next step: ask this institution for the identity behind this identifier."""
    lead_id: str
    case_id: str
    identifier_id: str
    choke_point: ChokePoint
    holder: str                                # who holds the data, in plain words
    what_it_identifies: str
    requests: List[RequestKind]
    priority: Literal["urgent", "high", "normal"]
    rationale: str


# ---------- Where the money went, and the mules on the way (investigation 4.2) ----------
# Each kind of endpoint is handled differently: an exchange can be asked for KYC and told to freeze; a DEX pool has no
# account holder at all; a bank account takes a freeze or lien request; a mixer cannot be followed; a wallet still
# holding funds can be held by the token issuer.
EndpointKind = Literal["vasp", "dex", "bank_account", "mixer", "bridge", "idle_wallet", "dead_end"]


class Outcome(BaseModel):
    outcome_id: str
    case_id: str
    kind: EndpointKind
    title: str
    subject: str                               # the address or account this is about
    subject_label: Optional[str] = None
    amount: Optional[float] = None
    status: Literal["action_needed", "in_progress", "info"]
    handling: List[str]                        # what an officer does about this kind of endpoint, in order
    lead_ids: List[str] = []                   # the leads that carry out those steps


class Mule(BaseModel):
    """A suspected mule: a wallet that passed the money on, or a bank account the victim paid. Always 'suspected'."""
    case_id: str
    kind: Literal["wallet", "bank_account"]
    value: str
    label: Optional[str] = None
    hop: Optional[int] = None
    risk: Optional[RiskLevel] = None
    risk_score: Optional[float] = None
    reasons: List[str]
    received: float = 0.0
    forwarded: float = 0.0
    onward: List[str] = []                     # where it sent the money: vasp, dex, mixer, bridge, wallet
    identifier_id: Optional[str] = None


# ---------- Requests to institutions, and their replies (investigation 4.3) ----------
# An officer turns a lead into a request: a draft letter, approved by an officer, then sent. A reply brings facts and NEW
# identifiers, which open new leads. In this demo nothing is sent anywhere and every reply is FICTIONAL.
RequestStatus = Literal["draft", "approved", "sent", "acknowledged", "replied", "closed"]


class RequestCreate(BaseModel):
    lead_id: str
    kind: RequestKind


class RequestEvent(BaseModel):
    at: int
    status: RequestStatus
    note: str


class InstitutionRequest(BaseModel):
    request_id: str
    case_id: str
    lead_id: str
    identifier_id: str
    choke_point: ChokePoint
    holder: str
    kind: RequestKind
    subject: str                               # the identifier the request is about
    status: RequestStatus = "draft"
    letter_subject: str
    letter_body: str                           # a DRAFT: legal references are placeholders for the officer
    created_at: int
    updated_at: int
    reference: Optional[str] = None            # the acknowledgement reference once sent (simulated)
    history: List[RequestEvent] = []


class ReplyField(BaseModel):
    label: str
    value: str


class Reply(BaseModel):
    reply_id: str
    request_id: str
    case_id: str
    received_at: int
    summary: str
    fields: List[ReplyField]
    new_identifier_ids: List[str] = []         # what this reply added to the case's ledger
    fictional: bool = True                     # always true in this demo
