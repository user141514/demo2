import json


STAGE_NAMES = {
    "context": "M01 建模背景摘要",
    "dimensions": "M02 维度卡片",
    "descriptions": "M03 维度定位描述",
    "anchors": "M04 行为锚定",
    "description_regen": "M03 单条描述重写",
    "anchor_regen": "M04 单条行为锚定重写",
}


def build_stage_prompt(stage, model_data):
    stage_name = STAGE_NAMES.get(stage, stage)
    payload = json.dumps(model_data or {}, ensure_ascii=False, indent=2)
    return """你是资深领导力建模顾问，请根据用户材料完成 {stage_name}。

全局规则：
1. 本次建模只服务一个单一层级/群体，不生成多层级矩阵。
2. M01 信息采集必须按行业/规模/战略/痛点/目标层级/优秀管理者画像归纳，信息不足时直接指出缺口。
3. M02 必须生成 4-8 个推荐维度和 5-10 个备选维度；推荐维度优先 4-6 个，最多 8 个。
4. M02 每个维度包含 id、name、definition、sources、priority、rationale；sources 使用 strategy/framework/interview 三类来源。
5. M03 必须为每个确认维度输出 description 和 quality_check，描述聚焦目标层级，长度 50-120 字。
6. M03 禁用空泛词：积极、主动、高度、认真、负责、努力、认可、重视、关注、善于、较强、具备、出色、优秀、良好。
7. M04 必须输出优秀、达标、不达标三档 BARS 行为锚定；字段为 anchors.excellent、anchors.standard、anchors.below。
8. M04 每条行为必须以行为动词开头，可观察、可衡量，避免总是、从不、永远等绝对词。
9. 如果材料缺少行业、战略、痛点、优秀管理者画像或文档证据，要直接指出缺失项，不得虚构。
10. 只输出 JSON，不输出 Markdown。

M02 JSON 结构：
{{"recommended":[{{"id":"D001","name":"2-5字","definition":"2-3句","sources":{{"strategy":"...","framework":"...","interview":"..."}},"priority":"core|important|supplementary","rationale":"1句"}}],"alternatives":[]}}

M03 JSON 结构：
{{"descriptions":[{{"dimension_id":"D001","dimension_name":"维度名称","description":"50-120字","quality_check":{{"passed":true,"issues":[]}}}}]}}

M04 JSON 结构：
{{"anchors":[{{"dimension_id":"D001","dimension_name":"维度名称","anchors":{{"excellent":[{{"id":"D001-E1","text":"...","level":"excellent"}}],"standard":[{{"id":"D001-S1","text":"...","level":"standard"}}],"below":[{{"id":"D001-B1","text":"...","level":"below"}}]}}}}]}}

当前模型数据：
{payload}
""".format(
        stage_name=stage_name,
        payload=payload,
    )
