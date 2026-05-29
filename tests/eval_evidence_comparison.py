"""
Quantitative evaluation: new evidence system (weighted scoring + TF-IDF)
vs old (first-keyword-match) system.

Test data: 4 real manual-flow fixtures + 1 built-in sample.

Strategies compared:
  A) Old: first-keyword-first-sentence match
  B) New-A: weighted scoring (kw_density 0.35 + focus 0.40 + position 0.15 - exhaust 0.10)
  C) New-B: TF-IDF semantic ranking (0.7 similarity + 0.3 keyword density)

Metrics per dimension (0-3 scale):
  - Keyword relevance: evidence contains dimension keywords       (1 pt)
  - Multi-keyword coverage: evidence contains >=2 dim keywords     (1 pt)
  - Focus alignment: evidence mentions dimension focus concept     (1 pt)

Additional metrics:
  - Evidence diversity: Jaccard overlap between evidence strings across dims
  - Length reasonableness: evidence length within 20-80 chars
  - Duplicate evidence count
"""

import json
import re
import sys
from pathlib import Path

# -- Sklearn-based TF-IDF (inlined to avoid pypdf import chain) --
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    HAS_SKLEARN = True
except Exception:
    HAS_SKLEARN = False

# -- Inline the relevant scoring logic --

def looks_like_garbled_text(text):
    """Inline from scoring_app.core.text_quality"""
    if not text:
        return True
    bad = ["锟斤拷", "烫烫烫", "婊戝", "----"]
    for token in bad:
        if token in text:
            return True
    if len(text) < 4:
        return True
    # High ratio of non-CJK, non-ASCII punctuation
    excluded = set(" ，。、；：？！""''（）【】《》\n\r\t...---")
    meaningful = sum(1 for c in text if c not in excluded)
    if meaningful == 0:
        return True
    cjk = sum(1 for c in text if "一" <= c <= "鿿" or "　" <= c <= "〿")
    if cjk / meaningful < 0.15:
        return True
    return False


def split_sentences(text):
    """Split text into sentences by Chinese/English terminators."""
    return [segment.strip() for segment in re.split(r"[。！？\n\r]+", text) if segment.strip()]


def limit_text(text, size):
    """Truncate text to approximately *size* characters."""
    if len(text) <= size:
        return text
    return text[: size - 1].rstrip() + "..."


# -- OLD system: first-keyword-first-sentence match --
def old_build_evidence(text, keywords):
    """Simulate the OLD _build_evidence(): first keyword first sentence match."""
    sentences = split_sentences(text)
    if not keywords:
        for sentence in sentences:
            if not looks_like_garbled_text(sentence):
                return limit_text(sentence, 80)
        return ""

    for keyword in keywords:
        for sentence in sentences:
            if looks_like_garbled_text(sentence):
                continue
            if keyword in sentence:
                return limit_text(sentence, 80)

    # Fallback: first non-garbled sentence
    for sentence in sentences:
        if not looks_like_garbled_text(sentence):
            return limit_text(sentence, 80)
    return "文档文本提取质量不足，未找到可直接引用的有效证据。"


# -- NEW helper functions (inlined from scoring_app.scoring) --
def calc_keyword_density(text, keywords):
    """Calculate keyword hit ratio (0.0-1.0)."""
    if not keywords:
        return 0.0
    hits = sum(1 for kw in keywords if kw in text)
    return min(hits / float(len(keywords)), 1.0)


def calc_focus_alignment(text, dim_name, dim_focus):
    """Calculate focus alignment score (0.0-1.0)."""
    if not dim_name and not dim_focus:
        return 0.0

    focus_score = 0.0
    name_score = 0.0

    if dim_focus:
        if dim_focus in text:
            focus_score = 1.0
        else:
            text_chars = set(text)
            focus_chars = set(dim_focus)
            if focus_chars:
                overlap = len(text_chars & focus_chars)
                focus_score = overlap / len(focus_chars)

    if dim_name:
        if dim_name in text:
            name_score = 0.8
        else:
            text_chars = set(text)
            name_chars = set(dim_name)
            if name_chars:
                overlap = len(text_chars & name_chars)
                name_score = 0.6 * (overlap / len(name_chars))

    if dim_focus and dim_name:
        return 0.6 * focus_score + 0.4 * name_score
    elif dim_focus:
        return focus_score
    else:
        return name_score


def calc_position_bonus(idx, total_sentences):
    """Calculate position quality score (0.0-1.0)."""
    if total_sentences <= 1:
        return 1.0
    if idx == 0:
        return 1.0
    if idx == total_sentences - 1:
        return 0.6
    return 0.0


def calc_exhaustivity_penalty(sentence, used_sentences):
    """Return 1.0 if sentence is already used as evidence."""
    if not used_sentences:
        return 0.0
    return 1.0 if sentence in used_sentences else 0.0


