import json


STAGE_NAMES = {
    "context": "M01 建模背景摘要",
    "dimensions": "M02 维度卡片",
    "descriptions": "M03 维度定位描述",
    "anchors": "M04 行为锚定",
}


def build_stage_prompt(stage, model_data):
    stage_name = STAGE_NAMES.get(stage, stage)
    payload = json.dumps(model_data or {}, ensure_ascii=False, indent=2)
    return """你是领导力建模顾问，请根据用户材料完成 {stage_name}。

全局规则：
1. 本次建模只服务一个单一层级/群体，不生成多层级矩阵。
2. M02 必须生成 4-8 个领导力维度，每个维度包含 name、definition、sources、priority。
3. 每个维度必须展示来源依据，来源可以是战略关键词、标准库参照或用户访谈归纳。
4. M03 的维度定位描述必须说明核心要求、行为侧重点、价值贡献，并给出质检状态。
5. M04 的行为锚定必须包含正向行为优秀水平、正向行为达标水平、负向行为不达标表现。
6. 行为描述必须以行为动词开头，可观察、可衡量，不使用空泛口号。
7. 如果材料缺少行业、战略、痛点、优秀管理者画像或文档证据，要直接指出缺失项，不得虚构。
8. 只输出 JSON，不输出 Markdown。

当前模型数据：
{payload}
""".format(
        stage_name=stage_name,
        payload=payload,
    )
