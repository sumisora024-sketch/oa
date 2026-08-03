import json
import re
from typing import Any

import httpx

from app.core.config import get_settings
from app.models import Employee, Project


PROJECT_EXTRACTION_SCHEMA = {
    "name": "project_metadata",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "client_company": {"type": "string"},
            "project_name": {"type": "string"},
            "description": {"type": "string"},
            "required_skills": {"type": "array", "items": {"type": "string"}},
            "workplace": {"type": "string"},
            "nationality_requirement": {"type": ["string", "null"]},
            "duration": {"type": ["string", "null"]},
            "start_date": {"type": ["string", "null"]},
            "end_date": {"type": ["string", "null"]},
            "headcount": {"type": ["integer", "null"]},
            "unit_price": {"type": ["string", "null"]},
            "remote_type": {"type": ["string", "null"]},
            "station": {"type": ["string", "null"]},
            "source_confidence": {"type": "number"},
        },
        "required": [
            "client_company",
            "project_name",
            "description",
            "required_skills",
            "workplace",
            "nationality_requirement",
            "duration",
            "start_date",
            "end_date",
            "headcount",
            "unit_price",
            "remote_type",
            "station",
            "source_confidence",
        ],
    },
}


def build_extract_prompt(subject: str | None, body: str, attachment_text: str | None) -> str:
    source = attachment_text or body
    return (
        "你是日本 IT 派遣/SES 案件信息录入助手。请从邮件正文或附件文本中抽取案件元数据，并严格返回 JSON。"
        "优先使用附件；没有附件时使用邮件正文。不要编造信息，映射不到的可填 null 或空数组，不要输出 ???、不明、unknown 作为占位。"
        "字段规则："
        "client_company=甲方/エンド/客户/会社名；"
        "project_name=案件名/件名/案件概要中最像项目名的一行；"
        "description=能概括业务内容和职责的原文摘要；"
        "required_skills=语言、云、DB、框架、OS、工具等技术栈数组，保留原文大小写；"
        "workplace=勤務地/作業場所/場所/最寄駅/在宅条件，必须尽量抽出具体地点或在宅状态；"
        "nationality_requirement 只能输出 日本籍のみ、制限なし 或 null；"
        "duration=期間/開始/終了；headcount=募集人数；unit_price=単価/月額/予算；"
        "start_date/end_date 必须是 YYYY-MM-DD；如果原文只有年月、长期、随时、即日等无法确定具体日期，则日期字段填 null，把原文放到 duration；"
        "remote_type=全在宅/フルリモート/半在宅/常駐/出社/不明；station=最寄駅或车站。"
        "如果原文写国籍不问、国籍不問、制限なし、外国籍可、中国籍可，则 nationality_requirement=制限なし。"
        "如果原文写日本籍のみ、日籍のみ、日本国籍限定，则 nationality_requirement=日本籍のみ。"
        "source_confidence 取 0 到 1，表示抽取可信度。\n\n"
        f"邮件标题：{subject or ''}\n"
        f"内容：\n{source}"
    )


async def extract_project_metadata(subject: str | None, body: str, attachment_text: str | None = None) -> dict[str, Any]:
    settings = get_settings()
    prompt = build_extract_prompt(subject, body, attachment_text)
    if settings.openai_api_key:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{settings.openai_api_base.rstrip('/')}/chat/completions",
                    headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                    json={
                        "model": settings.openai_model,
                        "messages": [
                            {"role": "system", "content": "只输出符合 JSON Schema 的案件元数据。"},
                            {"role": "user", "content": prompt},
                        ],
                        "response_format": {"type": "json_schema", "json_schema": PROJECT_EXTRACTION_SCHEMA},
                    },
                )
                response.raise_for_status()
                payload = response.json()
                content = payload["choices"][0]["message"]["content"]
                return normalize_project_metadata(json.loads(content), body, subject, attachment_text)
        except Exception as exc:
            fallback = heuristic_extract(subject, body, attachment_text)
            fallback["attributes"] = {**(fallback.get("attributes") or {}), "ai_error": str(exc)}
            return fallback

    return heuristic_extract(subject, body, attachment_text)


