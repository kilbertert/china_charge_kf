"""Rename images to chapter-based kebab-case filenames and emit a CSV stub.

Reads kb-assets/_raw_extraction.json and renames img-NNN.png to
<section>-<chapter>-<sub>.png based on the chapter heading.
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

IMG_DIR = Path(r"d:/AI/company-projects/ai-customer/china_charge_kf/kb-assets/images")
RAW = Path(r"d:/AI/company-projects/ai-customer/china_charge_kf/kb-assets/_raw_extraction.json")
OUT_CSV = Path(r"d:/AI/company-projects/ai-customer/china_charge_kf/kb-assets/_manifest_stub.csv")

SECTION_MAP = {
    "The operation of the PC management backend is as follows:": "pc-backend",
    "The user side operation is as follows:": "user-side",
    "The operation of the butler end is as follows:": "butler-end",
}

CHAPTER_SLUG = {
    "Role Management": "role-management",
    "Shop Level": "shop-level",
    "Individual operator": "individual-operator",
    "Operator review for entry": "operator-review",
    "Add sites under the operator": "add-sites",
    "Site audit": "site-audit",
    "Billing Template (Charging Station)": "billing-template",
    "Add product model": "add-product-model",
    "equipment": "equipment",
    "Placement equipment": "placement-equipment",
    "Charging coupons": "charging-coupons",
    "Equipment Failure List": "equipment-failure-list",
    "User Management": "user-management",
    "Financial Management": "financial-management",
    "Order Management": "order-management",
    "Operations Management": "operations-management",
    "Data View": "data-view",
    "Sign up": "sign-up",
    "top-up": "top-up",
    "place an order": "place-order",
    "Four wheel charging order": "four-wheel-charging-order",
    "Placeholder fee order": "placeholder-fee-order",
    "venue": "venue",
    "license plate": "license-plate",
    "Change password": "change-password",
    "Fault Repair": "fault-repair",
    "Real name authentication (incoming)": "real-name-authentication",
    "Create venue": "create-venue",
    "my venue": "my-venue",
    "Create template": "create-template",
    "Venue association template": "venue-association-template",
    "data sector": "data-sector",
    "order": "order",
    "Venue details": "venue-details",
    "Profit withdrawal": "profit-withdrawal",
}

SUB_SLUG_OVERRIDES = {
    "Example - By Transaction Amount": "by-transaction-amount",
    "Example - By charging degree": "by-charging-degree",
    "Example - Seat occupancy fee billing template": "seat-occupancy-fee",
    "Example - Point Award Template": "point-award",
    "Example - Venue Configuration Template": "venue-configuration",
    "Example - Cloud Fast Charging Protocol Device": "cloud-fast-charging",
    "Example - Add Device": "add-device",
    "Example - Remote device startup in the background": "remote-device-startup",
    "Example - Placement Equipment": "placement",
    "Example - Platform Charging Coupon": "platform-coupon",
    "Example - Venue Charging Coupon": "venue-coupon",
    "Example - Backend distribution of coupons to users": "distribute-coupons",
    "Example - Backend verification of user recharge": "verify-recharge",
    "Example - User Withdrawal Review": "withdrawal-review",
    "Example - View Balance Details": "balance-details",
    "Example - Settlement Statement+Statement": "settlement-statement",
    "Example - Charging Order": "charging-order",
    "Example - Occupancy fee order": "occupancy-fee-order",
    "Example - Abnormal Charging Monitoring": "abnormal-charging-monitoring",
    "Example - Order Evaluation": "order-evaluation",
    "Example - Article (such as operation guide)": "article-guide",
    "Example - Protocol (such as User Privacy Agreement, Privacy Policy)": "protocol-privacy",
    "Example - Login and Registration": "login-and-registration",
    "Example - Recharge": "recharge",
    "Example - Scan code to place an order": "scan-to-order",
    "Example - License Plate": "license-plate",
    "Example - Login to Operator Account": "login-operator",
    "Example - Registering an Operator Account": "register-operator",
    "Example - Creating a billing template": "creating-billing-template",
    "Example - Associated billing template": "associated-billing",
    "Example - Associated Occupancy Fee Template": "associated-occupancy",
    "Example - Associate default point award template": "associate-point-award",
    "Example - Four rounds of related data": "four-wheel-data",
    "Example - Four Round Order": "four-round-order",
    "Example - Four Wheel Field": "four-wheel-venue",
    "Example - Adding an individual operator to the backend": "add-individual-operator",
    "Example - Editing and Modifying Personal Information of Operators in the Backend": "edit-operator-info",
    "Example - Operator": "operator",
    "Example - Permissions": "permissions",
    "Example - Audit": "audit",
    "Example - Adding a Venue (New Energy Four Wheel Venue)": "add-venue",
    "Example - Domestic Four Wheel Billing Template": "domestic-four-wheel",
}


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def parse_heading(path: str):
    parts = [p.strip() for p in path.split(">")]
    if parts and parts[0].endswith(":"):
        section_title = parts[0]
        parts = parts[1:]
    else:
        section_title = ""
    return section_title, parts


# Image-content overrides: keyed on the OLD placeholder filename (img-NNN.png).
# Use when an image is extracted under one chapter but its visual content
# actually belongs to a different concept (e.g. img-070 is the "My vehicle"
# car-list page, not a venue map). Keeps the row order stable while fixing
# the filename so it's discoverable in OSS listings.
FILENAME_OVERRIDES: dict[str, str] = {
    "img-070.png": "user-side-my-vehicle-1.png",
}


def build_filename(section: str, chapter: str, sub: str, idx_in_chapter: int) -> str:
    sec_slug = SECTION_MAP.get(section, slugify(section) or "misc")
    chap_slug = CHAPTER_SLUG.get(chapter) or slugify(chapter)
    if sub:
        sub_slug = SUB_SLUG_OVERRIDES.get(sub) or slugify(sub.removeprefix("Example - "))
        return f"{sec_slug}-{chap_slug}-{sub_slug}-{idx_in_chapter}.png"
    return f"{sec_slug}-{chap_slug}-{idx_in_chapter}.png"


def main():
    data = json.loads(RAW.read_text(encoding="utf-8"))
    groups: dict = {}
    rows: list = []
    for r in data:
        section, parts = parse_heading(r["context_heading"])
        chapter = parts[0] if len(parts) >= 1 else ""
        sub = parts[1] if len(parts) >= 2 else ""
        key = (section, chapter, sub)
        groups[key] = groups.get(key, 0) + 1
        idx = groups[key]
        old_filename = r["filename"]
        new_name = FILENAME_OVERRIDES.get(old_filename) or build_filename(section, chapter, sub, idx)
        old_path = IMG_DIR / old_filename
        new_path = IMG_DIR / new_name
        if old_path.exists() and old_path != new_path:
            if not new_path.exists():
                old_path.rename(new_path)
        rows.append({
            "order": r["order"],
            "old_filename": r["filename"],
            "new_filename": new_name,
            "section": section,
            "chapter": chapter,
            "sub": sub,
            "context_heading": r["context_heading"],
            "prev_paragraph": r["prev_paragraph"],
            "this_paragraph": r["this_paragraph"],
            "next_paragraph": r["next_paragraph"],
            "description": "",
            "oss_key": f"kb/charge-pile/{new_name}",
        })

    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    (OUT_CSV.parent / "_manifest_stub.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    by_section: dict = {}
    for r in rows:
        by_section[r["section"]] = by_section.get(r["section"], 0) + 1
    print("Renamed and grouped by section:")
    for s, c in by_section.items():
        print(f"  {s or '(none)'}: {c}")
    print(f"\nCSV stub: {OUT_CSV}")
    print(f"JSON stub: {OUT_CSV.parent / '_manifest_stub.json'}")


if __name__ == "__main__":
    main()
