"""Check local documentation links and ownership coverage; no third-party modules."""
import re
from pathlib import Path

root = Path(__file__).resolve().parents[1]
errors = []
for file in root.rglob("*.md"):
    if any(part in {"node_modules", ".venv", ".git"} for part in file.parts):
        continue
    for target in re.findall(r"\]\(([^)]+)\)", file.read_text(encoding="utf-8")):
        if "://" in target or target.startswith("#"):
            continue
        if not (file.parent / target.split("#")[0]).exists():
            errors.append(f"Broken link in {file.relative_to(root)}: {target}")

features = (root / "docs/features.md").read_text(encoding="utf-8")
rows = re.findall(r"^\| (CC-\d{2}) \| (Sandip|Tanjila|Tasin|Saif) \|", features, re.M)
expected = {
    "Sandip": {1, 16, 18, 19, 20}, "Tanjila": {2, 3, 4, 5, 13},
    "Tasin": {6, 7, 8, 11, 17}, "Saif": {9, 10, 12, 14, 15},
}
if len(rows) != 20 or len({feature for feature, _ in rows}) != 20:
    errors.append("Feature list must contain 20 unique rows")
for owner, ids in expected.items():
    actual = {int(feature[3:]) for feature, member in rows if member == owner}
    if actual != ids:
        errors.append(f"Incorrect ownership: {owner}")
if errors:
    raise SystemExit("\n".join(errors))
print("Foundation checks passed: local Markdown links and 20 unique feature assignments.")