def normalize_project_metadata(data: dict[str, Any], body: str, subject: str | None, attachment_text: str | None) -> dict[str, Any]:
    fallback = heuristic_extract(subject, body, attachment_text)
    fallback_fields: list[str] = []

    def choose_text(field: str, value: Any) -> str:
        text = str(value or "").strip()
        if is_placeholder(text):
            fallback_fields.append(field)
            return str(fallback.get(field) or "").strip()
        return text

    client_company = choose_text("client_company", data.get("client_company")) or fallback["client_company"]
    project_name = choose_text("project_name", data.get("project_name")) or fallback["project_name"]
    description = choose_text("description", data.get("description")) or fallback["description"]
    workplace = choose_text("workplace", data.get("workplace")) or fallback["workplace"]
    required_skills = normalize_skills([*(data.get("required_skills") or []), *(fallback.get("required_skills") or [])])
    duration = choose_text("duration", data.get("duration")) or fallback.get("duration")
    unit_price = choose_text("unit_price", data.get("unit_price")) or fallback.get("unit_price")
    remote_type = choose_text("remote_type", data.get("remote_type")) or (fallback.get("attributes") or {}).get("remote_type")
    station = choose_text("station", data.get("station")) or (fallback.get("attributes") or {}).get("station")
    return {
        "client_company": client_company or "未识别甲方",
        "project_name": project_name or subject or "未命名案件",
        "description": description or body[:500] or "未识别描述",
        "required_skills": required_skills,
        "workplace": workplace or "未识别工作场所",
        "nationality_requirement": normalize_nationality_requirement(data.get("nationality_requirement")) or fallback.get("nationality_requirement"),
        "duration": duration or None,
        "start_date": normalize_iso_date(data.get("start_date")),
        "end_date": normalize_iso_date(data.get("end_date")),
        "headcount": data.get("headcount") if data.get("headcount") is not None else fallback.get("headcount"),
        "unit_price": unit_price or None,
        "attributes": {
            "source": "openai",
            "remote_type": remote_type,
            "station": station,
            "source_confidence": data.get("source_confidence"),
            "fallback_fields": fallback_fields,
        },
    }