def new_build_evidence(text, dimension, used_sentences=None):
    """NEW strategy A: weighted sentence scoring."""
    keywords = dimension.get("keywords", [])
    sentences = split_sentences(text)
    candidates = []

    for idx, sentence in enumerate(sentences):
        if looks_like_garbled_text(sentence):
            continue

        kw_density = calc_keyword_density(sentence, keywords)
        focus_score = calc_focus_alignment(
            sentence,
            dimension.get("name", ""),
            dimension.get("focus", ""),
        )
        pos_score = calc_position_bonus(idx, len(sentences))
        exhaustivity = calc_exhaustivity_penalty(sentence, used_sentences or set())

        total = (
            0.35 * kw_density + 0.40 * focus_score + 0.15 * pos_score - 0.10 * exhaustivity
        )
        candidates.append((total, sentence))

    if not candidates:
        return "文档文本提取质量不足，未找到可直接引用的有效证据。"

    candidates.sort(key=lambda x: x[0], reverse=True)
    return limit_text(candidates[0][1], 80)


# -- TF-IDF EvidenceRanker (inlined) --

class InlineEvidenceRanker:
    """Simplified TF-IDF ranker matching scoring_app.evidence_rancer.EvidenceRanker."""

    def __init__(self, dimensions):
        self.dimensions = {d["id"]: d for d in dimensions}
        if HAS_SKLEARN:
            dim_corpus = []
            self.dim_ids = []
            for dim in dimensions:
                doc_text = "{} {} {}".format(
                    dim["name"], dim["focus"], " ".join(dim.get("keywords", []))
                )
                dim_corpus.append(doc_text)
                self.dim_ids.append(dim["id"])

            self.vectorizer = TfidfVectorizer(
                analyzer="char_wb", ngram_range=(2, 4), max_features=5000
            )
            self.dim_vectors = self.vectorizer.fit_transform(dim_corpus)

    def rank_sentences(self, sentences, dimension_id):
        """Return top-3 sentences ranked by cosine similarity."""
        if not HAS_SKLEARN:
            return []
        if not sentences:
            return []

        sent_vectors = self.vectorizer.transform(sentences)
        dim_idx = self.dim_ids.index(dimension_id)
        dim_vector = self.dim_vectors[dim_idx]
        similarities = cosine_similarity(sent_vectors, dim_vector).flatten()
        ranked = sorted(
            range(len(sentences)), key=lambda i: similarities[i], reverse=True
        )
        top3 = ranked[:3]
        return [
            {"sentence": sentences[i], "similarity": float(similarities[i])}
            for i in top3
        ]

    def best_evidence(self, text, dimension_id):
        """Select best evidence using 0.7 TF-IDF + 0.3 keyword density."""
        if not HAS_SKLEARN:
            return None

        dim = self.dimensions.get(dimension_id)
        if not dim:
            return None

        sentences = split_sentences(text)
        candidates = self.rank_sentences(sentences, dimension_id)
        if not candidates:
            return "文档文本提取质量不足，未找到可直接引用的有效证据。"

        keywords = dim.get("keywords", [])
        for c in candidates:
            kw_density = calc_keyword_density(c["sentence"], keywords)
            c["combined_score"] = 0.7 * c["similarity"] + 0.3 * kw_density

        candidates.sort(key=lambda c: c["combined_score"], reverse=True)
        return limit_text(candidates[0]["sentence"], 80)


def tfidf_build_evidence(text, dimension, ranker):
    """NEW strategy B: TF-IDF ranking."""
    return ranker.best_evidence(text, dimension["id"])


# =========================================================================
#  Fixture data
# =========================================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = PROJECT_ROOT / "test" / "fixtures" / "manual_flow"

# -- Built-in sample data for 温故知新 --
SAMPLE_DOCUMENT_TEXT = (
    "温故知新个人汇报样例材料"
    "本次复盘围绕年度战略目标、组织痛点、关键任务推进与结果改善展开。"
    "我先说明业务背景，再展示问题分析、行动步骤、协同节点与阶段成效。"
    "课题立项部分聚焦组织效率、关键指标提升与资源规划安排。"
    "行动结果包括流程时长下降18%，跨团队协同效率提升22%，客户满意度提升9%。"
    "复盘部分同时补充不足、改进路径、后续迭代节奏与里程碑安排。"
    "汇报材料强调目标、规划、行动、结果、反思、创新与突破。"
)

SAMPLE_TRANSCRIPT_TEXT = (
    "大家好，我将按背景、问题、行动、结果四个部分完成汇报。"
    "首先解释为什么这个课题与当前组织战略直接相关，其次说明资源和推进计划。"
    "然后展示关键动作、执行节点、协同方式以及阶段结果。"
    "最后总结亮点、不足和下一步改进安排，整体控制在八分钟内。"
)

# -- Manual fixture document and transcript texts --
DOC1 = (
    "行动学习第一次课程认知升级汇报样例。 "
    "我当前负责战略项目推进，现状是能完成任务拆解，"
    "但对外部趋势、个人能力短板和组织第三次创业之间的连接还不够系统。 "
    "直面问题部分，我结合商业综合推理、管理技能、管理个性、管理风格、"
    "职业锚和组织忠诚度测评，识别出三个核心瓶颈："
    "战略判断依赖经验、跨部门影响力不足、复盘反馈闭环不稳定。 "
    "环境评估部分，我用PEST分析和行业趋势判断，"
    "发现新能源、海外合规、智能制造会改变岗位能力要求，"
    "机会面是数据化管理能力提升，风险面是原有经验失效。 "
    "创新构想部分，我把ASTRAL领导力模型和IDP方案结合，"
    "计划用AI辅助学习、轮岗、项目历练和导师辅导，"
    "形成从我的世界到我们的世界的转变。 "
    "结构性方法部分，我按照IDP七步法展开：自我评估、环境评估、职业选择、"
    "确定目标、行动计划、行动实施、评估反馈，"
    "并用现状、目标、能力、计划四模块组织材料。 "
    "可操作性部分，我设定1年完成数据分析能力补强，"
    "2年主导跨部门战略项目，3年承担业务单元战略协同角色；"
    "每月产出一份复盘报告，责任人为本人和导师，"
    "交付物包括能力地图、项目里程碑和反馈记录。 "
    "资源需求包括导师辅导、轮岗机会、AI工具订阅和项目实践名额，"
    "评价方式包括测评复测、行为记录、项目成果和上级反馈。"
)

