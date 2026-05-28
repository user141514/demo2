import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

os.environ["SCORING_APP_KEY_FILE"] = str(Path("missing-test-key.py").resolve())
os.environ["SCORING_LLM_MODE"] = "mock"

from scoring_app import create_app
from test.fixture_builder import build_text_pdf_bytes


ROOT = Path("test/fixtures/manual_flow")
INPUT_ROOT = ROOT / "input"
OUTPUT_ROOT = ROOT / "output"


SAMPLES = [
    {
        "slug": "01_cognitive_upgrade",
        "name": "李明-认知升级样例",
        "org": "战略发展部",
        "report_type": "行动学习",
        "course_session": "第一次课 · 管理认知",
        "document": "\n".join(
            [
                "行动学习第一次课程认知升级汇报样例。",
                "我当前负责战略项目推进，现状是能完成任务拆解，但对外部趋势、个人能力短板和组织第三次创业之间的连接还不够系统。",
                "直面问题部分，我结合商业综合推理、管理技能、管理个性、管理风格、职业锚和组织忠诚度测评，识别出三个核心瓶颈：战略判断依赖经验、跨部门影响力不足、复盘反馈闭环不稳定。",
                "环境评估部分，我用PEST分析和行业趋势判断，发现新能源、海外合规、智能制造会改变岗位能力要求，机会面是数据化管理能力提升，风险面是原有经验失效。",
                "创新构想部分，我把ASTRAL领导力模型和IDP方案结合，计划用AI辅助学习、轮岗、项目历练和导师辅导，形成从我的世界到我们的世界的转变。",
                "结构性方法部分，我按照IDP七步法展开：自我评估、环境评估、职业选择、确定目标、行动计划、行动实施、评估反馈，并用现状、目标、能力、计划四模块组织材料。",
                "可操作性部分，我设定1年完成数据分析能力补强，2年主导跨部门战略项目，3年承担业务单元战略协同角色；每月产出一份复盘报告，责任人为本人和导师，交付物包括能力地图、项目里程碑和反馈记录。",
                "资源需求包括导师辅导、轮岗机会、AI工具订阅和项目实践名额，评价方式包括测评复测、行为记录、项目成果和上级反馈。",
            ]
        ),
        "transcript": "\n".join(
            [
                "各位老师好，我本次汇报按自我认知、外部环境、职业目标、能力发展、行动计划和评估反馈展开。",
                "我先说明测评结果暴露出的能力短板，再说明PEST趋势对岗位的影响。",
                "我的核心目标不是单纯提升个人能力，而是把个人IDP和中集车辆第三次创业的组织需求连接起来。",
                "最后我用三分钟说明一年、两年、三年的里程碑，并回答导师关于资源和风险的问题。整体控制在十五分钟以内。",
            ]
        ),
    },
    {
        "slug": "02_org_collaboration",
        "name": "王敏-组织协同样例",
        "org": "财务共享中心",
        "report_type": "行动学习",
        "course_session": "第二次课 · 组织协同",
        "document": "\n".join(
            [
                "行动学习第二次课程组织协同汇报样例。",
                "案例背景是管报与法报数据在月结第三天经常出现口径差异，导致业务部门反复解释，财务BP和经营分析团队互相等待。",
                "直面问题部分，我没有把原因归为人的责任心不足，而是用七大协同障碍根源分析：组织分工不明确、目标差异、部门墙、沟通技能缺失、横向沟通机制不健全和缺乏协作文化。",
                "根源剖析显示，RACI矩阵里数据口径确认人缺失，流程中没有同步节点，指标目标只考核本部门准时率，没有共同目标。",
                "创新构想部分，我设计服务协同、指导协同、管控协同和情感协同四类机制：建立统一数据字典，设置双计双考机制，引入跨部门满意度互评，并建立问题升级机制。",
                "结构性方法部分，我按聚焦、共创、对齐、闭环四步法确定共同目标，围绕组织、流程、目标、机制、氛围和影响力六个维度设计方案。",
                "可操作性部分，短期1到2周内完成数据字段清单、责任人、同步时间节点和校验模板；中期1到3个月内上线月结协同看板，明确里程碑、风险应对和资源配置。",
                "预期成果是月结差异项减少30%，重复沟通时间降低20%，争议问题在24小时内完成升级处理。",
            ]
        ),
        "transcript": "\n".join(
            [
                "今天我汇报一个跨部门协同案例，顺序是案例背景、根源剖析、解决方案、推进计划、预期成果和反思。",
                "评委问到为什么不是人的问题，我回答这是流程、机制和共同目标缺失造成的系统问题。",
                "我会先做RACI责任矩阵，再推动数据字典和双计双考，最后用满意度互评形成反馈闭环。",
                "本次汇报控制在十五分钟，答辩部分重点回应风险和资源投入。",
            ]
        ),
    },
    {
        "slug": "03_problem_solving",
        "name": "赵强-问题解决样例",
        "org": "制造运营部",
        "report_type": "行动学习",
        "course_session": "第三次课 · 问题解决",
        "document": "\n".join(
            [
                "行动学习第三次课程问题解决能力提升汇报样例。",
                "案例背景是某产线换型后首周返工率从2.5%上升到6.8%，交付周期延长两天，客户投诉风险升高。",
                "直面问题部分，我用根源拆解三层模型分析：现象层是返工率和交付周期异常，流程层是首件确认和异常升级节点缺失，系统层是数据看板滞后、SOP培训不一致和授权机制不清。",
                "我同时识别风险面和机会面：风险是质量损失和客户信任下降，机会是建立可复用的换型问题解决机制。",
                "结构性方法部分，我按照六步框架发现、分析、目标、方案、执行、评估展开，并根据执行偏差类问题选择5Why、5W2H、SOP体系搭建和数据运营闭环。",
                "创新构想部分，我引入AI辅助工具对异常记录做聚类，把经验复用和快速适配结合，形成换型风险清单和班组训练脚本。",
                "可操作性部分，第一周完成数据复盘和首件确认SOP更新，第二周完成分层培训，第三到第四周上线日清看板；责任人为生产主管、质量工程师和班组长，交付物包括SOP、培训记录、看板和复盘报告。",
                "评估指标包括返工率降到3%以内、异常响应不超过30分钟、换型后首周一次交检通过率提升到96%。",
            ]
        ),
        "transcript": "\n".join(
            [
                "我的汇报按背景、问题、分析、方案、计划和总结展开。",
                "我先界定问题边界，再用现象层、流程层、系统层定位根因。",
                "针对评委关于AI工具是否可行的问题，我说明AI只做异常聚类和知识沉淀，最终决策仍由生产和质量负责人确认。",
                "整个方案有试点验证、动态调整和全面推广三个阶段，答辩用五分钟回应风险。",
            ]
        ),
    },
]


