"""
ChainTrace API contract (single source of truth).

Person A (engine) returns these models. Person B (product) consumes them.
Do not change a field without telling the other person and bumping CONTRACT_VERSION.
Conventions: timestamps = Unix epoch SECONDS (UTC); amounts = token units (e.g. 7850.0 USDT).
"""
from typing import List, Literal, Optional
from pydantic import BaseModel, Field

CONTRACT_VERSION = "1.0.0"

NodeType = Literal["victim", "scam_wallet", "intermediary", "bridge", "mixer", "exchange", "unknown"]
RiskLevel = Literal["Low", "Medium", "High", "Critical"]
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
    risk: RiskLevel = "Low"
    risk_score: float = Field(0.0, ge=0, le=1)
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


class TraceResponse(BaseModel):
    contract_version: str = CONTRACT_VERSION
    case_id: str
    complaint_id: str
    wallet: str
    chain: Chain = "tron"
    fraud_type: Optional[str] = None
    amount_lost: Optional[float] = None
    risk: RiskLevel
    risk_score: float
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
    risk: RiskLevel
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
    type: Literal["FUNDS_MOVED", "REACHED_VASP", "ENTERED_MIXER", "NEW_COMPLAINT_LINKED", "HIGH_RISK_WALLET"]
    severity: Literal["info", "warning", "critical"]
    case_id: str
    message: str
    timestamp: int


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