TRANS1 = (
    "各位老师好，我本次汇报按自我认知、外部环境、职业目标、"
    "能力发展、行动计划和评估反馈展开。"
    "我先说明测评结果暴露出的能力短板，再说明PEST趋势对岗位的影响。"
    "我的核心目标不是单纯提升个人能力，"
    "而是把个人IDP和中集车辆第三次创业的组织需求连接起来。"
    "最后我用三分钟说明一年、两年、三年的里程碑，"
    "并回答导师关于资源和风险的问题。整体控制在十五分钟以内。"
)

DOC2 = (
    "行动学习第二次课程组织协同汇报样例。 "
    "案例背景是管报与法报数据在月结第三天经常出现口径差异，"
    "导致业务部门反复解释，财务BP和经营分析团队互相等待。 "
    "直面问题部分，我没有把原因归为人的责任心不足，"
    "而是用七大协同障碍根源分析：组织分工不明确、目标差异、部门墙、"
    "沟通技能缺失、横向沟通机制不健全和缺乏协作文化。 "
    "根源剖析显示，RACI矩阵里数据口径确认人缺失，"
    "流程中没有同步节点，指标目标只考核本部门准时率，没有共同目标。 "
    "创新构想部分，我设计服务协同、指导协同、管控协同和情感协同四类机制："
    "建立统一数据字典，设置双计双考机制，"
    "引入跨部门满意度互评，并建立问题升级机制。 "
    "结构性方法部分，我按聚焦、共创、对齐、闭环四步法确定共同目标，"
    "围绕组织、流程、目标、机制、氛围和影响力六个维度设计方案。 "
    "可操作性部分，短期1到2周内完成数据字段清单、责任人、"
    "同步时间节点和校验模板；中期1到3个月内上线月结协同看板，"
    "明确里程碑、风险应对和资源配置。 "
    "预期成果是月结差异项减少30%，重复沟通时间降低20%，"
    "争议问题在24小时内完成升级处理。"
)

TRANS2 = (
    "各位老师好，本次汇报围绕组织协同问题展开。"
    "我首先说明数据口径差异造成的实际问题。"
    "接下来我用七大协同障碍作为分析框架，"
    "然后通过RACI矩阵找到流程中的关键缺失节点。"
    "我的方案围绕四类协同机制设计，重点在数据同步和横向沟通机制。"
    "本次汇报控制在十五分钟，答辩部分重点回应风险和资源投入。"
    "评委问到为什么不是人的问题，我回答这是流程、机制和共同目标缺失造成的系统问题。"
)

DOC3 = (
    "行动学习第三次课程问题解决能力提升汇报样例。 "
    "案例背景是某产线换型后首周返工率从2.5%上升到6.8%，"
    "交付周期延长两天，客户投诉风险升高。 "
    "直面问题部分，我用根源拆解三层模型分析："
    "现象层是返工率和交付周期异常，"
    "流程层是首件确认和异常升级节点缺失，"
    "系统层是数据看板滞后、SOP培训不一致和授权机制不清。 "
    "我同时识别风险面和机会面：风险是质量损失和客户信任下降，"
    "机会是建立可复用的换型问题解决机制。 "
    "结构性方法部分，我按照六步框架发现、分析、目标、方案、执行、评估展开，"
    "并根据执行偏差类问题选择5Why、5W2H、SOP体系搭建和数据运营闭环。 "
    "创新构想部分，我引入AI辅助工具对异常记录做聚类，"
    "把经验复用和快速适配结合，形成换型风险清单和班组训练脚本。 "
    "可操作性部分，第一周完成数据复盘和首件确认SOP更新，"
    "第二周完成分层培训，第三到第四周上线日清看板；"
    "责任人为生产主管、质量工程师和班组长，"
    "交付物包括SOP、培训记录、看板和复盘报告。 "
    "评估指标包括返工率降到3%以内、异常响应不超过30分钟、"
    "换型后首周一次交检通过率提升到96%。"
)

TRANS3 = (
    "我的汇报按背景、问题、分析、方案、计划和总结展开。"
    "整个方案有试点验证、动态调整和全面推广三个阶段，答辩用五分钟回应风险。"
)

