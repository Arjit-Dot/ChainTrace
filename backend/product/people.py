"""
Linking cases and naming suspected people (Person B, investigation 4.4).

CASES are linked when they share identifiers: one strong shared identifier (a phone, email, device, handle, domain, UPI ID,
bank account, or a wallet that is the reported, mule or exchange-deposit wallet), or two or more weaker ones (an IP address
or an app name on its own proves little: addresses are shared, names are generic).

PEOPLE are named ONLY by institutions' replies (an exchange's account holder, a telecom's subscriber, a domain's
registrant, an app store's developer). Several independent institutions naming the same person, across several cases, raise
the suspicion; one reply in one case stays low. A person who holds a mule BANK account is listed separately, at low
confidence: such account holders are often victims too. Every figure here is an inference for an officer to check.
"""
from collections import defaultdict
from itertools import combinations
from typing import Dict, List, Optional, Set, Tuple

from contract.schemas import (CasePeople, PersonCluster, PersonEvidence, SharedIdentifier, SuspectPerson)
from product import store

STRONG = {"phone", "email", "device", "social_handle", "domain", "upi_id", "bank_account"}
MODERATE = {"ip_address"}
WALLET_ROLES = {"reported", "mule_suspect", "vasp_deposit"}                     # other wallets (for example idle holders) do not link
NAME_FIELDS = {"exchange": "Account holder", "telecom": "Subscriber name", "domain_host": "Registrant", "app_store": "Developer name",
               "bank": "Account holder", "payment_app": "Registered name", "p2p_desk": "Account holder"}
MULE_HOLDER_POINTS = {"bank", "payment_app"}
CAUTION = ("These links and names are inferences from shared identifiers and from institutions' replies. They are for an officer to "
           "check and are not findings. Holders of mule accounts are often victims too.")
MAX_OPERATOR_CONFIDENCE = 0.9
MULE_CONFIDENCE = 0.3


def strength(kind: str) -> str:
    return "strong" if kind in STRONG or kind == "wallet" else "moderate" if kind in MODERATE else "weak"


def _linking_key(i) -> Optional[Tuple[str, str]]:
    if i.kind == "wallet" and i.role not in WALLET_ROLES:
        return None
    return (i.kind, i.value)


def shared_identifiers() -> Dict[Tuple[str, str], Set[str]]:
    """(kind, value) -> the cases that have it, for everything that appears in two or more cases."""
    seen: Dict[Tuple[str, str], Set[str]] = defaultdict(set)
    for c in store.list_cases():
        for i in store.list_identifiers(c.case_id):
            key = _linking_key(i)
            if key:
                seen[key].add(c.case_id)
    return {k: v for k, v in seen.items() if len(v) >= 2}


def _groups(shared: Dict[Tuple[str, str], Set[str]]) -> List[Set[str]]:
    """Connected groups of cases: linked by one strong shared identifier or by two weaker ones."""
    strong_pairs: Set[Tuple[str, str]] = set()
    weak_count: Dict[Tuple[str, str], int] = defaultdict(int)
    for (kind, _), cases in shared.items():
        for a, b in combinations(sorted(cases), 2):
            if strength(kind) == "strong":
                strong_pairs.add((a, b))
            else:
                weak_count[(a, b)] += 1
    links = strong_pairs | {p for p, n in weak_count.items() if n >= 2}
    parent: Dict[str, str] = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in links:
        parent[find(a)] = find(b)
    groups: Dict[str, Set[str]] = defaultdict(set)
    for node in list(parent):
        groups[find(node)].add(node)
    return [g for g in groups.values() if len(g) >= 2]


def people_in(case_ids: List[str]) -> List[SuspectPerson]:
    """Everyone the replies of these cases name, grouped by name and role."""
    found: Dict[Tuple[str, str], List[PersonEvidence]] = defaultdict(list)
    tied: Dict[Tuple[str, str], Set[str]] = defaultdict(set)
    cases_of: Dict[Tuple[str, str], Set[str]] = defaultdict(set)
    institutions: Dict[Tuple[str, str], Set[str]] = defaultdict(set)
    for cid in case_ids:
        values = {i.identifier_id: f"{i.kind}: {i.value}" for i in store.list_identifiers(cid)}
        for req in store.list_requests(cid):
            reply = store.get_reply(req.request_id)
            field = NAME_FIELDS.get(req.choke_point)
            if not reply or not field:
                continue
            name = next((f.value for f in reply.fields if f.label == field), None)
            if not name:
                continue
            role = "mule_holder" if req.choke_point in MULE_HOLDER_POINTS else "operator_suspected"
            key = (name, role)
            found[key].append(PersonEvidence(institution=req.holder, case_id=cid, request_id=req.request_id, field=field, value=name))
            institutions[key].add(req.holder)
            cases_of[key].add(cid)
            tied[key].update(values[i] for i in reply.new_identifier_ids if i in values and not values[i].startswith(("bank_account", "wallet")))
    people = []
    for (name, role), evidence in found.items():
        n_inst, n_cases = len(institutions[(name, role)]), len(cases_of[(name, role)])
        if role == "operator_suspected":
            conf = min(MAX_OPERATOR_CONFIDENCE, 0.35 + 0.15 * (n_inst - 1) + 0.1 * (n_cases - 1))
            basis = f"Named by {n_inst} institution{'s' if n_inst != 1 else ''} in {n_cases} case{'s' if n_cases != 1 else ''}"
        else:
            conf = MULE_CONFIDENCE
            basis = "Holds an account the money passed through: often a victim who was tricked or paid, not the operator"
        people.append(SuspectPerson(name=name, role=role, confidence=round(conf, 2), basis=basis, evidence=evidence,
                                    identifiers=sorted(tied[(name, role)]), case_ids=sorted(cases_of[(name, role)])))
    return sorted(people, key=lambda p: (p.role != "operator_suspected", -p.confidence, p.name))


def clusters() -> List[PersonCluster]:
    shared = shared_identifiers()
    cases = {c.case_id: c for c in store.list_cases()}
    out = []
    for group in _groups(shared):
        ids = sorted(group)
        items = [SharedIdentifier(kind=k, value=v, strength=strength(k), case_ids=sorted(cs & group))
                 for (k, v), cs in sorted(shared.items()) if len(cs & group) >= 2]
        people = people_in(ids)
        operators = [p for p in people if p.role == "operator_suspected"]
        lost = sum(cases[c].amount_lost for c in ids if c in cases)
        states = sorted({cases[c].state for c in ids if c in cases and cases[c].state and cases[c].state != "Unknown"})
        summary = (f"{len(ids)} complaints are linked by {len(items)} shared identifier{'s' if len(items) != 1 else ''}"
                   + (f"; {operators[0].name} appears in the replies of {len(operators[0].case_ids)} of them" if operators else
                      "; no institution has yet named a person: the shared identifiers show which to ask next"))
        out.append(PersonCluster(cluster_id=f"CL-{ids[0]}", case_ids=ids, complaint_ids=[cases[c].complaint_id for c in ids if c in cases],
                                 total_lost=round(lost, 2), states=states, shared=items, people=people, summary=summary, caution=CAUTION))
    return sorted(out, key=lambda c: c.cluster_id)


def cluster_of(case_id: str) -> Optional[PersonCluster]:
    return next((c for c in clusters() if case_id in c.case_ids), None)


def case_people(case_id: str) -> CasePeople:
    return CasePeople(case_id=case_id, cluster=cluster_of(case_id), people=people_in([case_id]))
