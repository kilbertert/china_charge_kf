#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""根因(三轮垮掉): 多轮上下文靠 cv_feedback_zh 文本拼接传递 -> 6172 嵌套拼接崩溃。

根因:
  - cv_feedback_zh 语义混乱(INSUFFICIENT 存原始 query_text / 迭代存 6172.merged 拼接 /
    SUFFICIENT 存结构化 caozuomiaoshu)。
  - 6172 合并 = "已有反馈:{cv_feedback_zh}\n用户补充:{query_text}", 多轮 INSUFFICIENT 后
    嵌套("已有反馈: 已有反馈:...") -> 6250b 转写崩溃 -> 第三轮垮。
  - 6250/6250b/6244/6262 全无 memory, 上下文只靠 cv_feedback_zh(混乱)传递。

修复(基于业务: memory 传递多轮上下文, cv_feedback_zh 只存最新结构化转写, 6172 拼接退役):
  A. 6250/6250b/6244/6262 开 memory(window=10) -- #1 第二批(话术/转写 LLM)
  B. 6250-insuf / 6250b-insuf 删 cv_feedback_zh item -- cv_feedback_zh 只在 SUFFICIENT 路径写
  C. 退役 6172: 6171::modify_new -> 6250b 直连, 6250b 输入从 6172.merged 改 query_text(+memory)
  D. 6250b prompt 重写(基于 cv_ 上一轮字段 + query_text 当前 + memory 历史, 保留判定/输出规则)
  E. 6244 prompt 重写(基于 cv_ 系统整理字段, 去"用户反馈:{query_text}"误导, user 改 cv_feedback_zh)

运行:
  ssh 124 'docker exec -i docker-api-1 python3 -'          < patch_cv_memory.py        # dry-run
  ssh 124 'docker exec -i docker-api-1 python3 - --apply'  < patch_cv_memory.py        # 部署
"""
import os, json, sys
import psycopg2, psycopg2.extras

BID = "707dd6d2-059f-47c9-aaac-4638e74969c6"
APPLY = (len(sys.argv) > 1 and sys.argv[1] == "--apply")
MEMORY = {"window": {"enabled": True, "size": 10}}

P6250B_SYS = """你是 B 端 SaaS 产品客户反馈一体化处理引擎。当前是【迭代场景】:用户在已有反馈基础上补充/修改信息,需结合对话历史与上一轮结构化字段,整合后重新判定。