# -- 温故知新 definition (inlined from rules.py) --
WG_DIMENSIONS = [
    {"id": 1, "name": "战略链接与价值认知", "focus": "战略理解深度",
     "keywords": ["战略", "目标", "业务", "价值", "支撑", "痛点", "任务"]},
    {"id": 2, "name": "知识融合与框架应用", "focus": "工具应用精度",
     "keywords": ["框架", "模型", "工具", "方法", "认知", "协同", "解题"]},
    {"id": 3, "name": "行为的具体性与可观察性", "focus": "行为颗粒度",
     "keywords": ["动作", "场景", "步骤", "协同", "节点", "执行", "具体"]},
    {"id": 4, "name": "行动的有效性与结果导向", "focus": "结果验证强度",
     "keywords": ["结果", "成效", "提升", "闭环", "达成", "效率", "指标"]},
    {"id": 5, "name": "反思深刻性与真诚度", "focus": "反思迭代高度",
     "keywords": ["反思", "复盘", "不足", "改进", "认知", "迭代", "收获"]},
    {"id": 6, "name": "课题的战略价值", "focus": "价值贡献度",
     "keywords": ["课题", "价值", "战略", "效能", "需求", "痛点", "组织"]},
    {"id": 7, "name": "目标与规划的前瞻性", "focus": "落地可行性",
     "keywords": ["目标", "规划", "里程碑", "资源", "计划", "推进", "实施"]},
    {"id": 8, "name": "创新与突破性", "focus": "方案差异化",
     "keywords": ["创新", "突破", "优化", "改善", "尝试", "新", "升级"]},
    # transcript-based (skipped when no transcript)
    {"id": 9, "name": "逻辑的严谨性和链条完整性", "focus": "系统思维",
     "keywords": ["首先", "其次", "最后", "因为", "所以", "问题", "结果", "闭环"],
     "source_key": "transcript"},
    {"id": 10, "name": "材料与汇报的展现力", "focus": "信息传递效率",
     "keywords": ["表达", "重点", "总结", "时间", "展示", "汇报", "听众"],
     "source_key": "transcript"},
]

# -- 行动学习 base definition (for general action learning reports) --
XL_BASE_DIMENSIONS = [
    {"id": 1, "name": "直面问题", "focus": "问题穿透深度",
     "keywords": ["问题", "痛点", "根因", "现状", "数据", "矛盾", "挑战"]},
    {"id": 2, "name": "创新构想", "focus": "方案差异化价值",
     "keywords": ["创新", "构想", "突破", "优化", "新方案", "改进"]},
    {"id": 3, "name": "结构性方法", "focus": "方案严谨性",
     "keywords": ["结构", "框架", "模型", "分析", "方法", "逻辑", "系统"]},
    {"id": 4, "name": "可操作性", "focus": "落地可行性",
     "keywords": ["步骤", "执行", "资源", "落地", "责任", "推进", "计划"]},
    {"id": 5, "name": "表达清晰", "focus": "信息传递效率",
     "keywords": ["表达", "清晰", "重点", "结构", "总结", "层次", "说明"],
     "source_key": "transcript"},
    {"id": 6, "name": "回答问题", "focus": "互动响应质量",
     "keywords": ["提问", "回答", "问题", "补充", "回应", "说明"],
     "source_key": "transcript"},
    {"id": 7, "name": "时间管理", "focus": "流程管控能力",
     "keywords": ["时间", "分钟", "节奏", "安排", "控制", "进度"],
     "source_key": "transcript"},
]

# -- Course-specific keyword overrides --
COURSE_KEYWORDS = {
    "行动学习-认知升级": {
        "直面问题": ["测评", "商业综合推理", "管理技能", "管理个性", "管理风格",
                     "职业锚", "PEST", "短板", "瓶颈"],
        "创新构想": ["ASTRAL", "IDP", "轮岗", "项目历练", "AI", "第三次创业", "组织发展"],
        "结构性方法": ["IDP七步法", "自我评估", "环境评估", "职业选择", "确定目标",
                       "行动计划", "7-2-1", "现状", "目标", "能力"],
        "可操作性": ["行动步骤", "时间节点", "责任人", "交付物", "1年", "2年", "3年",
                     "资源", "评价", "反馈闭环"],
    },
    "行动学习-组织协同": {
        "直面问题": ["七大协同障碍", "组织分工", "目标差异", "部门墙", "横向沟通",
                     "协作文化", "流程", "机制", "案例"],
        "创新构想": ["服务协同", "指导协同", "管控协同", "情感协同", "RACI",
                     "双计双考", "满意度", "共同目标"],
        "结构性方法": ["七大障碍", "RACI", "流程优化", "冲突处理", "情感账户",
                       "组织", "流程", "目标", "机制", "影响力", "聚焦", "共创",
                       "对齐", "闭环"],
        "可操作性": ["行动步骤", "时间节点", "责任人", "交付物", "1-2周", "1-3个月",
                     "风险", "里程碑", "资源"],
    },
    "行动学习-问题解决": {
        "直面问题": ["现象层", "流程层", "系统层", "风险面", "机会面", "问题类型",
                     "边界", "根因"],
        "创新构想": ["问题导向", "创新思维", "AI辅助", "差异化", "业务特性", "价值提升"],
        "结构性方法": ["六步框架", "发现", "分析", "目标", "方案", "执行", "评估",
                       "模糊决策", "PrOACT", "5W2H", "5Why", "数据驱动"],
        "可操作性": ["行动步骤", "时间节点", "责任人", "交付物", "资源", "风险",
                     "应对措施", "阶段性目标", "最终目标"],
    },
}


def get_dimensions(report_type):
    """Get dimensions for a report type."""
    if report_type == "温故知新":
        return list(WG_DIMENSIONS)
    elif report_type.startswith("行动学习"):
        # Apply course-specific keywords if available
        course_kw = COURSE_KEYWORDS.get(report_type, {})
        dims = []
        for d in XL_BASE_DIMENSIONS:
            d_copy = dict(d)
            if d["name"] in course_kw:
                d_copy["keywords"] = course_kw[d["name"]]
            dims.append(d_copy)
        return dims
    else:
        return list(XL_BASE_DIMENSIONS)


