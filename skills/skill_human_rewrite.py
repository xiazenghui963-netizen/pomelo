"""活人感改写 Skill。

适配自 human-writing（SKILL.md + references + check_prose.py）。
流程：草稿重写 → 硬禁令检查 → 命中则修复一轮 → 相似度校验输出提醒。
全部在 execute 内完成，不依赖外部文件，检查脚本规则内嵌。
"""

import re

# ---------- 检查规则（移植自 human-writing/scripts/check_prose.py） ----------

HARD_STOPS = ("说白了", "说穿了", "先说结论")

HARD_JARGON = (
    "赋能", "抓手", "商业闭环", "价值闭环", "能力沉淀", "拉通", "底层逻辑", "顶层设计",
    "认知跃迁", "价值释放", "能力建设", "降本增效", "内容矩阵", "全链路", "组合拳",
    "打开想象空间", "结构性机会", "关键命题", "深层逻辑", "技术底座", "公共底座",
    "技术主权", "单点风险", "主脊柱", "材料锚点", "认知增量", "迭代闭环",
)

FORBIDDEN_PUNCTUATION = {
    "：": "中文冒号（仅可引出人物原话）",
    ":": "英文冒号",
    "—": "破折号",
    "–": "连接号式破折号",
}

PIVOT_PATTERNS = (
    re.compile(r"(?:并)?不是[^。！？\n]{0,90}而是"),
    re.compile(r"并非[^。！？\n]{0,90}而是"),
    re.compile(r"不在于[^。！？\n]{0,90}而在于"),
    re.compile(r"与其说[^。！？\n]{0,90}(?:不如|毋宁|倒不如)"),
    re.compile(r"[。！？!?]\s*而是"),
    re.compile(r"表面(?:上)?[^。！？\n]{0,90}(?:其实|实际|实则)"),
    re.compile(r"看似[^。！？\n]{0,90}(?:其实|实际|实则)"),
)

SEMANTIC_PIVOT_PATTERNS = (
    re.compile(r"(?:总|一直|曾|都)?以为[^！？\n]{2,60}?(?:其实|才发现|才明白|才知道|后来才)"),
    re.compile(r"(?:总|都|一直)以为[^！？\n]{2,60}?[。，](?:可|但|其实)"),
    re.compile(r"回头(?:看|一看)?才(?:发现|明白|知道)"),
    re.compile(r"(?:并)?不是[^。！？\n]{1,40}，(?:更|才)?是[^，。！？\n]"),
    re.compile(r"从来(?:都)?(?:不是|与[^。！？，\n]{1,12}无关)"),
    re.compile(r"答案(?:是否定的|恰恰相反)|恰恰相反"),
)

NOMINALIZATION_PATTERNS = (
    re.compile(r"进行(?:了|一次|一场|着)?[^。，！？\n]{0,10}(?:调整|优化|升级|分析|讨论|沟通|梳理|复盘|迭代|探索|尝试|思考|规划|布局)"),
    re.compile(r"实现了?[^。，！？\n]{0,14}的?[^。，！？\n]{0,6}(?:提升|增长|突破|转变|跃升|落地)"),
    re.compile(r"完成了?对[^。，！？\n]{0,16}的"),
    re.compile(r"起到了?[^。，！？\n]{0,12}的?作用"),
    re.compile(r"具有[^。，！？\n]{0,10}(?:意义|价值)"),
)

ROAD_SIGNS = ("更微妙的是", "还有一层", "只说对了一半", "值得注意的是", "需要指出的是", "从某种意义上说")

SOFT_MARKERS = ("真正", "本质上", "更深层次", "归根结底", "换句话说", "不可否认", "核心是", "关键在于", "这意味着")

LYRIC_WORDS = ("安放", "抵达", "微光", "褶皱", "丰盈", "滚烫", "轻盈", "赤裸", "剥开")

