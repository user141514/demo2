# 评分证据生成方案重新设计

**日期**: 2026-05-29  
**版本**: v1.0  
**状态**: 设计稿  

---

## 一、设计目标与约束

### 目标
1. **证据与维度语义匹配**: evidence 必须反映维度的核心评估意图，而非关键词偶然命中
2. **API 契约完全兼容**: `score_service.py::create_score_from_submission()` 的无感知替换
3. **向后兼容**: 现有历史评分数据不受影响，result 结构不变
4. **可证伪**: 每个 evidence 必须可追溯至原文

### 环境约束
| 约束 | 说明 |
|------|------|
| 平台 | Windows Server 2019+ |
| 数据库 | SQLite (无向量扩展) |
| LLM API | OpenAI 兼容 (当前为 DeepSeek), 无嵌入 API 保障 |
| 包管理 | pip, 无 Conda 环境 |
| 延迟要求 | 整个评分 ≤ 30s (含 LLM 调用) |

---

## 二、方案 A: 加权句子评分 (Weighted Sentence Scoring)

### 核心理念

用 **多维评分函数** 替代当前的第一匹配策略。每个候选句子被综合评分，最高分者当选 evidence。

### 评分公式

```
score(sentence, dimension) =
    α × keyword_density(sentence, dimension.keywords)
    + β × focus_alignment(sentence, dimension.name, dimension.focus)
    + γ × position_quality(sentence, text_structure)
    + δ × exhaustivity_penalty(sentence, already_quoted)
```

各分量说明:

| 分量 | 权重 (建议) | 计算方式 |
|------|------------|---------|
| `keyword_density` | α = 0.35 | 句子中命中的维度关键词数 / 句子总关键词数 × 归一化 |
| `focus_alignment` | β = 0.40 | 句子是否包含维度 `focus` 字段的词(如"问题穿透深度")或 `name` 中的核心词; 匹配加权 |
| `position_quality` | γ = 0.15 | 句子在段落中的位置: 首句/尾句加分; 独句段落加分 |
| `exhaustivity_penalty` | δ = -0.10 | 与其他维度的 evidence 句子重复时扣分, 鼓励多样性 |

### 实现变更

**仅修改**: `scoring_app/scoring.py` 中的 `_build_evidence()` 函数

```python
def _build_evidence(text, dimension):
    """Select best evidence sentence using weighted scoring."""
    sentences = _split_sentences(text)
    candidates = []

    for idx, sentence in enumerate(sentences):
        if looks_like_garbled_text(sentence):
            continue

        kw_density = _calc_keyword_density(sentence, dimension["keywords"])
        focus_score = _calc_focus_alignment(
            sentence, dimension["name"], dimension["focus"]
        )
        pos_score = _calc_position_bonus(idx, len(sentences))

        total = (
            0.35 * kw_density
            + 0.40 * focus_score
            + 0.15 * pos_score
        )
        candidates.append((total, sentence))

    if not candidates:
        return "文档文本提取质量不足，未找到可直接引用的有效证据。"

    candidates.sort(key=lambda x: x[0], reverse=True)
    return _limit(candidates[0][1], 80)
```

需新增辅助函数至 `scoring.py`:

- `_calc_keyword_density(text, keywords)`: 计算关键词在句子中的命中密度，含中文分词粗略替代（ngram 滑动窗口）
- `_calc_focus_alignment(text, dim_name, dim_focus)`: 使用维度的 `name` 和 `focus` 构建扩展匹配集（含近义预定义列表）
- `_calc_position_bonus(idx, total)`: 段落首尾句加分 (使用分段符号识别)

### 对 LLM 路径的补充

在 `live_scoring.py` 的 `_normalize_dimensions()` 中增加验证步骤:

```python
def _validate_evidence(evidence_text, source_text):
    """Verify LLM-generated evidence can be found in source text."""
    if not evidence_text or len(evidence_text) < 5:
        return False
    # 按子串匹配或模糊匹配
    evidence_clean = evidence_text.strip("…。，")
    return evidence_clean in source_text
```

如果验证失败，回退到 heuristic 路径的 `_build_evidence()` 作为兜底。

### 评估

| 维度 | 评价 |
|------|------|
| **证据质量** | 显著提升 — 从随机命中变为综合排序。消除"第一句凑巧含关键词"的问题 |
| **实现复杂度** | 低 — 仅修改一个函数 + 新增 3 个辅助函数, 约 60 行 Python |
| **性能影响** | 极小 — 纯字符串运算, 10 个维度 × 500 句 ≈ 0.02s |
| **向后兼容** | 完全兼容 — result JSON 结构不变 |
| **依赖新增** | 无 |
| **LLM 成本** | 无新增 |
| **局限性** | 仍基于关键词, 无法理解"问题穿透深度"等抽象概念; 需要人工调参 |

---

## 三、方案 B: TF-IDF 语义重排序 (Semantic Reranking)

### 核心理念

使用 **TF-IDF 向量化 + 余弦相似度** 计算句子与维度的语义相关性，从 Top-10 候选中选择与维度命中最相关的一批。