# =========================================================================
#  Evaluation metrics
# =========================================================================

def eval_relevance(evidence_text, dimension):
    """Score evidence relevance (0-3)."""
    if not evidence_text or evidence_text in (
        "文档文本提取质量不足，未找到可直接引用的有效证据。",
        "录音材料未提供。",
        "录音材料未提供",
    ):
        return 0

    score = 0
    keywords = dimension.get("keywords", [])
    focus = dimension.get("focus", "")
    dim_name = dimension.get("name", "")

    # 1 pt: contains at least one keyword
    if any(kw in evidence_text for kw in keywords):
        score += 1

    # 1 pt: contains >=2 keywords
    if sum(1 for kw in keywords if kw in evidence_text) >= 2:
        score += 1

    # 1 pt: focus alignment
    has_focus = False
    if focus and focus in evidence_text:
        has_focus = True
    if dim_name and dim_name in evidence_text:
        has_focus = True
    if not has_focus and focus:
        text_chars = set(evidence_text)
        focus_chars = set(focus)
        if focus_chars:
            overlap_ratio = len(text_chars & focus_chars) / len(focus_chars)
            if overlap_ratio > 0.50:
                has_focus = True
    if has_focus:
        score += 1

    return score


def eval_diversity(dimensions_with_evidence):
    """Evidence diversity = 1 - avg pairwise Jaccard similarity."""
    skip_values = {
        "录音材料未提供。", "录音材料未提供",
        "文档文本提取质量不足，未找到可直接引用的有效证据。"
    }
    evidence_texts = [
        d["evidence"] for d in dimensions_with_evidence
        if d["evidence"] and d["evidence"] not in skip_values
    ]
    if len(evidence_texts) < 2:
        return 1.0

    total_sim = 0.0
    pairs = 0
    for i in range(len(evidence_texts)):
        for j in range(i + 1, len(evidence_texts)):
            set_i = set(evidence_texts[i])
            set_j = set(evidence_texts[j])
            intersection = len(set_i & set_j)
            union = len(set_i | set_j)
            jaccard = intersection / max(union, 1)
            total_sim += jaccard
            pairs += 1

    avg_similarity = total_sim / max(pairs, 1)
    return 1.0 - avg_similarity


def count_duplicate_evidence(dimensions_with_evidence):
    """Count duplicate evidence strings across dimensions."""
    skip_values = {
        "录音材料未提供。", "录音材料未提供",
        "文档文本提取质量不足，未找到可直接引用的有效证据。"
    }
    evidence_counts = {}
    for d in dimensions_with_evidence:
        ev = d["evidence"]
        if ev and ev not in skip_values:
            evidence_counts[ev] = evidence_counts.get(ev, 0) + 1
    return sum(v - 1 for v in evidence_counts.values() if v > 1)


def eval_length_ok(evidence_text):
    """Check if evidence length is reasonable (20-80 chars)."""
    if not evidence_text:
        return False
    if evidence_text in (
        "录音材料未提供。", "录音材料未提供",
        "文档文本提取质量不足，未找到可直接引用的有效证据。"
    ):
        return True
    return 20 <= len(evidence_text) <= 80


def count_keywords(evidence_text, keywords):
    """Count how many keywords appear in evidence."""
    if not evidence_text:
        return 0
    return sum(1 for kw in keywords if kw in evidence_text)


# =========================================================================
#  Run comparison
# =========================================================================

