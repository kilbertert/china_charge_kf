#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修复 6250b-judge 的 FALLBACK 误触发(用户真实测试三轮第3轮崩)。

根因: 6250b-judge 有 `if (not is_suf) and count >= 2: return FALLBACK`。
      第3轮 count=2, 6250b LLM 输出 INSUFFICIENT(有好的引导话术), 但 judge 升级为
      FALLBACK -> 走 6250b-parse(FALLBACK 分支返回"待人工核实"垃圾)-> 6243b 写表+汇报,
      丢弃了 6250b LLM 的引导话术。

业务: 6250b 路径=用户补充信息, LLM 整合+判充足度+生成针对性引导话术。INSUFFICIENT 应
      走 6250b-insuf-out 直出 LLM 引导话术(继续引导), 直到 SUFFICIENT 或用户 ABANDON
      (6170b 上游检测)。FALLBACK 在固定2轮放弃+丢弃话术+写低质量记录, 与业务相悖, 且与
      首轮 6250-judge(无 FALLBACK)不一致。

修复: 移除 6250b-judge 的 FALLBACK 分支。INSUFFICIENT 永远返回 INSUFFICIENT。
      (FALLBACK label 不再产生; 6250b-if 的 fallback/default case 与 6250b-parse 的
      FALLBACK 分支成为死代码, 不影响功能, 保持聚焦不动。)

运行:
  ssh 124 'docker exec -i docker-api-1 python3 -'          < patch_fix_6250b_fallback.py        # dry-run
  ssh 124 'docker exec -i docker-api-1 python3 - --apply'  < patch_fix_6250b_fallback.py        # 部署
"""
import os, json, sys
import psycopg2, psycopg2.extras

BID = "707dd6d2-059f-47c9-aaac-4638e74969c6"
APPLY = (len(sys.argv) > 1 and sys.argv[1] == "--apply")

# 移除 FALLBACK 逻辑: INSUFFICIENT 永远返回 INSUFFICIENT (与首轮 6250-judge 对齐)
NEW_6250B_JUDGE_CODE = r'''def main(llm_text: str, clarify_count) -> dict:
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
    if is_suf:
        return {"label": "SUFFICIENT", "next_count": count}
    return {"label": "INSUFFICIENT", "next_count": count + 1}'''


def patch_graph(g):
    touched = []
    for n in g.get("nodes", []):
        if n.get("id") == "6250b-judge":
            d = n.get("data", {})
            old = d.get("code", "")
            if "FALLBACK" in old and "count >= 2" in old:
                d["code"] = NEW_6250B_JUDGE_CODE
                touched.append("6250b-judge:remove FALLBACK (INSUFFICIENT always guides)")
            elif "FALLBACK" not in old:
                touched.append("6250b-judge:already no FALLBACK")
            else:
                touched.append("6250b-judge:pattern NOT FOUND (skip)")
    return touched


def main():
    conn = psycopg2.connect(
        host=os.environ.get("DB_HOST", "db"),
        port=int(os.environ.get("DB_PORT", "5432")),
        user=os.environ.get("DB_USERNAME", "postgres"),
        password=os.environ.get("DB_PASSWORD", ""),
        dbname=os.environ.get("DB_DATABASE", "dify"),
    )
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id, version, graph FROM workflows WHERE app_id=%s AND version!='draft' ORDER BY updated_at DESC", (BID,))
    rows = cur.fetchall()
    print("BID=%s  published_rows=%d  APPLY=%s" % (BID, len(rows), APPLY))
    changed = 0
    for r in rows:
        g = r["graph"]
        if isinstance(g, str):
            g = json.loads(g)
        touched = patch_graph(g)
        if not touched:
            continue
        if APPLY:
            cur.execute("UPDATE workflows SET graph=%s WHERE id=%s", (json.dumps(g, ensure_ascii=False), r["id"]))
            changed += cur.rowcount
        print("  %s version=%s -> %s" % ("patched" if APPLY else "would-patch", r["version"], touched))
    if APPLY:
        conn.commit()
        print("\n[APPLIED] updated %d rows" % changed)
        cur.execute("SELECT graph FROM workflows WHERE app_id=%s AND version!='draft' ORDER BY updated_at DESC LIMIT 1", (BID,))
        g = cur.fetchone()["graph"]
        if isinstance(g, str):
            g = json.loads(g)
        for n in g.get("nodes", []):
            if n.get("id") == "6250b-judge":
                c = n.get("data", {}).get("code", "")
                print("  verify 6250b-judge: has FALLBACK=%s | has count>=2=%s | returns INSUFFICIENT=%s" % (
                    "FALLBACK" in c, "count >= 2" in c or "count>=2" in c, "INSUFFICIENT" in c))
    else:
        print("\n[DRY-RUN] no writes. Re-run with --apply to deploy.")
    cur.close()
    conn.close()


main()
