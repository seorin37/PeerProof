"""Build a sourced, editable profile without inventing missing observations."""
from .schema import GROUPS, validate_profile


def build_business_profile(payload):
    data = validate_profile(payload)
    sections = {
        group["id"]: {key: {"label": label, **data["items"][key]} for key, label in group["fields"]}
        for group in GROUPS
    }
    # Only the Business Model enters the business similarity text. Numeric raw
    # financial observations remain accessible in their own section.
    profile_text = "\n".join(f"{item['label']}: {item['value']}"
                             for item in sections["business_model"].values())
    return {
        "schema_version": 2,
        "company": {"company_name": data["company_name"]},
        "analysis_as_of": data["analysis_as_of"],
        "profile_config": {"method": "manual", "domain": "unspecified"},
        "manual_profile": data,
        "sections": sections,
        "business_profile": {"profile_text": profile_text, "company_evidence": [],
                             "industry_context": [], "core_evidence": []},
        "review": {"status": "unreviewed", "observation_count": len(data["items"]),
                   "note": "모든 항목에 출처를 기록했습니다. 입력 내용은 원문과 대조 검토해야 합니다."},
    }