def run_comparison(name, dimensions, document_text, transcript_text, with_transcript):
    """Run all three strategies on all applicable dimensions."""
    doc_only = [d for d in dimensions if d.get("source_key") != "transcript"]
    if HAS_SKLEARN:
        ranker = InlineEvidenceRanker(dimensions)
    else:
        ranker = None

    # Track results for each strategy
    results = []

    for dim in dimensions:
        is_doc = dim.get("source_key") != "transcript"
        relevant_text = document_text if is_doc else transcript_text

        if not is_doc and not with_transcript:
            continue
        if not is_doc and not relevant_text.strip():
            continue

        # --- Strategy A: Old first-keyword-match ---
        old_ev = old_build_evidence(relevant_text, dim.get("keywords", []))

        # --- Strategy B: New weighted scoring (no TF-IDF) ---
        new_w_ev = new_build_evidence(relevant_text, dim)

        # --- Strategy C: TF-IDF (if available) ---
        if ranker:
            tfidf_ev = tfidf_build_evidence(relevant_text, dim, ranker)
            if tfidf_ev is None:
                tfidf_ev = new_w_ev  # fallback
        else:
            tfidf_ev = None

        old_rel = eval_relevance(old_ev, dim)
        new_w_rel = eval_relevance(new_w_ev, dim)
        tfidf_rel = eval_relevance(tfidf_ev, dim) if tfidf_ev else None

        results.append({
            "dim_id": dim["id"],
            "dim_name": dim["name"],
            "source": "文档" if is_doc else "录音转写",
            "old_evidence": old_ev[:80] if old_ev else "",
            "new_w_evidence": new_w_ev[:80] if new_w_ev else "",
            "tfidf_evidence": tfidf_ev[:80] if tfidf_ev else "",
            "old_relevance": old_rel,
            "new_w_relevance": new_w_rel,
            "tfidf_relevance": tfidf_rel,
            "old_kw_count": count_keywords(old_ev, dim.get("keywords", [])),
            "new_w_kw_count": count_keywords(new_w_ev, dim.get("keywords", [])),
            "tfidf_kw_count": count_keywords(tfidf_ev, dim.get("keywords", [])) if tfidf_ev else None,
            "old_len_ok": eval_length_ok(old_ev),
            "new_w_len_ok": eval_length_ok(new_w_ev),
            "tfidf_len_ok": eval_length_ok(tfidf_ev) if tfidf_ev else None,
            "w_improvement": new_w_rel - old_rel,
            "tfidf_improvement": (tfidf_rel - old_rel) if tfidf_rel is not None else None,
        })

    # --- Aggregate ---
    old_avg = sum(r["old_relevance"] for r in results) / max(len(results), 1)
    new_w_avg = sum(r["new_w_relevance"] for r in results) / max(len(results), 1)
    w_pct = ((new_w_avg - old_avg) / max(old_avg, 0.001)) * 100

    tfidf_scores = [r["tfidf_relevance"] for r in results if r["tfidf_relevance"] is not None]
    tfidf_avg = sum(tfidf_scores) / max(len(tfidf_scores), 1) if tfidf_scores else None

    w_improved = sum(1 for r in results if r["w_improvement"] > 0)
    w_same = sum(1 for r in results if r["w_improvement"] == 0)
    w_regressed = sum(1 for r in results if r["w_improvement"] < 0)

    # Diversity & dup: computed over doc-only dimensions for old + new-w
    doc_old_data = [
        {"evidence": r["old_evidence"], "score": r["old_relevance"]}
        for r in results if r["source"] == "文档"
    ]
    doc_new_w_data = [
        {"evidence": r["new_w_evidence"], "score": r["new_w_relevance"]}
        for r in results if r["source"] == "文档"
    ]
    doc_tfidf_data = []
    if tfidf_avg is not None:
        doc_tfidf_data = [
            {"evidence": r["tfidf_evidence"], "score": r["tfidf_relevance"]}
            for r in results if r["source"] == "文档"
        ]

    return {
        "name": name,
        "details": results,
        "old_avg_relevance": round(old_avg, 3),
        "new_w_avg_relevance": round(new_w_avg, 3),
        "tfidf_avg_relevance": round(tfidf_avg, 3) if tfidf_avg is not None else None,
        "w_pct_improvement": round(w_pct, 1),
        "w_improved": w_improved, "w_same": w_same, "w_regressed": w_regressed,
        "old_diversity": round(eval_diversity(doc_old_data), 3),
        "new_w_diversity": round(eval_diversity(doc_new_w_data), 3),
        "tfidf_diversity": round(eval_diversity(doc_tfidf_data), 3) if doc_tfidf_data else None,
        "old_dup": count_duplicate_evidence(doc_old_data),
        "new_w_dup": count_duplicate_evidence(doc_new_w_data),
        "tfidf_dup": count_duplicate_evidence(doc_tfidf_data) if doc_tfidf_data else None,
        "old_len_pct": round(sum(1 for r in results if r["old_len_ok"]) / max(len(results), 1) * 100, 1),
        "new_w_len_pct": round(sum(1 for r in results if r["new_w_len_ok"]) / max(len(results), 1) * 100, 1),
        "tfidf_len_pct": round(sum(1 for r in results if r.get("tfidf_len_ok")) / max(len(results), 1) * 100, 1) if tfidf_avg is not None else None,
        "old_avg_kw": round(sum(r["old_kw_count"] for r in results) / max(len(results), 1), 2),
        "new_w_avg_kw": round(sum(r["new_w_kw_count"] for r in results) / max(len(results), 1), 2),
        "tfidf_avg_kw": round(sum(r["tfidf_kw_count"] for r in results if r["tfidf_kw_count"] is not None) / max(len(results), 1), 2) if tfidf_avg is not None else None,
    }


# =========================================================================
#  Output helpers
# =========================================================================

def print_table(results, name, has_tfidf):
    """Print per-dimension comparison table."""
    print()
    print("=" * 140)
    print(f"  Fixture: {name}  (TF-IDF: {'yes' if has_tfidf else 'no'})")
    print("=" * 140)
    if has_tfidf:
        header = (
            f"{'Dim':<3} {'Src':<5} {'Name':<14} "
            f"{'Old(keyword)':<32} {'New-W(weight)':<32} {'TF-IDF(semantic)':<32} "
            f"{'OldR':>4} {'W-R':>4} {'T-R':>4}"
        )
    else:
        header = (
            f"{'Dim':<3} {'Src':<5} {'Name':<14} "
            f"{'Old Evidence (keyword match)':<38} {'New Evidence (weighted)':<38} "
            f"{'OldR':>4} {'NewR':>4}"
        )
    print(header)
    print("-" * 140)
    for r in results:
        old_ev = r["old_evidence"][:30]
        new_ev = r["new_w_evidence"][:30]
        if has_tfidf:
            t_ev = (r.get("tfidf_evidence") or "")[:30]
            print(
                f"{r['dim_id']:<3} {r['source']:<5} {r['dim_name']:<14} "
                f"{old_ev:<32} {new_ev:<32} {t_ev:<32} "
                f"{r['old_relevance']:>4} {r['new_w_relevance']:>4} "
                f"{r.get('tfidf_relevance', '-'):>4}"
            )
        else:
            print(
                f"{r['dim_id']:<3} {r['source']:<5} {r['dim_name']:<14} "
                f"{old_ev:<38} {new_ev:<38} "
                f"{r['old_relevance']:>4} {r['new_w_relevance']:>4}"
            )
    print()