METAPHOR_WORDS = {
    "温度": ("降温", "升温", "冷却", "余温"),
    "战争": ("杀死", "死因", "枪响", "开火", "战场", "引爆", "弹药"),
    "建筑": ("坍塌", "崩塌", "地基", "砖头", "支柱", "废墟"),
    "仓储": ("仓库", "库房", "租金", "取货", "入库", "库存"),
    "道路": ("赛道", "岔路", "十字路口", "终点线", "门票"),
    "机器": ("齿轮", "引擎", "发动机", "血管", "骨架", "肌肉"),
    "海洋": ("蓝海", "浪潮", "潮水", "航船", "灯塔", "彼岸"),
}

TRIPLE_PARALLEL = re.compile(r"(?:[^。！？，\n]{2,14}[，、]){3,}")


def _check_prose(text: str) -> dict:
    hard: list[str] = []
    soft: list[str] = []

    for ch, label in FORBIDDEN_PUNCTUATION.items():
        if ch in text:
            hard.append(f"出现{label}")

    for phrase in HARD_STOPS:
        if phrase in text:
            hard.append(f"出现“{phrase}”")

    for phrase in HARD_JARGON:
        if phrase in text:
            hard.append(f"出现禁用黑话“{phrase}”")

    for pattern in PIVOT_PATTERNS + SEMANTIC_PIVOT_PATTERNS:
        if pattern.search(text):
            hard.append(f"疑似翻案腔：{pattern.pattern[:24]}…")

    for pattern in NOMINALIZATION_PATTERNS:
        if pattern.search(text):
            hard.append(f"疑似动词名词化：{pattern.pattern[:24]}…")

    for phrase in ROAD_SIGNS:
        if phrase in text:
            hard.append(f"出现洞察路标“{phrase}”")

    for marker in SOFT_MARKERS:
        if marker in text:
            soft.append(f"出现软路标“{marker}”，结合语境判断")

    for word in LYRIC_WORDS:
        if word in text:
            soft.append(f"出现抒情词“{word}”，检查是否给抽象概念穿衣服")

    for field, words in METAPHOR_WORDS.items():
        hits = [w for w in words if w in text]
        if len(hits) >= 2:
            soft.append(f"比喻换场“{field}”：{hits}")

    if TRIPLE_PARALLEL.search(text):
        soft.append("疑似三项以上同构排比，保留两项以内")

    return {"hard": hard, "soft": soft}


def _check_summary(text: str) -> str:
    check = _check_prose(text)
    hard = check["hard"]
    if not hard:
        return ""
    return "硬禁令命中：" + "；".join(hard[:8])


SYSTEM_DRAFT = """你是内容改写助手，任务是把用户给出的原文改写成一篇面向小红书的正文，表达方式完全不同，保留原文核心信息。改写必须符合「活人感写作」标准。

写作要求：
1. 写成一个见过事、愿意把来龙去脉讲清楚的人在说话，有具体动作、细节、时间和真实过程。
2. 第一稿直接写，先让主语和动作出现，原因、条件接在后面。
3. 每一段带来一件新东西：新事实、新动作、新例子、新区别或新结果。同一观点换说法不算推进。
4. 段落长短有松有紧，允许正常的重复、补充和诚实修正，不按固定间隔表演随意。
5. 判断可以偏、可以有情绪，依据放在附近。
6. 口语化但要克制，不靠“老铁”“姐妹们”“谁懂啊”一类称呼堆活人感。
7. 禁止洗稿：完全改变句式结构，打散原文句子顺序，更换表达词汇，禁止连续照抄原文长句。
8. 直接给结果文本，不要输出任何说明。

成稿硬性禁令（命中任何一项都算不合格）：
- 禁止冒号“：”“:”（仅允许引出人物原话时使用）。
- 禁止破折号“—”“——”“–”。
- 禁止翻案腔，例如“不是……而是”“并非……”“不在于……而在于”“与其说……不如说”“表面……其实”“看似……实则”“你(总/一直)以为……其实”“回头才发现”“A不重要，重要的是B”等。判断从正面直接下，先给判断再给依据。
- 禁止三项以上同构排比，同类排比最多两项。
- 禁止动词名词化，例如“进行了调整”“实现了提升”“完成了对……的优化”，还原成“把方案改了”“多挣了多少”。
- 禁止黑话：赋能、抓手、闭环、底层逻辑、顶层设计、认知跃迁、降本增效、全链路、组合拳、沉淀、对齐、颗粒度等。
- 禁止“说白了”“说穿了”“先说结论”。
- 禁止“更微妙的是”“还有一层”“只说对了一半”“值得注意的是”“需要指出的是”“从某种意义上说”一类段落路标。
- 禁止用仓库、温度、浪潮、骨架、齿轮等借喻包装抽象概念；确实在写这些事物本身时不受限。
- 不用“真正的”“本质上”“归根结底”一类抬价词替普通事情定调。"""

