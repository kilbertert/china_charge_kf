"""Extract images from the docx with surrounding context for the LLM KB.

Walks paragraphs and tables in document order. For each image:
  - Captures the nearest preceding heading (1-3 levels)
  - Captures the nearest preceding paragraph (the step description)
  - Captures the immediately following paragraph (if any)
  - Computes SHA256 for dedup
  - Saves to kb-assets/images/ with a placeholder name first; final
    naming happens in a separate pass once we know the chapter map.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn

DOCX_PATH = Path(r"d:/AI/company-projects/ai-customer/china_charge_kf/《标准版充电桩操作手册》--英语版本.docx")
OUT_DIR = Path(r"d:/AI/company-projects/ai-customer/china_charge_kf/kb-assets/images")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# --- helpers -----------------------------------------------------------------

HEADING_STYLE = re.compile(r"^Heading\s*(\d+)$", re.IGNORECASE)


def iter_block_items(parent):
    """Yield paragraphs and tables in document order."""
    from docx.document import Document as _Doc
    from docx.oxml.table import CT_Tbl
    from docx.oxml.text.paragraph import CT_P
    from docx.table import Table, _Cell
    from docx.text.paragraph import Paragraph

    if isinstance(parent, _Doc):
        parent_elm = parent.element.body
    elif isinstance(parent, _Cell):
        parent_elm = parent._tc
    else:
        parent_elm = parent

    for child in parent_elm.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, parent)
        elif isinstance(child, CT_Tbl):
            yield Table(child, parent)


def heading_level(style_name):
    if not style_name:
        return None
    m = HEADING_STYLE.match(style_name)
    return int(m.group(1)) if m else None


def get_para_text(p):
    return p.text.strip()


def images_in_paragraph(p):
    blips = p._element.findall(".//" + qn("a:blip"))
    out = []
    for blip in blips:
        rid = blip.get(qn("r:embed"))
        if not rid:
            continue
        out.append(rid)
    return out


def main():
    if not DOCX_PATH.exists():
        print(f"ERROR: docx not found: {DOCX_PATH}", file=sys.stderr)
        return 2

    doc = Document(str(DOCX_PATH))
    part = doc.part

    headings: list = []
    last_para: str = ""

    image_records: list = []
    seen_hashes: dict = {}

    counter = 0
    for block in iter_block_items(doc):
        if hasattr(block, "rows"):
            for row in block.rows:
                for cell in row.cells:
                    for p in cell.paragraphs:
                        rids = images_in_paragraph(p)
                        for rid in rids:
                            counter += 1
                            rel = part.rels[rid]
                            blob = rel.target_part.blob
                            sha = hashlib.sha256(blob).hexdigest()
                            ext = (rel.target_part.partname.split(".")[-1] or "png").lower()
                            if ext not in {"png", "jpg", "jpeg", "gif", "bmp", "webp"}:
                                ext = "png"
                            dup_of = seen_hashes.get(sha)
                            if not dup_of:
                                fname = f"img-{counter:03d}.{ext}"
                                target = OUT_DIR / fname
                                target.write_bytes(blob)
                                seen_hashes[sha] = fname
                            else:
                                fname = dup_of
                            image_records.append({
                                "order": counter,
                                "rid": rid,
                                "filename": fname,
                                "sha256": sha[:12],
                                "duplicate_of": dup_of,
                                "context_heading": " > ".join(h for _, h in headings) or "(no heading yet)",
                                "prev_paragraph": last_para[:500],
                                "this_paragraph": get_para_text(p)[:500],
                                "next_paragraph": "",
                                "location": "table cell",
                            })
                        if p.text.strip():
                            last_para = p.text.strip()
        else:
            text = get_para_text(block)
            lvl = heading_level(block.style.name if block.style else None)
            if lvl is not None and text:
                while headings and headings[-1][0] >= lvl:
                    headings.pop()
                headings.append((lvl, text))
            rids = images_in_paragraph(block)
            if rids:
                for rid in rids:
                    counter += 1
                    rel = part.rels[rid]
                    blob = rel.target_part.blob
                    sha = hashlib.sha256(blob).hexdigest()
                    ext = (rel.target_part.partname.split(".")[-1] or "png").lower()
                    if ext not in {"png", "jpg", "jpeg", "gif", "bmp", "webp"}:
                        ext = "png"
                    dup_of = seen_hashes.get(sha)
                    if not dup_of:
                        fname = f"img-{counter:03d}.{ext}"
                        target = OUT_DIR / fname
                        target.write_bytes(blob)
                        seen_hashes[sha] = fname
                    else:
                        fname = dup_of
                    image_records.append({
                        "order": counter,
                        "rid": rid,
                        "filename": fname,
                        "sha256": sha[:12],
                        "duplicate_of": dup_of,
                        "context_heading": " > ".join(h for _, h in headings) or "(no heading yet)",
                        "prev_paragraph": last_para[:500],
                        "this_paragraph": text[:500],
                        "next_paragraph": "",
                        "location": "paragraph",
                    })
                if text:
                    last_para = text
            else:
                if text:
                    last_para = text

    for i, rec in enumerate(image_records):
        if i + 1 < len(image_records):
            nxt = image_records[i + 1]
            rec["next_paragraph"] = nxt.get("prev_paragraph", "")[:500]

    raw_path = OUT_DIR.parent / "_raw_extraction.json"
    raw_path.write_text(json.dumps(image_records, ensure_ascii=False, indent=2))

    outline = []
    headings = []
    for block in iter_block_items(doc):
        if hasattr(block, "rows"):
            continue
        text = get_para_text(block)
        lvl = heading_level(block.style.name if block.style else None)
        if lvl is not None and text:
            while headings and headings[-1][0] >= lvl:
                headings.pop()
            headings.append((lvl, text))
            outline.append({
                "level": lvl,
                "title": text,
                "path": " > ".join(h for _, h in headings),
            })
    (OUT_DIR.parent / "_heading_outline.json").write_text(
        json.dumps(outline, ensure_ascii=False, indent=2)
    )

    print(f"Total image references found: {counter}")
    print(f"Unique images (deduped):    {len(seen_hashes)}")
    print(f"Raw manifest:                {raw_path}")
    print(f"Heading outline:             {OUT_DIR.parent / '_heading_outline.json'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
