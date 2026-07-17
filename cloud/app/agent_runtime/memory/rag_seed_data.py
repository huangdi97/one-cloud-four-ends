"""RAG demo seed data — 为知识库注入模拟医药行业知识。"""

import logging

logger = logging.getLogger(__name__)


def seed_demo_data(vm) -> None:
    """注入20-30条模拟知识：药品信息/HCP画像/竞品情报/临床指南。"""
    records = []

    # 药品信息 6条
    records.extend(
        [
            (
                "drug:ai_wei_ling",
                "阿维灵（Avilin）是一种新型EGFR-TKI，用于非小细胞肺癌一线治疗，推荐剂量为每日80mg口服。常见不良反应包括皮疹（45%）、腹泻（38%），3级以上不良反应发生率约12%。临床研究显示中位无进展生存期（PFS）为11.2个月，优于对照组的8.5个月。",
                {"category": "drug_info", "drug": "阿维灵", "indication": "非小细胞肺癌"},
            ),
            (
                "drug:ke_lin_mei_su",
                "克林霉素是一种广谱抗生素，主要用于革兰阳性菌引起的感染，包括呼吸道感染、皮肤软组织感染。成人常用剂量为150-300mg每6小时一次。对金黄色葡萄球菌、链球菌有良好抗菌活性。注意与林可霉素有交叉耐药性。",
                {"category": "drug_info", "drug": "克林霉素", "indication": "细菌感染"},
            ),
            (
                "drug:xin_na_ka_ban",
                "欣纳卡班是一种新型抗凝血药物，用于非瓣膜性房颤患者的卒中预防。标准剂量为每日一次20mg。相比华法林，卒中风险降低21%，大出血风险降低31%。无需常规凝血功能监测，与食物相互作用少。",
                {"category": "drug_info", "drug": "欣纳卡班", "indication": "房颤卒中预防"},
            ),
            (
                "drug:wei_sheng_su_d3",
                "维生素D3（胆钙化醇）用于预防和治疗维生素D缺乏症。成人预防剂量为每日400-800IU，治疗剂量为每日2000-4000IU。长期过量可能导致高钙血症。建议在医生指导下使用，尤其对骨质疏松高风险人群。",
                {"category": "drug_info", "drug": "维生素D3", "indication": "维生素D缺乏"},
            ),
            (
                "drug:pu_luo_xi_ding",
                "普罗西定是一种选择性5-羟色胺再摄取抑制剂（SSRI），用于抑郁症和焦虑症的治疗。初始剂量为每日20mg，可根据疗效调整至40-60mg。常见不良反应为恶心、失眠、性功能障碍。起效时间约2-4周，需规律服药。",
                {"category": "drug_info", "drug": "普罗西定", "indication": "抑郁症/焦虑症"},
            ),
            (
                "drug:a_tuo_fa_ta_ding",
                "阿托伐他汀是一种HMG-CoA还原酶抑制剂，用于高胆固醇血症和冠心病防治。常用剂量为10-40mg每日一次。可降低LDL-C 39-60%。注意监测肝功能和肌酸激酶，与某些CYP3A4抑制剂合用时需调整剂量。",
                {"category": "drug_info", "drug": "阿托伐他汀", "indication": "高胆固醇血症"},
            ),
        ]
    )

    # HCP画像 6条
    records.extend(
        [
            (
                "hcp:zhang_wei",
                "张伟教授，三甲医院呼吸科主任医师，从事肺癌诊治25年，擅长靶向治疗和免疫治疗。年门诊量约5000人次，处方偏好：EGFR-TKI类药物。参与多项国际多中心临床研究，在非小细胞肺癌领域发表SCI论文60余篇。",
                {"category": "hcp_profile", "hospital": "省人民医院", "specialty": "呼吸内科"},
            ),
            (
                "hcp:li_mei",
                "李梅主任，三甲医院心内科副主任，专攻心律失常和抗凝治疗。年处方抗凝药物约3000例。对新型口服抗凝药接受度较高，定期参加欧洲心脏病学会年会。科室年PCI手术量约800台。",
                {"category": "hcp_profile", "hospital": "市心血管病医院", "specialty": "心内科"},
            ),
            (
                "hcp:wang_fang",
                "王芳，社区医院全科主治医师，年门诊量约8000人次，覆盖高血压、糖尿病等慢性病管理。处方倾向经典仿制药，对创新药认知有待提升。参加继续教育项目年均2-3次。",
                {"category": "hcp_profile", "hospital": "社区健康服务中心", "specialty": "全科"},
            ),
            (
                "hcp:cheng_qiang",
                "程强教授，肿瘤医院消化道肿瘤科主任，擅长胃癌和结直肠癌的综合治疗。担任CSCO青年委员，主持国家级课题3项。对新药临床试验持开放态度，目前牵头1项III期胃癌靶向治疗临床研究。",
                {"category": "hcp_profile", "hospital": "省肿瘤医院", "specialty": "肿瘤内科"},
            ),
            (
                "hcp:liu_yan",
                "刘艳博士，三甲医院内分泌科副主任医师，专注糖尿病和甲状腺疾病。年门诊量4000人次，胰岛素处方经验丰富。参与编写《中国2型糖尿病防治指南》，注重患者教育和生活方式干预。",
                {"category": "hcp_profile", "hospital": "大学附属医院", "specialty": "内分泌科"},
            ),
            (
                "hcp:zhao_lei",
                "赵磊主任，儿童医院呼吸科主任，擅长儿童哮喘和过敏性疾病的诊治。年门诊量逾6000人次。倡导规范化吸入治疗，对儿童用药安全极为重视。发表儿科呼吸领域论文30余篇。",
                {"category": "hcp_profile", "hospital": "市儿童医院", "specialty": "儿科呼吸"},
            ),
        ]
    )

    # 竞品情报 6条
    records.extend(
        [
            (
                "compete:competitor_a",
                "竞争对手A公司研发的AK-100是一种PD-1/CTLA-4双特异性抗体，目前已进入II期临床试验。与本公司产品相比，AK-100在临床前研究中显示更强的肿瘤抑制活性，但安全性数据尚未充分披露。预计2026年提交NDA申请。",
                {"category": "competitive_intel", "company": "竞品A", "drug": "AK-100", "phase": "II期临床"},
            ),
            (
                "compete:competitor_b",
                "竞品B公司宣布其BTK抑制剂B-200获FDA突破性疗法认定，用于治疗复发/难治性套细胞淋巴瘤。II期临床ORR达78%，远超现有标准治疗。该公司计划加速推进上市申请，可能提前6个月进入市场。",
                {"category": "competitive_intel", "company": "竞品B", "drug": "B-200", "phase": "NDA准备"},
            ),
            (
                "compete:competitor_c",
                "竞品C公司发布的C-300（三代EGFR-TKI）III期临床数据表现优异，mPFS达18.9个月，脑转移亚组客观缓解率85%。该公司正积极拓展医保谈判，预计定价比本公司同类产品低15-20%，将对市场份额构成较大压力。",
                {"category": "competitive_intel", "company": "竞品C", "drug": "C-300", "phase": "III期完成"},
            ),
            (
                "compete:competitor_d",
                "竞品D公司GLP-1受体激动剂D-400在减重适应症III期临床试验中达到主要终点，52周平均减重15.3%。该公司已启动FDA和NMPA双报策略，预计2025年底获批。产能方面已投资20亿元建设新的生产基地。",
                {"category": "competitive_intel", "company": "竞品D", "drug": "D-400", "phase": "III期成功"},
            ),
            (
                "compete:competitor_e",
                "竞品E公司宣布与某AI药物发现公司达成战略合作，利用AI平台加速小分子药物研发。合作首付款5000万美元，里程碑付款最高可达12亿美元。首个合作项目针对三阴性乳腺癌，预计2025年进入临床。",
                {"category": "competitive_intel", "company": "竞品E", "drug": "AI平台管线", "phase": "临床前"},
            ),
            (
                "compete:competitor_f",
                "竞品F公司的F-500（JAK抑制剂）因安全性问题被FDA部分暂停临床试验。此前该公司已投入8亿美元研发费用。此事件为本公司同靶点管线的差异化开发提供了窗口期，但需注意加快进度以抢占市场先机。",
                {"category": "competitive_intel", "company": "竞品F", "drug": "F-500", "phase": "临床暂停"},
            ),
        ]
    )

    # 临床指南 6条
    records.extend(
        [
            (
                "guideline:nsclc_2024",
                "2024版非小细胞肺癌诊疗指南更新要点：对EGFR突变阳性患者，一线推荐奥希替尼或阿维灵。新增免疫联合化疗方案用于PD-L1阳性患者。脑转移患者推荐TKI治疗优先于全脑放疗。分子检测推荐NGS panel覆盖至少10个驱动基因。",
                {"category": "clinical_guideline", "disease": "非小细胞肺癌", "year": "2024"},
            ),
            (
                "guideline:hypertension_2024",
                "2024中国高血压防治指南推荐：血压控制目标<130/80mmHg（高危患者）或<140/90mmHg（一般人群）。起始治疗推荐联合用药方案。强调家庭血压监测和远程管理在血压控制中的重要性。新增SGLT2抑制剂在心衰合并高血压患者中的推荐。",
                {"category": "clinical_guideline", "disease": "高血压", "year": "2024"},
            ),
            (
                "guideline:diabetes_2024",
                "2024年ADA糖尿病诊疗标准推荐：HbA1c控制目标<7.0%（大多数成人）。合并ASCVD或高危因素者推荐GLP-1RA或SGLT2抑制剂。强调个体化治疗和患者共同决策。新增持续葡萄糖监测系统在1型糖尿病中的A级推荐。",
                {"category": "clinical_guideline", "disease": "糖尿病", "year": "2024"},
            ),
            (
                "guideline:af_stroke_2024",
                "2024年房颤卒中预防指南更新：CHA2DS2-VASc评分≥2的男性及≥3的女性推荐口服抗凝药。新型口服抗凝药（NOACs）优于华法林。左心耳封堵术适用于抗凝禁忌患者。强调房颤早期节律控制可能改善预后。",
                {"category": "clinical_guideline", "disease": "房颤", "year": "2024"},
            ),
            (
                "guideline:copd_2024",
                "GOLD 2024慢阻肺诊疗策略：初始评估强调症状和急性加重风险的个体化评估。药物治疗推荐LAMA/LABA联合作为初始方案，血嗜酸性粒细胞计数指导ICS使用。非药物治疗强调肺康复、疫苗接种和自我管理教育。",
                {"category": "clinical_guideline", "disease": "慢阻肺", "year": "2024"},
            ),
            (
                "guideline:breast_cancer_2024",
                "2024年乳腺癌诊疗指南：HR+/HER2-晚期乳腺癌一线推荐CDK4/6抑制剂联合内分泌治疗。三阴性乳腺癌术后辅助治疗推荐帕博利珠单抗+化疗。HER2低表达新分类将影响治疗策略选择。强调基因检测指导精准治疗。",
                {"category": "clinical_guideline", "disease": "乳腺癌", "year": "2024"},
            ),
        ]
    )

    for key, content, metadata in records:
        try:
            vm.store(agent_name="knowledge_worker", key=key, content=content, metadata=metadata, share_with=["*"])
        except Exception:
            logger.exception("Failed to seed %s", key)

    count = len(records)
    logger.info("Seeded %d demo records into vector memory", count)

    try:
        results = vm.search(agent_name="knowledge_worker", query="肺癌靶向治疗", top_k=3)
        logger.info("Verification search returned %d results", len(results))
    except Exception:
        logger.exception("Verification search failed")
