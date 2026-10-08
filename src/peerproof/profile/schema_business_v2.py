"""
PeerProof Business Profile Schema v2

기존 src/peerproof/profile/schema.py를 건드리지 않고
Business 파트만 독립적으로 실험하기 위한 스키마입니다.

B1~B4 코드는 유지하고,
B5는 business_structure 대신 product_revenue_share를 사용합니다.
"""

BUSINESS_SCHEMA = {
"business": {



    # ====================================================

    # B1 Product / Service

    # ====================================================

    "products_services": {

        "code": "B1",

        "label": "주요 제품·서비스",



        "retrieval_categories": [

            "business",

        ],



        "queries": [

            "회사가 현재 외부 고객이나 이용자에게 실제로 판매·공급·제공하고 있는 주요 제품과 서비스는 무엇인가?",

            "공시의 주요 제품·서비스 표에서는 어떤 제품, 서비스 또는 제품군을 제시하고 있는가?",

            "각 주요 제품·서비스는 어떤 기능, 용도 또는 고객가치를 제공한다고 설명되어 있는가?",

            "공시에 등장하는 브랜드, 상표, 제품명, 서비스명, 솔루션명, 플랫폼명은 각각 어떤 역할로 설명되어 있는가?",

            "핵심 제품·서비스를 지원하는 앱, 플랫폼, 커뮤니티, 유지지원 등의 Supporting Service가 있는가?",

            "현재 실제 제공 중인 제품·서비스와 개발 중, 임상 중, 출시 예정, 신규사업 계획 단계의 Offering은 어떻게 구분되는가?",

            "현재 외부에 실제 제공 중인 기술, IP, 라이선스 권리 또는 기타 경제적 Offering이 있는가?",

        ],



        "rules": [

            "Product / Service는 분석 기준시점에 외부 고객·이용자·거래상대에게 실제 판매·공급·제공되고 있는 현재의 핵심 경제적 Offering을 의미한다.",

            "현재 실제 제공되는 Core Offering, Core Offering을 지원하는 Supporting Service, 개발·임상·출시예정·신규사업 단계의 Development/Planned Offering을 구분한다.",

            "현재 매출 발생 여부나 매출규모만으로 Product / Service 존재 여부를 판단하지 않는다.",

            "무료로 제공되는 서비스도 핵심 고객가치 자체를 제공하는 Offering이면 Product / Service가 될 수 있다.",

            "브랜드나 상표라는 이유만으로 Product / Service로 분류하지 않는다. 공시가 동일 명칭을 실제 Offering으로 설명하는 경우에만 Offering으로 사용할 수 있다.",

            "Solution, Platform 등의 표현만으로 Product / Service라고 판단하지 않고 실제 외부 제공 여부와 기능을 확인한다.",

            "Product / Service, Product Group, Business Area, Disclosed Business Segment, Accounting Operating Segment, Application Industry, Brand, Trademark를 서로 다른 개념으로 취급한다.",

            "Product Group과 개별 Product, Product와 회계상 영업부문, Product와 적용산업, Brand와 Product를 공시 근거 없이 임의로 1:1 매핑하지 않는다.",

            "공시가 직접 제공하는 범위 안에서 가장 구체적이면서 비교 의미가 있는 Offering 수준을 보존하되 불필요한 SKU 수준까지 강제하지 않는다.",

            "기업마다 공시 상세도가 다르다는 이유로 더 상세한 기업의 정보를 임의로 축약하거나 덜 상세한 기업의 정보를 추정하여 보완하지 않는다.",

            "동일 개념·동일 범위에 대해 더 최신 공시에서 직접적인 신규·변경·종료·정정 사실이 확인되면 최신 정보를 우선한다.",

            "최신 공시에서 단순히 언급되지 않았다는 이유만으로 이전 공시에서 직접 확인된 현재 사업구조를 자동 삭제하지 않는다.",

            "이전 공시의 직접 확인 사실은 최신 Evidence와 양립하고 종료·변경 근거가 없을 때만 조건부로 유지한다.",

            "공시에 없는 제품·서비스를 산업상식이나 모델 일반지식으로 추가하지 않는다.",

            "검색 결과가 없다는 사실만으로 미공시라고 판단하지 않는다.",

            "동일 시점·동일 범위의 직접 Evidence가 실질적으로 충돌하고 해소할 수 없으면 임의로 하나를 선택하지 않고 수동검토 대상으로 남긴다.",

        ],

    },



    # ====================================================

    # B2 Revenue Model

    # ====================================================

    "revenue_model": {

        "code": "B2",

        "label": "수익모델",



        "retrieval_categories": [

            "business",

            "finance",

        ],



        "queries": [

            "회사는 주요 제품·서비스·권리 또는 기타 Offering을 제공하고 어떤 형태의 대가를 받는다고 설명하는가?",

            "공시는 제품·상품 판매대가와 서비스·용역 제공대가를 어떻게 설명하거나 구분하는가?",

            "고객이 일정 기간 서비스나 제품에 접근·사용하기 위해 기간기준 또는 정기적인 대가를 지급하는 구조가 공시되어 있는가?",

            "사용량, 건수, 용량, 시간 등 실제 이용량에 따라 대가가 결정되는 구조가 공시되어 있는가?",

            "거래·중개·판매 성사 또는 거래금액을 기준으로 수수료를 받는 구조가 공시되어 있는가?",

            "광고 게재·노출·성과 또는 광고서비스 제공에 대한 대가가 공시되어 있는가?",

            "현재 외부 상대방에게 기술·IP·소프트웨어 등의 권리를 제공하는 계약이 있으며 그 대가 구조는 어떻게 설명되어 있는가?",

            "권리 제공 계약에서 Upfront, Milestone, Royalty 등 어떤 대가 방식이 공시되어 있는가?",

            "구축·설치·유지보수·지원·컨설팅·운영 등의 서비스에 대해 별도 대가를 받는 구조가 공시되어 있는가?",

            "자산·장비·공간·제품의 일정 기간 사용권에 대해 임대료 또는 사용료를 받는 구조가 공시되어 있는가?",

            "특정 Product / Service와 특정 Revenue Model 또는 과금구조가 직접 연결되어 있는가?",

            "공시된 수익구조 중 현재 실제 운영·계약 중인 구조와 향후 도입·추진 예정인 구조는 무엇인가?",

            "매출·수익 주석에서는 제품매출, 상품매출, 용역매출, 라이선스 등 수익 유형을 어떻게 구분하고 있는가?",

        ],



        "rules": [

            "Revenue Model은 외부 고객·이용자·거래상대에게 제공하는 경제적 Offering에 대해 어떤 경제적 거래구조와 산정기준으로 대가가 발생하는지를 의미한다.",

            "Product / Service 자체, Customer Type, Distribution Channel, Geography, Payment Method, 일반적인 Payment Terms, Revenue Recognition 시점과 구분한다.",

            "기업에는 여러 Current Revenue Model이 동시에 존재할 수 있다.",

            "특정 Product / Service와 특정 Revenue Model의 관계는 공시가 직접 또는 충분히 명확하게 연결할 때만 생성한다.",

            "제품이 존재한다는 이유만으로 Product Sale Revenue Model을 자동 생성하지 않는다.",

            "고객맞춤형 또는 프로젝트 단위라는 이유만으로 Service Revenue Model로 판단하지 않는다. 고객이 대가를 지급하는 주된 대상이 제품 이전인지 용역 수행인지 확인한다.",

            "설치·유지보수·컨설팅 등의 활동이 존재한다는 이유만으로 별도 Service Revenue Model을 생성하지 않고 별도 대가·계약·수익 Evidence를 확인한다.",

            "Subscription은 일정 기간의 지속적 접근·사용권과 기간 또는 갱신단위에 따른 대가가 확인될 때만 인정한다.",

            "반복구매, 반복매출, 계약갱신 가능성만으로 Subscription이라고 판단하지 않는다.",

            "앱이나 멤버십이 존재한다는 사실만으로 Subscription Revenue를 생성하지 않는다.",

            "Platform이나 Marketplace를 운영한다는 사실만으로 Transaction 또는 Commission Revenue Model을 생성하지 않는다.",

            "Licensing / Rights Grant를 상위 경제적 거래구조로 보고, 공시상 해당 계약에 연결된 Upfront, Milestone, Royalty 등을 하위 consideration mechanism으로 해석할 수 있다.",

            "Milestone이나 Upfront라는 명칭만으로 Licensing이라고 단정하지 않고 underlying contract를 확인한다.",

            "현금·카드·선불·후불·지급기한 등 이미 정해진 대가의 지급방법이나 시점은 원칙적으로 Revenue Model이 아니다.",

            "사용량·기간·거래액·시간·성과 등 대가의 크기나 발생 기준 자체는 Revenue Model 정보가 될 수 있다.",

            "제품매출·용역매출 등 회계 분류는 고수준 Revenue Model의 보조근거로 사용할 수 있지만 세부 monetization 구조를 임의로 생성하지 않는다.",

            "Revenue Recognition의 한 시점/기간에 걸친 인식은 Revenue Model 자체로 사용하지 않는다.",

            "현재 실제 운영 또는 유효한 계약구조만 Current Revenue Model에 포함하고 향후 구독전환, 라이선스 추진, 유료화 계획은 분리한다.",

            "특정 기간 실제 Revenue가 0이더라도 현재 유효한 monetization arrangement가 존재하면 Current Revenue Model은 존재할 수 있다.",

            "현재 Revenue Model이 없다는 사실이 충분히 확인되면 상태는 확인으로 두고 값에서 현재 없음으로 표현한다.",

            "동일 구조에 대한 최신 직접 Evidence에서 신규·변경·종료·정정이 확인되면 최신 정보를 우선한다.",

            "최신 공시의 단순 생략만으로 이전에 직접 확인된 지속적 Revenue Model을 자동 삭제하지 않는다.",

            "일회성 Upfront 등 개별 Payment Event와 지속적인 Licensing Arrangement의 존속을 구분한다.",

            "정성표현으로 Revenue Model 존재는 확인할 수 있으나 주요·대부분 등의 표현을 Revenue Share 숫자로 변환하지 않는다.",

            "산업관행이나 일반지식으로 Revenue Model을 보완하지 않는다.",

        ],

    },



    # ====================================================

    # B3 Customer Type

    # ====================================================

    "customer_type": {

        "code": "B3",

        "label": "고객 유형",



        "retrieval_categories": [

            "business",

            "risk",

        ],



        "queries": [

            "회사가 현재 제품·서비스를 직접 판매·공급하거나 계약하는 고객 또는 거래상대는 누구라고 공시되어 있는가?",

            "개인 소비자가 회사로부터 직접 제품·서비스를 구매·계약하거나 대가를 지급하는 거래가 공시되어 있는가?",

            "기업·법인·사업자가 회사와 직접 제품구매·공급·서비스·라이선스 등의 계약관계를 맺는다고 공시되어 있는가?",

            "정부기관·지방자치단체·공공기관 등이 회사와 직접 구매 또는 서비스 계약을 맺는다고 공시되어 있는가?",

            "Distributor, 도매상, 대리점, Dealer, Retailer 등의 중간 판매주체는 어떤 역할을 하며 회사의 직접 거래상대인지 확인되는가?",

            "회사의 제품·서비스를 최종적으로 사용하거나 소비하는 주체는 누구라고 공시되어 있는가?",

            "직접 거래상대와 최종사용자가 서로 다른 구조가 공시되어 있는가?",

            "직접 기업고객이 속한 산업 또는 고객군이 공시되어 있는가?",

            "제품·서비스가 최종적으로 사용되거나 적용되는 산업·업무·환경은 무엇이라고 공시되어 있는가?",

            "플랫폼이나 다면 서비스에서 판매자·구매자·광고주 등 어떤 참여자가 존재하며 누가 직접 대가를 지급하거나 계약하는가?",

            "특정 Product / Service와 특정 고객유형 또는 사용자유형이 공시에서 직접 연결되어 있는가?",

            "공시는 주요 사업 전반의 고객구조를 설명하는가, 아니면 특정 고객 또는 일부 사업 사례만 제시하는가?",

            "현재 고객군과 과거·일회성 고객 또는 향후 목표고객을 구분할 수 있는가?",

        ],



        "rules": [

            "Customer Type은 직접 구매·계약·대가 지급 등의 상업적 관계를 맺는 Direct Counterparty와 필요한 경우 최종 사용자 End User를 구분하여 구조화한다.",

            "Direct Counterparty와 End User를 자동으로 동일시하지 않는다.",

            "B2B, B2C, B2G 요약 분류는 End User가 아니라 Direct Commercial Counterparty를 기준으로 부여한다.",

            "한 기업에 B2B, B2C, B2G가 동시에 존재할 수 있다.",

            "소비재라는 이유만으로 B2C를 생성하지 않고 산업용 제품이라는 이유만으로 B2B를 생성하지 않는다.",

            "SaaS라는 Product Type만으로 B2B라고 판단하지 않는다.",

            "환자가 최종사용자라는 이유만으로 해당 기업의 거래를 B2C라고 판단하지 않는다.",

            "자사몰, 온라인, 오프라인, 직접판매, 대리점 등 판매경로 자체를 Customer Type으로 사용하지 않는다.",

            "Distributor, Dealer, Retailer 등이 실제 제품 매입·계약 상대임이 확인되면 Direct Counterparty로 기록할 수 있지만 중간 유통역할과 End User는 구분한다.",

            "'대리점을 통해 판매한다'는 표현만으로 대리점이 실제 Direct Buyer라고 확정하지 않는다.",

            "Customer Industry와 End-use/Application Industry를 구분하며 산업명을 Customer Type 자체로 사용하지 않는다.",

            "제품이 특정 산업에 사용된다는 사실만으로 해당 산업의 기업을 Direct Buyer라고 추정하지 않는다.",

            "정부지원사업, 정부 R&D 지원, 정책수혜 등의 사실만으로 B2G Customer라고 판단하지 않고 정부·공공기관과 직접 거래·계약 Evidence를 확인한다.",

            "플랫폼에서는 Paying Counterparty, Non-paying User, Participant 역할을 필요에 따라 분리한다.",

            "누가 대가를 지급하는지는 Customer Type 정보이고 과금방식 자체는 Revenue Model로 분리한다.",

            "특정 고객명은 해당 Customer Type이 존재한다는 근거가 될 수 있으나 한 고객의 존재를 전체 고객구조로 일반화하지 않는다.",

            "고객별 매출액·비중·의존도는 Customer Concentration 정보이며 Customer Type 자체와 구분한다.",

            "특정 Product / Service와 Customer Type 관계는 공시가 직접 연결할 때만 생성한다.",

            "목표시장, 목표고객, 진출 예정 고객군은 Current Customer Type으로 사용하지 않는다.",

            "현재 주요 Product / Service의 Direct Counterparty 구조가 어느 정도 설명되는지를 Feature Coverage의 핵심으로 본다.",

            "별도 downstream End User가 존재한다는 Evidence가 있고 그 유형이 확인되지 않으면 전체 Coverage는 부분확인일 수 있다.",

            "별도 End User layer가 의미 있게 존재하지 않고 Direct Counterparty 구조가 충분하다면 End User가 별도 공시되지 않아도 확인 가능하다.",

            "현재 상업적 Counterparty가 없다는 사실이 충분히 확인되면 상태는 확인으로 두고 값에서 현재 없음으로 표현한다.",

            "지속적 고객구조와 과거 특정 고객의 일회성 거래를 구분한다.",

            "최신 공시의 단순 생략만으로 과거 직접 확인된 지속적인 고객구조를 자동 삭제하지 않는다.",

            "산업상식이나 모델 일반지식으로 고객유형을 보완하지 않는다.",

        ],

    },



    # ====================================================

    # B4 Distribution Channel

    # ====================================================

    "distribution_channel": {

        "code": "B4",

        "label": "판매·유통 채널",



        "retrieval_categories": [

            "business",

            "finance",

        ],



        "queries": [

            "회사는 현재 주요 제품·서비스를 어떤 판매·공급·계약 경로를 통해 고객 또는 거래상대에게 제공한다고 공시하는가?",

            "회사가 고객 또는 거래상대와 직접 판매·공급·계약하는 경로는 무엇이라고 공시되어 있는가?",

            "회사가 운영하는 웹사이트·온라인몰·앱 등에서 실제 주문·구매·구독 또는 계약이 이루어지는 경로가 있는가?",

            "직영점·회사 영업조직 등 회사가 직접 운영하는 오프라인 또는 관계기반 판매경로가 공시되어 있는가?",

            "Distributor·Wholesaler·Dealer·Retailer·Reseller·Agent 등 중간 판매주체를 통한 경로가 있으며 각각 어떤 역할을 하는가?",

            "제3자 Marketplace·App Store·Cloud Marketplace 등의 경로에서 실제 판매·계약·서비스 접근권 제공이 이루어지는가?",

            "Franchisee 또는 가맹 네트워크가 제품·서비스의 판매·제공 경로에서 어떤 역할을 하는가?",

            "회사가 중간 재판매업자를 거치지 않고 최종 개인 소비자와 직접 판매관계를 맺는 D2C 경로가 공시되어 있는가?",

            "공시는 판매경로를 온라인·오프라인 또는 다른 접점 기준으로 어떻게 구분하고 있는가?",

            "특정 Product / Service와 특정 Channel 사이의 관계가 공시에서 직접 연결되어 있는가?",

            "국내·해외 등 판매지역과 Distributor·자사몰·직접판매 등의 판매경로를 구분할 수 있는가?",

            "언급된 웹사이트·SNS·제휴사·Referral 등이 실제 거래경로인지 단순 마케팅·고객유입 경로인지 확인되는가?",

            "각 판매채널별 Revenue Amount 또는 Revenue Share가 직접 공시되어 있는가?",

            "채널별 매출정보의 실적기간·연결/별도·통화·단위·분모 범위는 무엇인가?",

            "현재 구조적 판매채널과 과거·일회성·향후 예정 판매채널을 구분할 수 있는가?",

        ],



        "rules": [

            "Distribution Channel은 Product / Service가 고객·거래상대에게 판매·계약·구독·라이선스·상업적 접근 제공 등의 형태로 도달하는 상업적 경로를 의미한다.",

            "Distribution Channel을 Customer Type, Revenue Model, Geography, Logistics/Shipping, Marketing/Acquisition Channel과 구분한다.",

            "Direct/Intermediated와 Online/Offline은 서로 다른 dimension으로 취급하고 모든 Channel을 억지로 하나의 taxonomy에 맞추지 않는다.",

            "공시에 사용된 원래 Channel 명칭과 역할을 최대한 보존하며 canonical classification이 원문을 대체하지 않도록 한다.",

            "Direct Sales라고 해서 D2C라고 판단하지 않는다. Direct B2B도 가능하다.",

            "D2C는 최종 개인 소비자와 회사 간 직접 상업적 판매관계가 확인될 때만 인정한다.",

            "Online이라고 해서 D2C라고 판단하지 않고 Offline이라고 해서 Indirect라고 판단하지 않는다.",

            "Distributor, Dealer, Agent, Reseller 등의 정확한 역할은 공시 Evidence보다 세분화하여 추정하지 않는다.",

            "회사 자체가 제공하는 Marketplace와 회사 제품을 판매하는 제3자 Marketplace를 역할에 따라 구분한다.",

            "단순 listing이나 노출만으로 Commercial Channel이라고 확정하지 않고 실제 주문·판매·계약·구독·접근권 제공 경로인지 확인한다.",

            "물리적 제품뿐 아니라 SaaS·Software·Service·License 등 비물리적 Offering의 상업적 주문·계약·접근권 판매경로도 Distribution Channel에 포함할 수 있다.",

            "주문형 제품이라는 이유만으로 Direct Channel이라고 판단하지 않고 직접판매·직접계약 Evidence를 확인한다.",

            "OEM이라는 표현만으로 Channel을 생성하지 않고 생산구조인지 고객·판매경로인지 확인한다.",

            "Referral이나 Lead Source는 실제 거래·계약 중개 또는 재판매 역할이 확인되지 않으면 Marketing/Acquisition 정보로 본다.",

            "Franchise 존재만으로 Retail Channel을 생성하지 않고 Franchisee의 실제 판매·서비스 제공 역할을 확인한다.",

            "고객명이나 적용산업을 Distribution Channel로 사용하지 않는다.",

            "특정 Product / Service와 Channel 관계는 공시가 직접 연결할 때만 생성한다.",

            "Channel Existence와 Channel Revenue Mix를 서로 다른 정보로 구분한다.",

            "정성적으로 주요·대부분·중심이라고 표현된 Channel을 정확한 Revenue Share 숫자로 변환하지 않는다.",

            "Channel Revenue Amount, 직접 공시된 Channel Revenue Share, deterministic하게 계산한 Derived Share를 구분한다.",

            "Channel Revenue Share의 deterministic 계산은 동일 기간·연결/별도·기업범위·Revenue Scope·통화·단위를 확인한 경우에만 수행하며 LLM이 직접 계산하지 않는다.",

            "동일 Channel Revenue Table의 Total이 동일 scope임이 확인되면 denominator 후보로 우선 사용하고 다른 재무제표 매출액을 임의 분모로 사용하지 않는다.",

            "Online과 Own Mall처럼 상위·하위 Channel hierarchy를 동일 레벨 Category처럼 합산하지 않는다.",

            "국내·해외 매출비중을 Direct·Distributor 등 Channel Revenue Share로 변환하지 않는다.",

            "Channel Structure Coverage는 현재 주요 Product / Service의 판매·계약 경로를 충분히 설명할 수 있는지를 기준으로 판단한다.",

            "Channel Revenue Mix Coverage는 기준 실적기간의 Channel-coded Revenue가 전체 Revenue scope를 충분히 설명하는지를 기준으로 판단한다.",

            "Distribution Channel 전체가 확인되려면 Channel Structure와 Channel Revenue Mix 두 Coverage가 모두 충분히 확인되어야 한다.",

            "모든 구조적 Channel 각각에 별도 Revenue Share가 존재할 필요는 없으며 기준기간의 Channel-coded Revenue가 전체 Revenue를 충분히 설명하면 Revenue Mix는 확인 가능하다.",

            "Channel Structure는 충분하지만 기준기간 Channel Revenue Mix가 일부 또는 전부 미공시이면 전체 Distribution Channel은 부분확인으로 처리한다.",

            "구조적으로 존재하는 Channel과 특정 실적기간에 실제 매출이 발생한 Channel을 동일시하지 않는다.",

            "Channel Existence는 지속적인 판매구조이고 종료 Evidence가 없으면 조건부 Carry-Forward가 가능하다.",

            "Channel Revenue Mix는 기간 실적이므로 과거 비중을 최신 또는 현재기간으로 Carry-Forward하지 않는다.",

            "향후 입점·Dealer 모집·Marketplace 진출 계획은 Current Channel로 사용하지 않는다.",

            "현재 상업적 Distribution Channel이 없다는 사실이 충분히 확인되면 상태는 확인으로 두고 값에서 현재 없음으로 표현한다.",

            "산업관행이나 일반지식으로 Channel을 보완하지 않는다.",

        ],

    },



    # ====================================================

    # B5 Product Revenue Share

    # ====================================================

    "product_revenue_share": {

        "code": "B5",

        "label": "제품·서비스 매출비중",



        "retrieval_categories": [

            "business",

            "finance",

        ],



        "queries": [

            "공시는 주요 제품·서비스별 또는 제품·서비스 그룹별 매출액과 매출비중을 어떻게 제시하고 있는가?",

            "매출표의 각 분류항목은 개별 제품·서비스, 제품·서비스 그룹, 사업부문, 회계상 영업부문 중 무엇을 의미한다고 설명되어 있는가?",

            "제품·서비스 매출비중의 분모가 되는 전체 매출 또는 동일 범위의 합계는 얼마이며 어떤 범위를 기준으로 하는가?",

            "해당 제품·서비스 매출액과 비중은 어떤 시작일과 종료일의 실적이며 연간, 누적 중간기간, 단일기간 중 어느 기준인가?",

            "해당 매출표는 연결기준인지 별도기준인지 공시에 어떻게 표시되어 있는가?",

            "해당 표의 통화와 매출액 표시단위는 무엇인가?",

            "제품·서비스 매출표의 주석이나 각주는 분류범위, 기간, 연결·별도 기준, 합계 또는 기타 항목을 어떻게 설명하는가?",

            "상위 제품·서비스 그룹 내부의 개별 제품·서비스 매출액 또는 비중이 별도로 공시되어 있는가?",

            "허용 공시들에서 동일하거나 비교 가능한 제품·서비스 Revenue Category가 기간별로 어떻게 제시되어 있는가?",

            "분석기간의 전체 Revenue 또는 Product / Service Revenue가 0인지 공시에서 확인되는가?",

        ],



        "rules": [

            "Product Revenue Share는 특정 실적기간의 전체 Revenue 중 Product, Service, Product Group 또는 Service Group이 차지하는 매출액과 비중을 의미한다.",

            "Business Segment, Accounting Operating Segment, Channel, Geography, Customer, Revenue Model 기준의 비중을 Product Revenue Share와 혼동하지 않는다.",

            "Product / Service Feature에서 확인된 Offering 구조와 Revenue Table의 분류체계를 공시 근거 없이 임의로 연결하거나 하위 Product에 상위 Group 비중을 배분하지 않는다.",

            "회사가 직접 공시한 Revenue Amount, 직접 공시한 Revenue Share, 공시 금액으로 deterministic하게 계산한 Derived Share를 구분한다.",

            "Derived Share라는 이유만으로 부분확인으로 낮추지 않는다. numerator와 denominator의 호환성이 완전히 확인되고 deterministic 계산을 사용했다면 확인 근거로 사용할 수 있다.",

            "LLM이 직접 매출액을 나누거나 합산하여 비율을 생성하지 않는다. 계산은 deterministic tool이 담당한다.",

            "모든 Revenue Share는 실적기간 시작일·종료일 및 연간·중간기간, 누적·단일기간 여부와 함께 해석한다.",

            "분기보고서라는 문서명만으로 해당 수치를 단일분기 실적으로 판단하지 않는다.",

            "연결과 별도 기준이 다른 numerator와 denominator를 결합하지 않는다.",

            "원천 통화와 금액 단위를 확인하고 서로 다른 단위를 그대로 계산하지 않는다.",

            "Derived Share의 denominator는 numerator와 의미적으로 동일한 Revenue Scope를 가져야 한다.",

            "동일 Product / Service Revenue Table에 직접 공시된 Total이 있고 동일 scope임이 확인되면 이를 우선 denominator 후보로 사용한다.",

            "다른 표 또는 재무제표의 Total Revenue를 denominator로 사용할 때는 동일 기간·회계범위·Revenue 정의·기업범위·분류범위가 확인되어야 한다.",

            "denominator scope가 확인되지 않으면 Derived Share를 생성하지 않는다.",

            "Product Table Total과 다른 재무제표 Total이 다르다는 이유만으로 충돌로 판단하지 않고 먼저 scope, basis, 기간, 조정 차이를 확인한다.",

            "과거기간 Revenue Share를 최신 또는 현재기간의 값으로 Carry-Forward하지 않는다.",

            "이전 기간의 Revenue Share는 필요하면 historical value로 보존할 수 있으나 반드시 해당 실적기간과 함께 사용한다.",

            "Product Revenue Share 100%는 Product / Service 수준에서 직접 공시되거나 동일 scope numerator와 denominator로 deterministic하게 검증되는 경우에만 인정한다.",

            "단일 영업부문, 단일 사업부문, 단일 Product / Service 존재만으로 특정 Product Revenue Share를 100%로 판단하지 않는다.",

            "기타, Others, etc. 항목은 공시된 Revenue Category 자체로 보존하고 알려진 제품에 임의 배분하지 않는다.",

            "직접 공시된 Share와 금액으로 재계산한 Derived Share가 반올림 때문에 다를 수 있으며 이를 자동 충돌로 판단하지 않는다.",

            "Product Revenue Share 전체 Coverage는 Product / Service Feature에서 확인된 Revenue-relevant Offering 구조를 어느 수준까지 매출구조가 설명하는지를 기준으로 판단한다.",

            "Product Group이라는 이유만으로 자동 부분확인 처리하지 않는다. 더 하위 Offering이 확인되지 않고 해당 수준의 Revenue 구조가 충분하면 확인 가능하다.",

            "더 구체적인 Current Core Offering 구조가 확인되어 있으나 상위 Group Revenue까지만 공개된 경우 전체 Coverage는 부분확인일 수 있다.",

            "전체 Revenue가 0이고 Product / Service Revenue도 없다는 사실이 직접 확인되면 비율은 0%가 아니라 정의되지 않으므로 해당없음으로 처리한다.",

            "Retrieval 실패만으로 미공시 또는 해당없음으로 판단하지 않는다.",

        ],

    },

}
}

# 위 업로드 블록은 `"business": {...}` 형태이므로
# 실제 Builder에서는 내부 business 딕셔너리만 사용합니다.
BUSINESS_SCHEMA = BUSINESS_SCHEMA["business"]


def get_business_schema() -> dict:
    """Business v2 schema를 반환합니다."""
    return BUSINESS_SCHEMA


def get_feature(feature_key: str) -> dict:
    """특정 Business feature 정의를 반환합니다."""
    if feature_key not in BUSINESS_SCHEMA:
        raise KeyError(
            f"알 수 없는 Business feature입니다: {feature_key}. "
            f"가능한 값: {', '.join(BUSINESS_SCHEMA.keys())}"
        )
    return BUSINESS_SCHEMA[feature_key]


def feature_keys() -> list[str]:
    """Business feature key 목록을 반환합니다."""
    return list(BUSINESS_SCHEMA.keys())
