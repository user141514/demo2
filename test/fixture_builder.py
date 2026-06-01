from pathlib import Path

from scoring_app.pdf_export import build_pdf_bytes
from scoring_app.rules import REPORT_DEFINITIONS


FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures"
INPUT_ROOT = FIXTURE_ROOT / "input"
OUTPUT_ROOT = FIXTURE_ROOT / "output"


def get_report_type_by_definition_id(definition_id):
    for report_type, definition in REPORT_DEFINITIONS.items():
        if definition["id"] == definition_id:
            return report_type
    raise AssertionError("Missing report definition id: {}".format(definition_id))


def build_sample_document_text():
    return "\n".join(
        [
            "温故知新个人汇报样例材料",
            "本次复盘围绕年度战略目标、组织痛点、关键任务推进与结果改善展开。",
            "我先说明业务背景，再展示问题分析、行动步骤、协同节点与阶段成效。",
            "课题立项部分聚焦组织效率、关键指标提升与资源规划安排。",
            "行动结果包括流程时长下降18%，跨团队协同效率提升22%，客户满意度提升9%。",
            "复盘部分同时补充不足、改进路径、后续迭代节奏与里程碑安排。",
            "汇报材料强调目标、规划、行动、结果、反思、创新与突破。",
        ]
    )


def build_sample_transcript_text():
    return "\n".join(
        [
            "大家好，我将按背景、问题、行动、结果四个部分完成汇报。",
            "首先解释为什么这个课题与当前组织战略直接相关，其次说明资源和推进计划。",
            "然后展示关键动作、执行节点、协同方式以及阶段结果。",
            "最后总结亮点、不足和下一步改进安排，整体控制在八分钟内。",
        ]
    )


def build_text_pdf_bytes(text):
    lines = [line.strip() for line in str(text).splitlines() if line.strip()]
    if not lines:
        lines = ["Sample PDF"]

    content_lines = ["BT", "/F1 12 Tf", "50 760 Td"]
    first = True
    for line in lines:
        escaped = _escape_pdf_literal(line)
        if not first:
            content_lines.append("0 -18 Td")
        content_lines.append("({}) Tj".format(escaped))
        first = False
    content_lines.append("ET")
    content_stream = "\n".join(content_lines).encode("utf-8")

    objects = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n",
        b"4 0 obj\n<< /Length "
        + str(len(content_stream)).encode("ascii")
        + b" >>\nstream\n"
        + content_stream
        + b"\nendstream\nendobj\n",
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
    ]

    payload = bytearray()
    payload.extend(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(payload))
        payload.extend(obj)

    startxref = len(payload)
    payload.extend(b"xref\n0 6\n")
    payload.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        payload.extend("{:010d} 00000 n \n".format(offset).encode("ascii"))
    payload.extend(b"trailer\n<< /Size 6 /Root 1 0 R >>\n")
    payload.extend(b"startxref\n")
    payload.extend(str(startxref).encode("ascii"))
    payload.extend(b"\n%%EOF\n")
    return bytes(payload)


def build_sample_score_result(user_id="fixture-user", score_id="fixture-score-001"):
    report_type = get_report_type_by_definition_id("wg")
    definition = REPORT_DEFINITIONS[report_type]
    dimensions = definition["dimensions"]
    selected = [dimensions[0], dimensions[2], dimensions[4]]
    scores = [8.8, 8.6, 8.0]
    evidence = [
        "材料中说明了目标、行动与结果之间的链路。",
        "文档说明课题围绕业务痛点提出价值主张，并体现优化创新思路。",
        "转写中对汇报顺序、重点和总结表达较为清楚。",
    ]
    comments = [
        "该维度支撑较强，能够说明战略价值与任务连接。",
        "该维度能够说明课题价值与创新方向，建议继续补充可验证收益。",
        "该维度表达顺畅，但仍可补充更多逻辑链条细节。",
    ]

    return {
        "score_id": score_id,
        "user_id": user_id,
        "name": "王晓晨",
        "org": "培训交付中心",
        "report_type": report_type,
        "date": "2026-05-25",
        "note": "真实样例测试数据",
        "pdf_filename": "real_submission_report.pdf",
        "upload_path": "uploads/real_submission_report.pdf",
        "document_preview": build_sample_document_text()[:800],
        "transcript_present": True,
        "total_score": 85.1,
        "total_level": "优秀",
        "doc_average": 8.7,
        "audio_average": 8.0,
        "lowest_dimension": {"name": selected[-1]["name"], "score": scores[-1]},
        "overall_comment": "整体表现稳健，文档结构完整，汇报逻辑清晰，建议继续补强低分维度的链条细节。",
        "strengths": [
            "战略链接与价值认知表现较强。",
            "知识融合与框架应用较为完整。",
            "整体材料对关键行动和结果支撑充分。",
        ],
        "improvements": [
            "逻辑的严谨性和链条完整性仍可继续补充。",
            "可进一步强化案例证据与量化结果的对应关系。",
        ],
        "disclaimer": "本报告由 AI 智能体自动生成，仅供参考，最终评定以培训导师意见为准。",
        "created_at": "2026-05-25T10:00:00Z",
        "dimensions": [
            {
                "id": dimension["id"],
                "name": dimension["name"],
                "group_name": dimension["group"],
                "group_weight": dimension["group_weight"],
                "actual_weight": dimension["actual_weight"],
                "material_source": dimension["material_source"],
                "score": score,
                "level_label": "优秀",
                "evidence": evidence[index],
                "comment": comments[index],
            }
            for index, (dimension, score) in enumerate(zip(selected, scores))
        ],
    }


def ensure_fixture_directories():
    INPUT_ROOT.mkdir(parents=True, exist_ok=True)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)


def write_real_fixture_files(markdown_builder):
    ensure_fixture_directories()

    document_text = build_sample_document_text()
    transcript_text = build_sample_transcript_text()
    score_result = build_sample_score_result()

    (INPUT_ROOT / "real_submission_report.pdf").write_bytes(build_text_pdf_bytes(document_text))
    (INPUT_ROOT / "real_submission_transcript.txt").write_text(transcript_text, encoding="utf-8")
    (OUTPUT_ROOT / "real_scored_report.md").write_text(
        markdown_builder(score_result), encoding="utf-8"
    )
    (OUTPUT_ROOT / "real_scored_report.pdf").write_bytes(build_pdf_bytes(score_result))
    (OUTPUT_ROOT / "real_scored_report.json").write_text(
        _json_dump(score_result), encoding="utf-8"
    )


def _escape_pdf_literal(value):
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _json_dump(payload):
    import json

    return json.dumps(payload, ensure_ascii=False, indent=2)