def print_summary(r):
    print(f"  --- {r['name']} ---")
    print(f"  Relevance (0-3):")
    print(f"    Old (keyword-first):      {r['old_avg_relevance']:.3f}/3")
    print(f"    New-W (weighted scoring): {r['new_w_avg_relevance']:.3f}/3  ({r['w_pct_improvement']:+.1f}%)")
    if r["tfidf_avg_relevance"] is not None:
        ti = r.get("tfidf_avg_relevance", 0) - r["old_avg_relevance"]
        tip = (ti / max(r["old_avg_relevance"], 0.001)) * 100
        print(f"    TF-IDF (semantic):         {r['tfidf_avg_relevance']:.3f}/3  ({tip:+.1f}%)")
    print(f"  Dimensional change (weighted): "
          f"+{r['w_improved']} improved, {r['w_same']} same, {r['w_regressed']} regressed")
    print(f"  Diversity:        OLD {r['old_diversity']:.3f}  W {r['new_w_diversity']:.3f}"
          + (f"  TF-IDF {r['tfidf_diversity']:.3f}" if r["tfidf_diversity"] is not None else ""))
    print(f"  Duplicate ev:     OLD {r['old_dup']}  W {r['new_w_dup']}"
          + (f"  TF-IDF {r['tfidf_dup']}" if r["tfidf_dup"] is not None else ""))
    print(f"  Length OK:        OLD {r['old_len_pct']:.1f}%  W {r['new_w_len_pct']:.1f}%"
          + (f"  TF-IDF {r['tfidf_len_pct']:.1f}%" if r["tfidf_len_pct"] is not None else ""))
    print(f"  Avg kw/dim:       OLD {r['old_avg_kw']:.2f}  W {r['new_w_avg_kw']:.2f}"
          + (f"  TF-IDF {r['tfidf_avg_kw']:.2f}" if r["tfidf_avg_kw"] is not None else ""))
    print()


# =========================================================================
#  Main
# =========================================================================

def do_test(name, dims, doc_text, trans_text, with_transcript, has_tfidf):
    """Run one test fixture and print results."""
    r = run_comparison(name, dims, doc_text, trans_text, with_transcript)
    print_table(r["details"], r["name"], has_tfidf)
    print_summary(r)
    return r


