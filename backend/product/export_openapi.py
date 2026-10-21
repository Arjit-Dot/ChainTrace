"""
Write the API's OpenAPI spec to docs/openapi.json: the integration contract handed to NCRP / SAHYOG-style systems.

Run from backend/:  python -m product.export_openapi
"""
import json

from paths import ROOT


def main() -> None:
    from main import app
    out = ROOT / "docs" / "openapi.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(app.openapi(), indent=2) + "\n")
    print(f"wrote {out.relative_to(ROOT)} ({len(app.openapi()['paths'])} paths)")


if __name__ == "__main__":
    main()