### 架构

```
维度定义文本 ──→ TF-IDF 向量 ──→ 维度向量 (query)
                                        ↓
文档句子列表 ──→ TF-IDF 向量 ──→ 候选向量矩阵
                                        ↓
                            余弦相似度计算 → 按相似度排序 → Top-3
                                                          ↓
                                            关键词密度加权 → 最终选择
```

### 设计细节

**语料构建** (一次性的, 启动时加载):

1. **维度语料**: 每个维度用其 `name` + `focus` + `keywords` 连接字符串，加上课程知识库中的该维度的 "重点关注" 指导文本
2. **文档语料** (每次评分动态构建): 文档的分句结果

**TF-IDF 配置**:
- 使用 `sklearn.feature_extraction.text.TfidfVectorizer`
- `analyzer='char_wb'` (character n-gram, 适合中文)
- `ngram_range=(2, 4)` — 2-4 个字的 ngram 对中文语义有较好捕获
- `max_features=5000`

**融合策略** (防止纯语义漂移):
```
final_score(sentence) = 0.7 × tfidf_similarity + 0.3 × keyword_density
```

### 实现变更

**新增模块**: `scoring_app/evidence_ranker.py`

```python
class EvidenceRanker:
    def __init__(self, definitions):
        # Build corpus from dimension definitions + knowledge base
        self._build_tfidf(definitions)

    def rank_sentences(self, sentences, dimension_id):
        # Vectorize sentences, compute similarity with dimension vector
        # Return top-3 with combined scores
        ...

    def best_evidence(self, text, dimension):
        sentences = _split_sentences(text)
        candidates = self.rank_sentences(sentences, dimension["id"])
        if candidates:
            return _limit(candidates[0]["sentence"], 80)
        return "文档文本提取质量不足，未找到可直接引用的有效证据。"
```

**修改**: `scoring.py` 中的 `_build_evidence()` 改为调用 `evidence_ranker`

```python
# 模块级别初始化 (惰性)
_ranker = None

def _get_ranker(definition):
    global _ranker
    if _ranker is None and definition:
        _ranker = EvidenceRanker(definition)
    return _ranker

def _build_evidence(text, keywords, dimension=None, definition=None):
    if dimension and definition:
        ranker = _get_ranker(definition)
        if ranker:
            return ranker.best_evidence(text, dimension)
    # Fallback to current logic
    ...
```

### 评估

| 维度 | 评价 |
|------|------|
| **证据质量** | 高 — TF-IDF 能在语义层面判断句子与维度的相关性, 显著优于纯关键词 |
| **实现复杂度** | 中 — 需新增模块 + 依赖 sklearn + jieba (中文), 约 150 行 Python |
| **性能影响** | 低 — TF-IDF 向量化 + 余弦相似度在 500 句 × 10 维度 ≈ 0.1s |
| **向后兼容** | 完全兼容 |
| **依赖新增** | `scikit-learn`, `jieba` |
| **LLM 成本** | 无 |
| **局限性** | TF-IDF 仍为词袋模型, 无法理解否定/反讽; 中文 char-ngram 的语义捕获有限; 需管理向量器持久化 |

---

## 四、方案 C: LLM 引导的证据提取 (LLM-Guided Extraction)

### 核心理念

利用 LLM 的语义理解能力，在现有调用基础上增加证据提取/验证步骤。分为两个子策略:

**C1. 增强 Prompt (LLM 路径)**:
在 `live_scoring.py` 的 prompt 中增加:
- 要求证据必须是原文**逐字引用**（而非 paraphrasing）
- 增加示例对 "好证据 vs 差证据" 的说明
- 要求 LLM 标注证据在原文中的起始位置（行号）

**C2. 批处理证据精炼 (启发式路径)**:
对于 heuristic 路径, 只在置信度低时触发:

```
触发条件: dimension confidence == "low"
  ↓
收集 Top-5 候选句子 (用方案 A 的加权评分)
  ↓
一次 LLM 批调用 (batch request): 
  "对以下每个维度，从候选句子中选择最能支持该维度评分的一段"
  ↓
解析 LLM 输出的选择 → 作为 evidence
```

### 实现变更

**LLM 路径变更** (`live_scoring.py`):

```python
def _build_user_prompt(...):
    # 在现有 prompt 尾部增加:
    evidence_guidance = """
证据要求:
- 必须是文档中**逐字存在**的原句, 不能 paraphrase
- 必须直接体现"{focus}"这个核心
- 优先选择包含多个关键词的完整陈述句
- 如果证据不足, 输出 "文档中未找到充分证据"
"""
    return prompt + evidence_guidance
```

**启发式路径变更** (`scoring.py`):

```python
def _refine_evidence_via_llm(dimension_results, sentences, definition, document_text):
    """Batch LLM call to refine evidence for low-confidence dimensions."""
    low_conf_dims = [d for d in dimension_results if d.get("confidence") == "low"]
    if not low_conf_dims:
        return dimension_results

    prompt = _build_refine_prompt(low_conf_dims, sentences, definition)
    response = llm_call(prompt)  # light model, fast
    # Parse and update evidence
    ...
```

