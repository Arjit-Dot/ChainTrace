"""Where everything lives. Import paths from here instead of building them from __file__ in each module."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
DATA = ROOT / "data"

REFERENCE = DATA / "reference"            # lookup tables: labels.csv, vasp_contacts.csv
LABELS_CSV = REFERENCE / "labels.csv"
CONTACTS_CSV = REFERENCE / "vasp_contacts.csv"

SEED = DATA / "seed"                      # the 8 seeded demo cases (B)
SEED_CASES = SEED / "seed_cases.json"
SEED_TRACES = SEED / "seed_traces.json"

FIXTURES = DATA / "fixtures"              # one example response per endpoint
SCENARIOS = DATA / "scenarios"            # attribution test scenarios + the live-monitoring replay
SCENARIOS_JSON = SCENARIOS / "scenarios.json"
REPLAY_JSON = SCENARIOS / "replay_movements.json"

CACHE = DATA / "cache"                    # raw TronGrid responses
TRON_CACHE = CACHE / "tron"
SCRIPTS = DATA / "scripts"
MODELS = DATA / "models"                  # trained risk model
MODEL_PKL = MODELS / "risk_model.pkl"
TEMPLATES = BACKEND / "product" / "templates"