def main():
    INPUT_ROOT.mkdir(parents=True, exist_ok=True)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    runtime = Path(tempfile.mkdtemp(prefix="manual-flow-runtime-"))
    try:
        os.environ["SCORING_APP_DATA_DIR"] = str(runtime / "data")
        os.environ["SCORING_APP_UPLOAD_DIR"] = str(runtime / "uploads")
        os.environ["SCORING_APP_DB_PATH"] = str(runtime / "data" / "scores.db")
        os.environ["SCORING_LLM_MODE"] = "mock"

        app = create_app()
        app.testing = True
        client = app.test_client()
        register = client.post(
            "/api/auth/register",
            json={
                "email": "manual-flow@example.com",
                "display_name": "Manual Flow",
                "password": "Passw0rd!",
            },
        )
        if register.status_code != 201:
            raise RuntimeError(register.get_data(as_text=True))

        summary = []
        for sample in SAMPLES:
            summary.append(run_sample(client, sample))

        history = client.get("/api/scores")
        if history.status_code != 200:
            raise RuntimeError(history.get_data(as_text=True))

        payload = {"history_count": len(history.get_json().get("items", [])), "summary": summary}
        (OUTPUT_ROOT / "manual_flow_summary.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    finally:
        shutil.rmtree(runtime, ignore_errors=True)


def run_sample(client, sample):
    pdf_path = INPUT_ROOT / "{}.pdf".format(sample["slug"])
    txt_path = INPUT_ROOT / "{}_transcript.txt".format(sample["slug"])
    pdf_path.write_bytes(build_text_pdf_bytes(sample["document"]))
    txt_path.write_text(sample["transcript"], encoding="utf-8")

    with pdf_path.open("rb") as pdf_file, txt_path.open("rb") as transcript_file:
        response = client.post(
            "/api/score",
            data={
                "name": sample["name"],
                "org": sample["org"],
                "report_type": sample["report_type"],
                "course_session": sample["course_session"],
                "date": "2026-05-28",
                "note": "手写样例冒烟验证：{}".format(sample["slug"]),
                "transcript": "",
                "pdf_file": (pdf_file, pdf_path.name),
                "transcript_file": (transcript_file, txt_path.name),
            },
            content_type="multipart/form-data",
        )
    if response.status_code != 200:
        raise RuntimeError(
            "{} submit failed: {} {}".format(
                sample["slug"], response.status_code, response.get_data(as_text=True)
            )
        )

    result = response.get_json()
    score_id = result["score_id"]
    detail = client.get("/api/scores/{}".format(score_id))
    if detail.status_code != 200:
        raise RuntimeError(detail.get_data(as_text=True))

    md_response = client.get("/api/scores/{}/export?format=md".format(score_id))
    if md_response.status_code != 200:
        raise RuntimeError(md_response.get_data(as_text=True))
    md_path = OUTPUT_ROOT / "{}_report.md".format(sample["slug"])
    md_path.write_bytes(md_response.get_data())

    pdf_response = client.get("/api/scores/{}/export?format=pdf".format(score_id))
    if pdf_response.status_code != 200:
        raise RuntimeError(pdf_response.get_data(as_text=True))
    pdf_bytes = pdf_response.get_data()
    if not pdf_bytes.startswith(b"%PDF"):
        raise RuntimeError("{} export is not a PDF".format(sample["slug"]))
    export_pdf_path = OUTPUT_ROOT / "{}_report.pdf".format(sample["slug"])
    export_pdf_path.write_bytes(pdf_bytes)

    result_path = OUTPUT_ROOT / "{}_result.json".format(sample["slug"])
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    lowest = result.get("lowest_dimension") or {}
    return {
        "slug": sample["slug"],
        "score_id": score_id,
        "report_type": result.get("report_type"),
        "course_session": result.get("course_session"),
        "total_score": result.get("total_score"),
        "total_level": result.get("total_level"),
        "doc_average": result.get("doc_average"),
        "audio_average": result.get("audio_average"),
        "lowest_dimension": {
            "name": lowest.get("name"),
            "score": lowest.get("score"),
        },
        "exports": {
            "json": str(result_path),
            "markdown": str(md_path),
            "pdf": str(export_pdf_path),
        },
    }


if __name__ == "__main__":
    main()