### 评估

| 维度 | 评价 |
|------|------|
| **证据质量** | 最高 — LLM 能理解维度语义和上下文 |
| **实现复杂度** | 中-高 — 需管理 LLM 调用、prompt 模板、回退策略 |
| **性能影响** | 中 — 批处理调用增加 5-15s 延迟 (视 API 响应时间) |
| **向后兼容** | 完全兼容 |
| **依赖新增** | 无 (复用现有 LLM 基础设施) |
| **LLM 成本** | 有 — 每次低置信度评分增加 1 次 LLM 调用, token 约 2K-5K |
| **局限性** | 依赖外部 API 可用性; 对于纯启发式路径引入了 LLM 依赖 |

---

## 五、方案对比总表

| 评估维度 | A: 加权评分 | B: TF-IDF 重排序 | C: LLM 引导 |
|---------|:-----------:|:----------------:|:-----------:|
| **证据相关性** | ★★★☆☆ | ★★★★☆ | ★★★★★ |
| **实现复杂度** | ★★★★★ (简单) | ★★★☆☆ (中等) | ★★☆☆☆ (复杂) |
| **性能开销** | ~0.02s | ~0.1s | +5~15s |
| **LLM 成本** | 无 | 无 | 有 |
| **外部依赖** | 无 | sklearn + jieba | 无 |
| **可测试性** | 高 (纯逻辑) | 高 (可 mock 向量器) | 中 (需 mock LLM) |
| **可维护性** | 高 (单个函数) | 中 (独立模块) | 中 (prompt 管理) |
| **适用路径** | Heuristic + LLM | Heuristic + LLM | 主要是 LLM |

---

## 六、推荐方案: A + B 混合策略

### 推荐理由

1. **零新增 API 调用**: 不增加 LLM 调用，避免成本上升和延迟恶化
2. **渐进式增强**: 可分阶段实施，每步可验证、可回滚
3. **环境适配**: sklearn + jieba 在 Windows 上 pip 安装无问题（纯 Python wheels 或预编译 wheels）
4. **中文优化**: char-ngram 特征 + jieba 分词能处理中文语义
5. **证据可追溯**: 所有 evidence 直接来自原文，不是 LLM 生成的 paraphrase

### 分阶段实施计划

```
阶段一 (1-2天)  — 加权句子评分
  实施方案 A 的全部内容
  修改 scoring.py::_build_evidence()
  新增辅助函数
  为 LLM 路径增加 evidence 接地验证
  覆盖测试: 5 个典型文档 × 10 维度 = 50 条 evidence 人工审核
  → 预期: 消除 70% 的"偏门信息"问题

阶段二 (2-3天)  — TF-IDF 语义排序
  新增 evidence_ranker.py 模块
  实现 TF-IDF 向量化 + 余弦相似度
  完成混合评分 (0.7 语义 + 0.3 关键词)
  集成到 scoring.py
  迁移测试: 阶段一的 50 条 evidence 质量对比
  → 预期: 在阶段一基础上再减少 50% 的残余问题

阶段三 (可选)  — LLM 增强
  为低置信度维度增加 LLM 引导精炼
  作为阶段二之上的一层 optional enhancement
  → 预期: 覆盖最后 10-15% 的复杂语义边缘案例
```

### 关键决策点

| 决策 | 建议 | 理由 |
|------|------|------|
| 词向量 or TF-IDF | TF-IDF | 词向量需外部模型, 增加复杂度; TF-IDF 足够好且轻量 |
| jieba 分词 or char-ngram | char-ngram (主) + jieba (备选) | char-ngram 免额外依赖, 对中文关键词语义捕获良好 |
| 置信度计算更新 | 加入 evidence 质量指标 | 避免阶段 1 的问题 5 反复出现 |
| `_build_comment` 更新 | 保持现状 | comment 是模板化评语, 不属于 evidence 质量问题范畴 |

### API 契约验证

以下契约保持不变:

```python
# result JSON
{
    "dimensions": [
        {
            "id": int,
            "score": float,          # 0.0-10.0
            "evidence": str,         # ≤80 字, 直接来自原文
            "comment": str,          # ≤120 字
            "level_label": str,      # 卓越/优秀/良好/合格/不合格
        }
    ]
}
```

全程只有 `_build_evidence()` 和 `_normalize_dimensions()` 的内部逻辑变更, `score_service.py::create_score_from_submission()` 零改动。

---

## 七、风险与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| 中文 char-ngram 语义捕获有限 | 中 | 低 | 保留关键词密度作为辅助特征 (0.3 权重) |
| sklearn 在 Windows 安装失败 | 低 | 中 | 阶段一只用方案 A (纯 Python); 阶段二再用 B |
| 评分延迟增加 | 低 | 低 | TF-IDF 计算 <0.1s, 可忽略 |
| 证据长度导致语义不完整 | 中 | 中 | 按句选取而非截断; 80 字截断逻辑保留作为安全措施 |