def main():
    print("=" * 140)
    print("  EVIDENCE QUALITY COMPARISON")
    print("  OLD:   first-keyword-first-sentence match")
    print("  NEW-W: weighted scoring (kw_density 0.35 + focus 0.40 + position 0.15 - exhaust 0.10)")
    if HAS_SKLEARN:
        print("  TF-IDF: 0.7 TF-IDF cosine similarity + 0.3 keyword density fusion")
    print("=" * 140)

    has_tfidf = HAS_SKLEARN
    all_results = []

    # --- Test 1: 温故知新 ---
    print("\n>>> Test 1: 温故知新 (built-in sample data)")
    dims_wg = get_dimensions("温故知新")
    r = do_test("温故知新", dims_wg, SAMPLE_DOCUMENT_TEXT, SAMPLE_TRANSCRIPT_TEXT, True, has_tfidf)
    all_results.append(r)

    # --- Test 2: 认知升级 (well-structured) ---
    print("\n>>> Test 2: 认知升级 (well-structured)")
    dims_xl1 = get_dimensions("行动学习-认知升级")
    r = do_test("行动学习-认知升级", dims_xl1, DOC1, TRANS1, True, has_tfidf)
    all_results.append(r)

    # --- Test 3: 组织协同 (moderate) ---
    print("\n>>> Test 3: 组织协同 (moderate quality)")
    dims_xl2 = get_dimensions("行动学习-组织协同")
    r = do_test("行动学习-组织协同", dims_xl2, DOC2, TRANS2, True, has_tfidf)
    all_results.append(r)

    # --- Test 4: 问题解决 (mixed quality) ---
    print("\n>>> Test 4: 问题解决 (mixed quality)")
    dims_xl3 = get_dimensions("行动学习-问题解决")
    r = do_test("行动学习-问题解决", dims_xl3, DOC3, TRANS3, True, has_tfidf)
    all_results.append(r)

    # --- Test 5: No transcript ---
    print("\n>>> Test 5: 问题解决 (no transcript -- document only)")
    r = do_test("问题解决（无录音）", dims_xl3, DOC3, "", False, has_tfidf)
    all_results.append(r)

    # =====================================================================
    #  Overall aggregate
    # =====================================================================
    print("=" * 140)
    print("  OVERALL AGGREGATE (" + str(len(all_results)) + " fixtures)")
    print("=" * 140)

    count = len(all_results)
    total_dims = sum(len(r["details"]) for r in all_results)

    # Relevance averages
    avg_old_rel = sum(r["old_avg_relevance"] for r in all_results) / count
    avg_w_rel = sum(r["new_w_avg_relevance"] for r in all_results) / count
    w_overall_pct = ((avg_w_rel - avg_old_rel) / max(avg_old_rel, 0.001)) * 100

    tfidf_results = [r for r in all_results if r["tfidf_avg_relevance"] is not None]
    if tfidf_results:
        avg_tfidf_rel = sum(r["tfidf_avg_relevance"] for r in tfidf_results) / len(tfidf_results)
        tfidf_overall_pct = ((avg_tfidf_rel - avg_old_rel) / max(avg_old_rel, 0.001)) * 100
    else:
        avg_tfidf_rel = None

    # Dimensional change
    total_w_imp = sum(r["w_improved"] for r in all_results)
    total_w_same = sum(r["w_same"] for r in all_results)
    total_w_reg = sum(r["w_regressed"] for r in all_results)

    # Diversity
    avg_old_div = sum(r["old_diversity"] for r in all_results) / count
    avg_w_div = sum(r["new_w_diversity"] for r in all_results) / count
    avg_t_div = sum(r.get("tfidf_diversity", 0) or 0 for r in all_results) / count if tfidf_results else None

    # Duplicates
    total_old_dup = sum(r["old_dup"] for r in all_results)
    total_w_dup = sum(r["new_w_dup"] for r in all_results)
    total_t_dup = sum(r.get("tfidf_dup", 0) or 0 for r in all_results) if tfidf_results else None

    # Length
    avg_old_len = sum(r["old_len_pct"] for r in all_results) / count
    avg_w_len = sum(r["new_w_len_pct"] for r in all_results) / count
    avg_t_len = sum(r.get("tfidf_len_pct", 0) or 0 for r in all_results) / count if tfidf_results else None

    # Keywords
    avg_old_kw = sum(r["old_avg_kw"] for r in all_results) / count
    avg_w_kw = sum(r["new_w_avg_kw"] for r in all_results) / count
    avg_t_kw = sum(r.get("tfidf_avg_kw", 0) or 0 for r in all_results) / count if tfidf_results else None

    print()
    print(f"  Fixtures compared:        {count}")
    print(f"  Total dimensions:         {total_dims}")
    print()
    print(f"  AVERAGE RELEVANCE (0-3):")
    print(f"    Old (keyword-first):     {avg_old_rel:.3f}/3")
    print(f"    New-W (weighted):        {avg_w_rel:.3f}/3  ({w_overall_pct:+.1f}%)")
    if avg_tfidf_rel is not None:
        print(f"    TF-IDF (semantic):       {avg_tfidf_rel:.3f}/3  ({tfidf_overall_pct:+.1f}%)")
    print()
    print(f"  DIMENSIONAL CHANGE (weighted):")
    print(f"    Improved:  {total_w_imp}/{total_dims} ({100*total_w_imp/total_dims:.1f}%)")
    print(f"    Unchanged: {total_w_same}/{total_dims} ({100*total_w_same/total_dims:.1f}%)")
    print(f"    Regressed: {total_w_reg}/{total_dims} ({100*total_w_reg/total_dims:.1f}%)")
    print()
    print(f"  EVIDENCE DIVERSITY:")
    print(f"    Old:   {avg_old_div:.3f}")
    print(f"    New-W: {avg_w_div:.3f}")
    if avg_t_div is not None:
        print(f"    TF-IDF: {avg_t_div:.3f}")
    print()
    print(f"  DUPLICATE EVIDENCE (total instances):")
    print(f"    Old:   {total_old_dup}")
    print(f"    New-W: {total_w_dup}")
    if total_t_dup is not None:
        print(f"    TF-IDF: {total_t_dup}")
    print()
    print(f"  LENGTH REASONABLENESS (20-80 chars):")
    print(f"    Old:   {avg_old_len:.1f}%")
    print(f"    New-W: {avg_w_len:.1f}%")
    if avg_t_len is not None:
        print(f"    TF-IDF: {avg_t_len:.1f}%")
    print()
    print(f"  AVG KEYWORDS PER DIMENSION:")
    print(f"    Old:   {avg_old_kw:.2f}")
    print(f"    New-W: {avg_w_kw:.2f}")
    if avg_t_kw is not None:
        print(f"    TF-IDF: {avg_t_kw:.2f}")
    print()

    # Verdict
    verdict_parts = []
    if avg_w_rel >= avg_old_rel:
        verdict_parts.append("Weighted scoring: PASS (>= old system)")
    else:
        verdict_parts.append("Weighted scoring: MINOR regression (-{:.1f}%)".format(abs(w_overall_pct)))

    if avg_tfidf_rel is not None:
        if avg_tfidf_rel >= avg_old_rel:
            verdict_parts.append("TF-IDF: PASS (>= old system)")
        else:
            verdict_parts.append("TF-IDF: regression")

    if total_w_dup <= total_old_dup:
        verdict_parts.append("Deduplication: IMPROVED")
    else:
        verdict_parts.append("Deduplication: REGRESSED")

    if total_w_dup < total_old_dup or avg_w_div >= avg_old_div:
        verdict_parts.append("Diversity: IMPROVED")
    else:
        verdict_parts.append("Diversity: REGRESSED")

    print("  VERDICT:")
    for v in verdict_parts:
        print(f"    - {v}")
    print("=" * 140)

    return all_results


if __name__ == "__main__":
    results = main()
