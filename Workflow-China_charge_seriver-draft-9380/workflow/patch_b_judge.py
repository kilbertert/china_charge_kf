#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修复 charge B(bugtrack) 的充足度子串匹配 bug。

问题: 6250-judge / 6250b-judge 用 `if "INSUFFICIENT" in t elif "SUFFICIENT" in t`,
      导致 LLM 输出 "NOT SUFFICIENT" 时被 "SUFFICIENT" 子串误判为充足;
      以及漏标签+有JSON时 else 默认 SUFFICIENT,把不足反馈当充足写表。

修复: 不足判定加 "NOT SUFFICIENT" 分支; else 默认 INSUFFICIENT(宁可再问也不写半截)。
      JSON 提取部分(mokuai 等)不变。

运行(在 docker-api-1 容器内, 通过 stdin 管道):
  ssh 124 'docker exec -i docker-api-1 python3 -'          < patch_b_judge.py   # dry-run
  ssh 124 'docker exec -i docker-api-1 python3 - --apply'  < patch_b_judge.py   # 部署
"""
import os, json, sys
import psycopg2, psycopg2.extras

BID = "707dd6d2-059f-47c9-aaac-4638e74969c6"  # charge_charging_B_bugtrack
APPLY = (len(sys.argv) > 1 and sys.argv[1] == "--apply")

NEW_6250 = r'''def main(llm_text: str) -> dict:
    import json, re
    text = llm_text or ""
    t = text.upper()
    if "INSUFFICIENT" in t or "NOT SUFFICIENT" in t:
        label = "INSUFFICIENT"
    elif "SUFFICIENT" in t:
        label = "SUFFICIENT"
    else:
        label = "INSUFFICIENT"
    mokuai=caozuomiaoshu=huanjing=leixing=""
    m = re.search(r"\{[^{}]*\}", text)
    if m:
        try:
            obj = json.loads(m.group(0))
            mokuai=str(obj.get("mokuai","")).strip()[:50]
            caozuomiaoshu=str(obj.get("caozuomiaoshu","")).strip()[:500]
            huanjing=str(obj.get("huanjing","")).strip()[:20]
            leixing=str(obj.get("leixing","")).strip()[:20]
        except Exception:
            pass
    return {"label": label, "mokuai": mokuai, "caozuomiaoshu": caozuomiaoshu, "huanjing": huanjing, "leixing": leixing}'''

NEW_6250b = r'''def main(llm_text: str, clarify_count) -> dict:
    import re
    text = llm_text or ""
    t = text.upper()
    if "INSUFFICIENT" in t or "NOT SUFFICIENT" in t:
        is_suf = False
    elif "SUFFICIENT" in t:
        is_suf = True
    else:
        is_suf = False
    try:
        count = int(clarify_count or 0)
    except Exception:
        count = 0
    if (not is_suf) and count >= 2:
        return {"label": "FALLBACK", "next_count": count}
    if is_suf:
        return {"label": "SUFFICIENT", "next_count": count}
    return {"label": "INSUFFICIENT", "next_count": count + 1}'''


def main():
    conn = psycopg2.connect(
        host=os.environ.get("DB_HOST", "db"),
        port=int(os.environ.get("DB_PORT", "5432")),
        user=os.environ.get("DB_USERNAME", "postgres"),
        password=os.environ.get("DB_PASSWORD", ""),
        dbname=os.environ.get("DB_DATABASE", "dify"),
    )
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "SELECT id, version, graph FROM workflows WHERE app_id=%s AND version!='draft' ORDER BY updated_at DESC",
        (BID,),
    )
    rows = cur.fetchall()
    print("BID=%s  published_rows=%d  APPLY=%s" % (BID, len(rows), APPLY))
    changed = 0
    for r in rows:
        g = r["graph"]
        if isinstance(g, str):
            g = json.loads(g)
        nodes = g.get("nodes", [])
        touched = False
        for n in nodes:
            nid = n.get("id")
            if nid == "6250-judge":
                n["data"]["code"] = NEW_6250
                touched = True
            elif nid == "6250b-judge":
                n["data"]["code"] = NEW_6250b
                touched = True
        if not touched:
            continue
        if APPLY:
            cur.execute(
                "UPDATE workflows SET graph=%s WHERE id=%s",
                (json.dumps(g, ensure_ascii=False), r["id"]),
            )
            changed += cur.rowcount
        print("  %s row version=%s %s" % ("patched" if APPLY else "would-patch", r["version"], "(written)" if APPLY else ""))
    if APPLY:
        conn.commit()
        print("\n[APPLIED] updated %d rows" % changed)
        # verify: re-read latest published judge code
        cur.execute(
            "SELECT graph FROM workflows WHERE app_id=%s AND version!='draft' ORDER BY updated_at DESC LIMIT 1",
            (BID,),
        )
        g = cur.fetchone()["graph"]
        if isinstance(g, str):
            g = json.loads(g)
        for n in g.get("nodes", []):
            if n.get("id") in ("6250-judge", "6250b-judge"):
                code = n.get("data", {}).get("code", "")
                ok = ("NOT SUFFICIENT" in code) and ("INSUFFICIENT\" in t or" in code or 'INSUFFICIENT" in t or' in code)
                print("  verify %s: has 'NOT SUFFICIENT' branch = %s" % (n["id"], "NOT SUFFICIENT" in code))
    else:
        print("\n[DRY-RUN] no DB writes. Re-run with --apply to deploy.")
    cur.close()
    conn.close()


main()