def normalize_skills(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    skills: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        for part in re.split(r"[,、/／;；\n]", text):
            item = part.strip()
            key = item.lower()
            if item and key not in seen:
                seen.add(key)
                skills.append(item)
    return skills


def normalize_nationality_requirement(value: str | None) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if any(keyword in text for keyword in ["日本籍のみ", "日籍のみ", "日本国籍限定", "日本人のみ"]):
        return "日本籍のみ"
    if any(keyword in text for keyword in ["无限制", "無制限", "国籍不問", "国籍不问", "外国籍可", "中国籍可", "制限なし", "不問"]):
        return "制限なし"
    return "制限なし"


def is_placeholder(value: str | None) -> bool:
    text = str(value or "").strip().lower()
    if not text:
        return True
    return text in {"???", "??", "?", "不明", "不詳", "unknown", "n/a", "null", "none"}


def normalize_iso_date(value: Any) -> str | None:
    text = str(value or "").strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return None
    return text


def heuristic_extract(subject: str | None, body: str, attachment_text: str | None = None) -> dict[str, Any]:
    text = attachment_text or body
    skill_candidates = [
        "AWS", "Azure", "GCP", "Java", "Spring", "Spring Boot", "Golang", "Go", "Python", "Django", "FastAPI",
        "Vue", "React", "Angular", "TypeScript", "JavaScript", "Node", "MySQL", "PostgreSQL", "Oracle", "Redis",
        "Linux", "Windows", "Docker", "Kubernetes", "EKS", "Terraform", "Ansible", "Shell", "PHP", "C#", ".NET",
        "Swift", "Kotlin", "Android", "iOS", "SAP", "Salesforce", "PMO", "インフラ", "基盤", "ネットワーク",
    ]
    found_skills = [skill for skill in skill_candidates if re.search(rf"(?<![A-Za-z0-9]){re.escape(skill)}(?![A-Za-z0-9])", text, re.I)]
    workplace = extract_workplace(text)
    remote_type = extract_remote_type(text)

    company_match = re.search(r"(?:甲方|エンド|会社|公司|客户|クライアント|顧客)[:：\s]*([^\n\r]+)", text)
    project_match = re.search(r"(?:案件名|案件|プロジェクト名|PJ名)[:：\s]*([^\n\r]+)", text)
    people_match = re.search(r"(?:募集|人数|要員|枠|所需人员数)?[:：\s]*(\d+)\s*(?:名|人|枠)", text)
    price_match = re.search(r"(?:単価|月額|予算|金額|単金)[:：\s]*([~〜\d,\.]+\s*(?:万|万円|円)[^\n\r]*)", text)
    station_match = re.search(r"(?:最寄駅|最寄|駅)[:：\s]*([^\n\r]+)", text)
    nationality = normalize_nationality_requirement(text)
    return {
        "client_company": company_match.group(1).strip() if company_match else "未识别甲方",
        "project_name": project_match.group(1).strip() if project_match else subject or "未命名案件",
        "description": text[:800] or "未识别描述",
        "required_skills": normalize_skills(found_skills),
        "workplace": workplace,
        "nationality_requirement": nationality,
        "duration": extract_duration(text),
        "start_date": None,
        "end_date": None,
        "headcount": int(people_match.group(1)) if people_match else None,
        "unit_price": price_match.group(1).strip() if price_match else None,
        "attributes": {"source": "heuristic", "remote_type": remote_type, "station": station_match.group(1).strip() if station_match else None},
    }


def extract_remote_type(text: str) -> str | None:
    if re.search(r"フルリモート|全在宅|完全在宅|full\s*remote", text, re.I):
        return "全在宅"
    if re.search(r"リモート併用|一部在宅|週\d.*在宅|半在宅|ハイブリッド", text, re.I):
        return "半在宅"
    if re.search(r"常駐|出社|オンサイト|出勤", text, re.I):
        return "常駐"
    return None


def extract_workplace(text: str) -> str:
    remote_type = extract_remote_type(text)
    workplace_match = re.search(r"(?:勤務地|作業場所|場所|勤務場所|就業場所|現場)[:：\s]*([^\n\r]+)", text)
    station_match = re.search(r"(?:最寄駅|最寄|駅)[:：\s]*([^\n\r]+)", text)
    parts = []
    if workplace_match:
        parts.append(workplace_match.group(1).strip())
    if station_match:
        parts.append(station_match.group(1).strip())
    if remote_type:
        parts.append(remote_type)
    return " / ".join(dict.fromkeys(parts)) if parts else "未识别工作场所"


def extract_duration(text: str) -> str | None:
    match = re.search(r"(?:期間|作業期間|契約期間|開始|参画時期)[:：\s]*([^\n\r]+)", text)
    return match.group(1).strip() if match else None


def build_recommendation_prompt(project: Project, employees: list[Employee]) -> str:
    return (
        "你是 OA 系统候选人推荐模块。请根据案件信息和候选人信息计算匹配分数。"
        "权重规则：国籍匹配 10 分，不匹配 0 分；技术栈权重 6；IT 工作年数权重 2；居住地/通勤匹配权重 2。"
        "请输出候选人排序、分数、匹配理由和风险点。\n\n"
        f"案件：{project.project_name}\n"
        f"甲方：{project.client_company}\n"
        f"技术栈：{project.required_skills}\n"
        f"工作场所：{project.workplace}\n"
        f"国籍要求：{project.nationality_requirement or '无'}\n\n"
        f"候选人：{json.dumps([employee_to_prompt(e) for e in employees], ensure_ascii=False)}"
    )


def employee_to_prompt(employee: Employee) -> dict[str, Any]:
    return {
        "id": employee.id,
        "name": employee.full_name,
        "nationality": employee.nationality,
        "residence": employee.residence,
        "nearest_station": employee.nearest_station,
        "it_years": employee.it_years,
        "talent_category": employee.talent_category,
        "skills": employee.skills or [],
    }


def score_candidates(project: Project, employees: list[Employee]) -> list[dict[str, Any]]:
    project_skills = {str(item).lower() for item in (project.required_skills or [])}
    scored: list[dict[str, Any]] = []
    for employee in employees:
        reasons: list[str] = []
        score = 0.0
        if project.nationality_requirement and employee.nationality:
            if project.nationality_requirement in employee.nationality or employee.nationality in project.nationality_requirement:
                score += 10
                reasons.append("国籍匹配")
        employee_skills = {str(item.get("name", "")).lower() for item in (employee.skills or []) if isinstance(item, dict)}
        matched = project_skills & employee_skills
        if project_skills:
            skill_score = 6 * (len(matched) / len(project_skills))
            score += skill_score
            if matched:
                reasons.append(f"技术栈匹配：{', '.join(sorted(matched))}")
        if employee.it_years:
            year_score = min(employee.it_years / 5, 1) * 2
            score += year_score
            reasons.append(f"IT年数 {employee.it_years:g} 年")
        if employee.residence and project.workplace and employee.residence in project.workplace:
            score += 2
            reasons.append("居住地与工作场所相关")
        scored.append({"employee": employee, "score": round(score, 2), "reasons": reasons or ["可作为备选"]})
    return sorted(scored, key=lambda item: item["score"], reverse=True)
