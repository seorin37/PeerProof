PROFILE_SCHEMA = {
    "business": {
        "description": "기업이 무엇을 판매하고 누구에게 어떤 방식으로 수익을 창출하는지",
        "fields": [
            "products_services",
            "revenue_model",
            "customer_type",
            "distribution_channel",
            "business_structure",
        ],
    },

    "growth": {
        "description": "기업의 성장 방향과 확장성",
        "fields": [
            "revenue_growth",
            "global_expansion",
            "new_business",
            "capacity_expansion",
        ],
    },

    "risk": {
        "description": "사업과 영업에 영향을 줄 수 있는 주요 위험",
        "fields": [
            "customer_concentration",
            "competition_risk",
            "regulatory_risk",
            "supply_chain_risk",
        ],
    },

    "finance": {
        "description": "수익성, 안정성, 현금흐름 등 재무 특성",
        "fields": [
            "revenue",
            "operating_income",
            "net_income",
            "operating_margin",
            "cash_flow",
        ],
    },
}


CATEGORY_KEYWORDS = {

    "business": [
        "사업의 내용",
        "사업의 개요",
        "사업 개요",
        "주요 사업",
        "주요 제품",
        "주요제품",
        "주요 서비스",
        "제품 및 서비스",
        "제품과 서비스",
        "매출 유형",
        "매출구성",
        "매출 구성",
        "매출 비중",
        "판매경로",
        "판매 경로",
        "판매방법",
        "판매 방법",
        "유통",
        "고객",
        "고객사",
        "브랜드",
        "수익구조",
        "수익 구조",
    ],

    "growth": [
        "성장",
        "매출 증가",
        "매출 성장",
        "시장 확대",
        "사업 확대",
        "해외",
        "수출",
        "글로벌",
        "신규 사업",
        "신규사업",
        "신제품",
        "신규 제품",
        "시장 진출",
        "해외 진출",
        "생산능력",
        "생산 능력",
        "증설",
        "투자계획",
        "투자 계획",
    ],

    "risk": [
        "위험",
        "위험요인",
        "위험 요인",
        "리스크",
        "경쟁",
        "시장위험",
        "시장 위험",
        "규제",
        "법률",
        "법규",
        "의존",
        "집중도",
        "거래처",
        "주요 고객",
        "원재료",
        "공급망",
        "환율",
        "금리",
    ],

    "finance": [
        "매출액",
        "영업이익",
        "영업손실",
        "당기순이익",
        "당기순손실",
        "순이익",
        "자산총계",
        "부채총계",
        "자본총계",
        "현금흐름",
        "영업활동현금흐름",
        "영업활동 현금흐름",
        "재무상태표",
        "손익계산서",
        "포괄손익계산서",
        "현금흐름표",
    ],
}


REPORT_PRIORITY = {

    # 사업 본질은 사업보고서를 우선
    "business": [
        "annual",
        "semiannual",
        "quarterly",
    ],

    # 성장 상태는 최근 자료 우선
    "growth": [
        "quarterly",
        "semiannual",
        "annual",
    ],

    # 위험 설명은 사업보고서가 상대적으로 상세
    "risk": [
        "annual",
        "semiannual",
        "quarterly",
    ],

    # 재무는 최근 상태 우선
    "finance": [
        "quarterly",
        "semiannual",
        "annual",
    ],
}