SYSTEM_REPAIR = """你是改稿执行者。下面这段文本违反了「活人感写作」的硬性禁令。请只修复这些问题，保持原文的意思、结构和语气，输出修复后的完整文本，不要输出检查说明。

修复原则：先找到原本想下的事实判断，用普通句子从正面说出来，不要寻找另一种漂亮句式替换；禁止冒号、破折号、翻案腔、名词化、三项排比和黑话。"""


def _mock(source: str) -> dict:
    source = (source or "").strip()
    if not source:
        return {"text": "", "similarity_score": 0.0, "reminder": "", "checks": []}
    text = source.replace("吧", "呀").replace("吗", "啦")
    return {"text": text, "similarity_score": 1.0, "reminder": "", "checks": []}


skill_meta = {
    "name": "skill_human_rewrite",
    "description": "正文改写（活人感写作）：内置防洗稿强制要求、小红书风格表达、硬禁令检查与翻案腔/黑话/名词化修复，支持传入私有资料，改写后自动相似度校验",
    "access_level": 1,
    "cost_point": 8,
    "parameters": [
        {"name": "source_text", "type": "string", "required": True, "label": "原文/笔记文本"},
        {"name": "materials_text", "type": "string", "required": False, "label": "私有资料"},
    ],
}


def execute(params: dict, llm_client) -> dict:  # noqa: ANN001
    source = params.get("source_text", "").strip()
    materials = params.get("materials_text", "")
    if not source:
        return {"text": "", "similarity_score": 0.0, "reminder": "无原文可改写", "checks": []}

    material_block = ""
    if materials:
        material_block = f"\n\n可参考的私有资料（自然融入，不偏离主题）：\n{materials}"

    user_prompt = f"请将下面的原文改写成全新的小红书正文。\n\n原文：\n{source}{material_block}"

    text = llm_client.chat(SYSTEM_DRAFT, user_prompt)
    if not text:
        return _mock(source)

    issue = _check_summary(text)
    if issue:
        repair_prompt = f"{issue}\n\n待修复文本：\n{text}"
        repaired = llm_client.chat(SYSTEM_REPAIR, repair_prompt)
        if repaired:
            text = repaired.strip()
            llm_client.last_output = text

    similarity_score = llm_client.similarity(source, text)
    threshold = getattr(llm_client, "similarity_threshold", 0.35)
    checks = _check_prose(text)

    reminders = []
    if checks["hard"]:
        reminders.append("命中硬禁令：" + "；".join(checks["hard"][:5]))
    if similarity_score > threshold:
        reminders.append(f"改写文本与原文相似度 {similarity_score:.2f}（超过阈值 {threshold}），请人工再调整或重新改写。")
    reminder = "；".join(reminders)

    return {
        "text": text,
        "similarity_score": similarity_score,
        "reminder": reminder,
        "checks": {"hard": checks["hard"], "soft": checks["soft"]},
    }