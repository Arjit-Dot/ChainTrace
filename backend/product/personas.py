"""
FICTIONAL people and details for the demo's seeded replies (Person B). Nothing here is real: every name carries "(demo)",
every phone number is in a made-up 90000 00xxx range, every domain ends in .example. A few personas are SHARED between
cases on purpose, so replies for different complaints contain the same phone, email, device or IP: that is what the
linking stage (4.4) uses to show one person behind several cases.
"""
import hashlib
from typing import Dict, List

PERSONAS: List[Dict[str, str]] = [
    {"name": "Anil Varkey (demo)", "phone": "9000000501", "alt_phone": "9000000511", "email": "anil.v.demo@mail.example",
     "device": "IMEI-35000000000501", "ip": "203.0.113.17", "ip2": "203.0.113.18", "city": "Kochi", "doc": "PAN ending 4821"},
    {"name": "Rohan Dsouza (demo)", "phone": "9000000502", "alt_phone": "9000000512", "email": "rohan.d.demo@mail.example",
     "device": "IMEI-35000000000502", "ip": "198.51.100.42", "ip2": "198.51.100.43", "city": "Pune", "doc": "Aadhaar ending 7710"},
    {"name": "Meena Rathore (demo)", "phone": "9000000503", "alt_phone": "9000000513", "email": "meena.r.demo@mail.example",
     "device": "IMEI-35000000000503", "ip": "192.0.2.88", "ip2": "192.0.2.89", "city": "Jaipur", "doc": "Passport ending 3302"},
    {"name": "Sameer Qureshi (demo)", "phone": "9000000504", "alt_phone": "9000000514", "email": "sameer.q.demo@mail.example",
     "device": "IMEI-35000000000504", "ip": "203.0.113.99", "ip2": "203.0.113.100", "city": "Hyderabad", "doc": "Voter ID ending 5566"},
]
# identifiers that mark a scam operation: whoever reported them is dealing with the same persona
OPERATIONS = {
    "hero-invest.example": 0, "hero.invest@okaxis": 0,                  # the hero network (C-001, C-002, C-003)
    "private_pics_demo": 1,                                             # the two sextortion complaints (C-004, C-005)
    "alpha-returns.example": 2, "alpha.returns@ybl": 2,                 # a waiting complaint
    "taskpay_demo": 3, "taskpay earn": 3,                               # another waiting complaint
}


def persona_for(values: List[str], seed: str) -> Dict[str, str]:
    """The persona behind a case: a shared one if the case mentions a known operation, otherwise one chosen from the seed."""
    for v in values:
        if v.lower() in OPERATIONS:
            return PERSONAS[OPERATIONS[v.lower()]]
    return PERSONAS[int(hashlib.sha256(seed.encode()).hexdigest(), 16) % len(PERSONAS)]


def mule_account(seed: str) -> Dict[str, str]:
    """A fictional mule bank account (number and IFSC) derived from the seed."""
    h = hashlib.sha256(("acct" + seed).encode()).hexdigest()
    return {"account": f"0009{int(h[:10], 16) % 10 ** 8:08d}", "ifsc": "SBIN0000002", "bank": "State Bank of India"}


def fake_ref(prefix: str, seed: str) -> str:
    return f"{prefix}-{hashlib.sha256(seed.encode()).hexdigest()[:8].upper()}"