【上一轮结构化字段】(系统整理,客户未提及的字段保留此原值):
模块: {{#conversation.cv_mokuai#}}
操作描述: {{#conversation.cv_feedback_zh#}}
环境: {{#conversation.cv_huanjing#}}
类型: {{#conversation.cv_leixing#}}

【当前用户补充】: {{#6002.query_text#}}
【对话历史】: 系统自动注入此前各轮用户原话与客服回复(无需手动引用)

【信息充足度判定】满足任意1条即判为"信息不足":
1. 模块/场景完全不明确(无法定位具体功能/页面)
2. 问题现象过于笼统(无操作路径/报错原文/触发条件)
3. 终端环境不明确(无法区分用户端/管家端/后台)
4. 诉求属性不明确(无法区分bug还是优化)
5. 完全无有效业务信息

【迭代修正规则】若用户补充了修改要求,100%按客户要求修正对应字段:
- 模块归属错误->调整mokuai为客户指定名称
- 描述偏差/遗漏->修正caozuomiaoshu对应内容
- 环境/类型错误->同步调整huanjing、leixing
- 客户未提及的字段保留上一轮原值,不变动

【输出规范】必须先输出【充足度】标签:

若信息充足:
【充足度】SUFFICIENT
【内部结构化数据】
{"mokuai":"模块标准名称(15字以内,无法识别填待确认)","caozuomiaoshu":"标准化操作路径与问题现象描述(80字以内,结构:操作终端+操作路径+执行动作+问题现象+业务影响)","huanjing":"后台/管家端/用户端(无法判定填待确认)","leixing":"bug/优化(无法判定填待确认)"}
【客户侧回复话术】
告知已根据补充内容更新记录,同步调整后的内容请客户确认(开篇+4字段通俗描述,bug译为功能故障,优化译为优化建议+确认+补充提示+收尾)

若信息不足:
【充足度】INSUFFICIENT
【客户侧引导话术】
针对仍缺失的信息点精准提问,末尾追加用户ID/订单ID/充电桩编号提示

【全局约束】
- 100%基于输入文本,不脑补不编造
- 枚举字段严格遵守可选值范围
- 客户回复只做信息同步与确认,不做排期/解决方案承诺
- 必须输出【充足度】SUFFICIENT 或【充足度】INSUFFICIENT 标签"""

P6250B_USER = "{{#6002.query_text#}}"

P6244_SYS = """你是充电桩智能客服。系统已将用户反馈整理为下方结构化字段,请基于这些字段生成面向客户的确认话术,让客户核对信息是否准确。

【系统整理的结构化字段】(非用户原话,是系统整合后的结果):
模块: {{#conversation.cv_mokuai#}}
操作描述: {{#conversation.cv_feedback_zh#}}
环境: {{#conversation.cv_huanjing#}}
类型: {{#conversation.cv_leixing#}}

**规则**:
1. 用通俗化语言整合上述字段,生成面向客户的确认话术
2. 结构:开篇问候 + 分点通俗描述(模块/操作/环境/类型) + 主动确认"以上信息是否准确" + 补充提示 + 礼貌收尾
3. 类型为 bug 时译为"功能故障",为优化时译为"优化建议"
4. 严格基于上述字段,不要引入字段之外的信息
5. 简洁,150字以内"""

P6244_USER = "{{#conversation.cv_feedback_zh#}}"

MEM_NODES = ("6250", "6250b", "6244", "6262")


def patch_graph(g):
    nodes = g["nodes"]; edges = g["edges"]
    touched = []

    # A. 开 memory + D/E prompt 重写
    for n in nodes:
        nid = n.get("id"); d = n.get("data", {})
        if nid in MEM_NODES:
            if not d.get("memory"):
                d["memory"] = json.loads(json.dumps(MEMORY))
                touched.append("%s:+memory" % nid)
        if nid == "6250b":
            pts = d.get("prompt_template", [])
            if pts:
                pts[0]["text"] = P6250B_SYS
                if len(pts) > 1:
                    pts[1]["text"] = P6250B_USER
                touched.append("6250b:prompt rewrite(退役6172.merged)")
        if nid == "6244":
            pts = d.get("prompt_template", [])
            if pts:
                pts[0]["text"] = P6244_SYS
                if len(pts) > 1:
                    pts[1]["text"] = P6244_USER
                touched.append("6244:prompt rewrite(去query_text误导)")

    # C. 退役 6172: 取 6250b 入边 targetHandle + 6171->6172 sourceHandle
    th_6250b = "target"; sh_6171 = None
    for e in edges:
        if e.get("source") == "6172" and e.get("target") == "6250b":
            th_6250b = e.get("targetHandle", "target")
        if e.get("source") == "6171" and e.get("target") == "6172":
            sh_6171 = e.get("sourceHandle")
    nb = len(nodes)
    nodes[:] = [n for n in nodes if n.get("id") != "6172"]
    if len(nodes) < nb:
        touched.append("6172:node removed")
    eb = len(edges)
    edges[:] = [e for e in edges if e.get("source") != "6172" and e.get("target") != "6172"]
    new_edge = {"id": "e-6171-modifynew-6250b", "source": "6171",
                "sourceHandle": sh_6171, "target": "6250b", "targetHandle": th_6250b, "type": "custom"}
    if not any(e.get("id") == new_edge["id"] for e in edges):
        edges.append(new_edge)
        touched.append("edge 6171::modify_new->6250b(直连)")

    # B. 删 6250-insuf/6250b-insuf 的 cv_feedback_zh item
    for n in nodes:
        if n.get("id") in ("6250-insuf", "6250b-insuf"):
            d = n.get("data", {})
            items = d.get("items", [])
            ib = len(items)
            items[:] = [it for it in items if it.get("variable_selector") != ["conversation", "cv_feedback_zh"]]
            if len(items) < ib:
                touched.append("%s:cv_feedback_zh item removed" % n["id"])

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
        ids = [n.get("id") for n in g["nodes"]]
        print("  verify 6172 removed:", "6172" not in ids)
        for n in g["nodes"]:
            nid = n.get("id"); d = n.get("data", {})
            if nid in MEM_NODES:
                print("  verify %s memory=%s" % (nid, bool(d.get("memory"))))
            if nid == "6250b":
                txt = d.get("prompt_template", [{}])[0].get("text", "")
                print("  verify 6250b: no 6172.merged=%s | has cv_mokuai=%s" % ("6172.merged" not in txt, "cv_mokuai" in txt))
            if nid == "6244":
                txt = d.get("prompt_template", [{}])[0].get("text", "")
                print("  verify 6244: no '用户反馈: {query_text}'=%s | user=%r" % (
                    "用户反馈: {{#6002.query_text#}}" not in txt, d.get("prompt_template", [{},{}])[1].get("text") if len(d.get("prompt_template",[]))>1 else "?"))
        has_edge = any(e.get("id") == "e-6171-modifynew-6250b" for e in g["edges"])
        print("  verify edge 6171->6250b:", has_edge)
        for n in g["nodes"]:
            if n.get("id") in ("6250-insuf", "6250b-insuf"):
                items = n.get("data", {}).get("items", [])
                has_fz = any(it.get("variable_selector") == ["conversation", "cv_feedback_zh"] for it in items)
                print("  verify %s cv_feedback_zh item removed=%s" % (n["id"], not has_fz))
    else:
        print("\n[DRY-RUN] no writes. Re-run with --apply to deploy.")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
