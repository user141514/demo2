from collections import OrderedDict


def build_markdown(result):
    groups = OrderedDict()
    for dimension in result["dimensions"]:
        groups.setdefault(dimension["group_name"], []).append(dimension)

    lines = [
        "# 汇报评分报告",
        "",
        "## 被评价人信息",
        "",
        "| 字段 | 内容 |",
        "|------|------|",
        "| 姓名 | {} |".format(result["name"]),
        "| 所属组织/部门 | {} |".format(result["org"]),
        "| 汇报类型 | {} |".format(result["report_type"]),
        "| 评分日期 | {} |".format(result["date"]),
        "| 备注 | {} |".format(result["note"] or "--"),
        "",
        "---",
        "",
        "## 总分",
        "",
        "**{} 分**（满分100分）".format(result["total_score"]),
        "",
        "## 总评",
        "",
        result["overall_comment"],
        "",
        "---",
        "",
        "## 各维度评分明细",
        "",
    ]

    for group_name, dimensions in groups.items():
        lines.append(
            "### 一级维度：{}（权重{}%）".format(group_name, dimensions[0]["group_weight"])
        )
        lines.append("")
        for dimension in dimensions:
            score_label = (
                "{} 分 · {}".format(dimension["score"], dimension["level_label"])
                if dimension["score"] is not None
                else "待补充"
            )
            lines.extend(
                [
                    "#### {}  {}".format(dimension["name"], score_label),
                    "",
                    "**评分依据：** {}".format(dimension["evidence"] or "--"),
                    "",
                    "**维度评价：** {}".format(dimension["comment"] or "--"),
                    "",
                ]
            )

    lines.extend(["---", "", "## 结论与建议", "", "### 优势亮点", ""])
    for item in result["strengths"]:
        lines.append("- {}".format(item))
    lines.extend(["", "### 改进方向", ""])
    for item in result["improvements"]:
        lines.append("- {}".format(item))

    lines.extend(
        [
            "",
            "---",
            "",
            "*{}*".format(result["disclaimer"]),
            "",
            "*生成时间：{}*".format(result["created_at"]),
            "",
        ]
    )
    return "\n".join(lines)
