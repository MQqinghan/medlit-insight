"""期刊静态指标库生成脚本。

运行：python data/build_journals.py  →  生成 data/journals.json

字段说明：
  name   期刊全称（与 PubMed Journal/Title 对齐）
  abbrev ISO 缩写（与 PubMed ISOAbbreviation 对齐）
  issn   print ISSN（不确定的留空，匹配时自动降级为刊名/缩写匹配）
  if     影响因子（约 2024 JCR 公开口径的近似整理值）
  cas    中科院大类分区（1-4）
  q      JCR 分区（Q1-Q4）
  cat    学科分组

⚠️ 口径声明：本库为演示用静态数据，非实时权威数据；生产环境请替换为
中科院分区官方 / LetPub 等权威源，只需保持 JSON 结构不变。
"""
import json
import os

# (name, abbrev, issn, if, cas, q, cat)
JOURNALS = [
    # ---------- 综合医学 ----------
    ("The New England Journal of Medicine", "N Engl J Med", "0028-4793", 96.2, 1, "Q1", "综合医学"),
    ("The Lancet", "Lancet", "0140-6736", 98.4, 1, "Q1", "综合医学"),
    ("JAMA", "JAMA", "0098-7484", 63.1, 1, "Q1", "综合医学"),
    ("The BMJ", "BMJ", "0959-8138", 93.6, 1, "Q1", "综合医学"),
    ("Nature Medicine", "Nat Med", "1078-8956", 58.7, 1, "Q1", "综合医学"),
    ("Annals of Internal Medicine", "Ann Intern Med", "0003-4819", 39.2, 1, "Q1", "综合医学"),
    ("PLoS Medicine", "PLoS Med", "1549-1277", 10.5, 1, "Q1", "综合医学"),
    ("BMC Medicine", "BMC Med", "1741-7015", 8.3, 1, "Q1", "综合医学"),
    # ---------- 肿瘤 ----------
    ("CA: A Cancer Journal for Clinicians", "CA Cancer J Clin", "0007-9235", 503.1, 1, "Q1", "肿瘤"),
    ("Journal of Clinical Oncology", "J Clin Oncol", "0732-183X", 42.1, 1, "Q1", "肿瘤"),
    ("Lancet Oncology", "Lancet Oncol", "1470-2045", 41.4, 1, "Q1", "肿瘤"),
    ("Nature Reviews Cancer", "Nat Rev Cancer", "1474-175X", 72.5, 1, "Q1", "肿瘤"),
    ("Cancer Cell", "Cancer Cell", "1535-6108", 48.8, 1, "Q1", "肿瘤"),
    ("Annals of Oncology", "Ann Oncol", "0923-7534", 50.5, 1, "Q1", "肿瘤"),
    ("JAMA Oncology", "JAMA Oncol", "2374-2437", 28.4, 1, "Q1", "肿瘤"),
    ("Clinical Cancer Research", "Clin Cancer Res", "1078-0432", 10.2, 1, "Q1", "肿瘤"),
    ("Cancer Research", "Cancer Res", "0008-5472", 12.5, 1, "Q1", "肿瘤"),
    ("British Journal of Cancer", "Br J Cancer", "0007-0920", 6.4, 2, "Q1", "肿瘤"),
    ("European Journal of Cancer", "Eur J Cancer", "0959-8049", 5.4, 2, "Q2", "肿瘤"),
    ("Oncogene", "Oncogene", "0950-9232", 6.9, 2, "Q1", "肿瘤"),
    ("Seminars in Cancer Biology", "Semin Cancer Biol", "1044-579X", 12.5, 1, "Q1", "肿瘤"),
    ("Cancer", "Cancer", "0008-543X", 6.1, 2, "Q2", "肿瘤"),
    ("Frontiers in Oncology", "Front Oncol", "2234-943X", 3.5, 3, "Q2", "肿瘤"),
    # ---------- 心血管 ----------
    ("Circulation", "Circulation", "0009-7322", 37.8, 1, "Q1", "心血管"),
    ("European Heart Journal", "Eur Heart J", "0195-668X", 37.6, 1, "Q1", "心血管"),
    ("Journal of the American College of Cardiology", "J Am Coll Cardiol", "0735-1097", 26.7, 1, "Q1", "心血管"),
    ("JAMA Cardiology", "JAMA Cardiol", "2380-6583", 27.7, 1, "Q1", "心血管"),
    ("Circulation Research", "Circ Res", "0009-7330", 20.1, 1, "Q1", "心血管"),
    ("European Journal of Heart Failure", "Eur J Heart Fail", "1388-9842", 18.2, 1, "Q1", "心血管"),
    ("Stroke", "Stroke", "0039-2499", 9.2, 1, "Q1", "心血管"),
    ("Hypertension", "Hypertension", "0194-911X", 7.3, 2, "Q1", "心血管"),
    ("Heart", "Heart", "1355-6037", 5.7, 2, "Q2", "心血管"),
    ("Atherosclerosis", "Atherosclerosis", "0021-9150", 4.9, 3, "Q2", "心血管"),
    ("International Journal of Cardiology", "Int J Cardiol", "0167-5273", 3.2, 3, "Q3", "心血管"),
    # ---------- 神经 ----------
    ("Lancet Neurology", "Lancet Neurol", "1474-4422", 48.0, 1, "Q1", "神经"),
    ("Brain", "Brain", "0006-8950", 14.5, 1, "Q1", "神经"),
    ("Annals of Neurology", "Ann Neurol", "0364-5134", 11.2, 1, "Q1", "神经"),
    ("JAMA Neurology", "JAMA Neurol", "2168-6149", 26.4, 1, "Q1", "神经"),
    ("Neurology", "Neurology", "0028-3878", 11.3, 1, "Q1", "神经"),
    ("Nature Neuroscience", "Nat Neurosci", "1097-6256", 21.2, 1, "Q1", "神经"),
    ("Acta Neuropathologica", "Acta Neuropathol", "0001-6322", 13.2, 1, "Q1", "神经"),
    ("Alzheimer's & Dementia", "Alzheimers Dement", "1552-5260", 14.0, 1, "Q1", "神经"),
    ("Brain, Behavior, and Immunity", "Brain Behav Immun", "0889-1591", 8.8, 2, "Q1", "神经"),
    # ---------- 内分泌代谢 ----------
    ("Diabetes Care", "Diabetes Care", "0149-5992", 14.8, 1, "Q1", "内分泌代谢"),
    ("Diabetologia", "Diabetologia", "0012-186X", 8.3, 2, "Q1", "内分泌代谢"),
    ("Journal of Clinical Endocrinology & Metabolism", "J Clin Endocrinol Metab", "0021-972X", 5.5, 2, "Q1", "内分泌代谢"),
    ("Diabetes", "Diabetes", "0012-1797", 6.5, 2, "Q1", "内分泌代谢"),
    ("Obesity", "Obesity", "1930-7381", 4.7, 2, "Q2", "内分泌代谢"),
    ("Metabolism", "Metabolism", "0026-0495", 9.8, 2, "Q1", "内分泌代谢"),
    ("Thyroid", "Thyroid", "1050-7256", 5.5, 3, "Q2", "内分泌代谢"),
    ("Endocrine Reviews", "Endocr Rev", "0163-769X", 22.0, 1, "Q1", "内分泌代谢"),
    # ---------- 呼吸 ----------
    ("European Respiratory Journal", "Eur Respir J", "0903-1936", 17.0, 1, "Q1", "呼吸"),
    ("American Journal of Respiratory and Critical Care Medicine", "Am J Respir Crit Care Med", "1073-449X", 21.4, 1, "Q1", "呼吸"),
    ("Thorax", "Thorax", "0040-6376", 9.2, 1, "Q1", "呼吸"),
    ("Chest", "Chest", "0012-3692", 9.8, 2, "Q1", "呼吸"),
    ("Respiratory Research", "Respir Res", "1465-9921", 6.0, 3, "Q2", "呼吸"),
    ("European Respiratory Review", "Eur Respir Rev", "0905-9180", 10.0, 2, "Q1", "呼吸"),
    # ---------- 消化 ----------
    ("Gastroenterology", "Gastroenterology", "0016-5085", 25.7, 1, "Q1", "消化"),
    ("Gut", "Gut", "0017-5749", 23.0, 1, "Q1", "消化"),
    ("Journal of Hepatology", "J Hepatol", "0168-8278", 26.8, 1, "Q1", "消化"),
    ("Hepatology", "Hepatology", "0270-9139", 12.9, 1, "Q1", "消化"),
    ("American Journal of Gastroenterology", "Am J Gastroenterol", "0002-9270", 8.0, 2, "Q1", "消化"),
    ("Clinical Gastroenterology and Hepatology", "Clin Gastroenterol Hepatol", "1542-3565", 11.0, 1, "Q1", "消化"),
    ("Inflammatory Bowel Diseases", "Inflamm Bowel Dis", "1078-0998", 4.5, 3, "Q2", "消化"),
    # ---------- 肾脏 ----------
    ("Journal of the American Society of Nephrology", "J Am Soc Nephrol", "1046-6673", 10.3, 1, "Q1", "肾脏"),
    ("Kidney International", "Kidney Int", "0085-2538", 14.8, 1, "Q1", "肾脏"),
    ("Clinical Journal of the American Society of Nephrology", "Clin J Am Soc Nephrol", "1555-9041", 8.0, 2, "Q1", "肾脏"),
    ("Nephrology Dialysis Transplantation", "Nephrol Dial Transplant", "0931-0509", 4.8, 3, "Q2", "肾脏"),
    # ---------- 风湿免疫 ----------
    ("Annals of the Rheumatic Diseases", "Ann Rheum Dis", "0003-4967", 20.3, 1, "Q1", "风湿免疫"),
    ("Arthritis & Rheumatology", "Arthritis Rheumatol", "2326-5191", 10.9, 1, "Q1", "风湿免疫"),
    ("Rheumatology", "Rheumatology", "1462-0324", 4.8, 3, "Q2", "风湿免疫"),
    ("Lupus", "Lupus", "0961-2033", 2.7, 4, "Q3", "风湿免疫"),
    # ---------- 感染 ----------
    ("Clinical Infectious Diseases", "Clin Infect Dis", "1058-4838", 8.5, 2, "Q1", "感染"),
    ("Journal of Infectious Diseases", "J Infect Dis", "0022-1899", 4.5, 3, "Q2", "感染"),
    ("Lancet Infectious Diseases", "Lancet Infect Dis", "1473-3099", 31.0, 1, "Q1", "感染"),
    ("Emerging Infectious Diseases", "Emerg Infect Dis", "1080-6040", 8.4, 1, "Q1", "感染"),
    ("BMC Infectious Diseases", "BMC Infect Dis", "1471-2334", 3.5, 4, "Q3", "感染"),
    # ---------- 血液 ----------
    ("Blood", "Blood", "0006-4971", 21.0, 1, "Q1", "血液"),
    ("Leukemia", "Leukemia", "0887-6924", 12.8, 1, "Q1", "血液"),
    ("Haematologica", "Haematologica", "0390-6078", 9.4, 2, "Q1", "血液"),
    ("American Journal of Hematology", "Am J Hematol", "0361-8609", 10.0, 2, "Q1", "血液"),
    ("British Journal of Haematology", "Br J Haematol", "0007-1048", 5.5, 3, "Q2", "血液"),
    # ---------- 精神心理 ----------
    ("JAMA Psychiatry", "JAMA Psychiatry", "2168-622X", 22.5, 1, "Q1", "精神心理"),
    ("American Journal of Psychiatry", "Am J Psychiatry", "0002-953X", 13.5, 1, "Q1", "精神心理"),
    ("Molecular Psychiatry", "Mol Psychiatry", "1359-4184", 10.7, 1, "Q1", "精神心理"),
    ("Biological Psychiatry", "Biol Psychiatry", "0006-3223", 9.0, 2, "Q1", "精神心理"),
    ("Psychological Medicine", "Psychol Med", "0033-2917", 5.5, 3, "Q2", "精神心理"),
    # ---------- 妇产 ----------
    ("Obstetrics & Gynecology", "Obstet Gynecol", "0029-7844", 5.7, 2, "Q1", "妇产"),
    ("American Journal of Obstetrics and Gynecology", "Am J Obstet Gynecol", "0002-9378", 8.0, 2, "Q1", "妇产"),
    ("BJOG", "BJOG", "1470-0328", 5.0, 2, "Q2", "妇产"),
    ("Human Reproduction Update", "Hum Reprod Update", "1355-4786", 14.5, 1, "Q1", "妇产"),
    ("Fertility and Sterility", "Fertil Steril", "0015-0282", 4.8, 3, "Q2", "妇产"),
    # ---------- 儿科 ----------
    ("JAMA Pediatrics", "JAMA Pediatr", "2168-6203", 24.7, 1, "Q1", "儿科"),
    ("Pediatrics", "Pediatrics", "0031-4005", 7.2, 1, "Q1", "儿科"),
    ("Journal of Pediatrics", "J Pediatr", "0022-3476", 3.7, 3, "Q2", "儿科"),
    ("Archives of Disease in Childhood", "Arch Dis Child", "0003-9888", 4.0, 3, "Q2", "儿科"),
    ("Pediatric Research", "Pediatr Res", "0031-3998", 3.0, 4, "Q3", "儿科"),
    # ---------- 眼科 ----------
    ("Ophthalmology", "Ophthalmology", "0161-6420", 6.1, 1, "Q1", "眼科"),
    ("JAMA Ophthalmology", "JAMA Ophthalmol", "2168-6165", 8.0, 1, "Q1", "眼科"),
    ("American Journal of Ophthalmology", "Am J Ophthalmol", "0002-9394", 5.2, 2, "Q1", "眼科"),
    ("Investigative Ophthalmology & Visual Science", "Invest Ophthalmol Vis Sci", "0146-0404", 5.0, 2, "Q2", "眼科"),
    ("Retina", "Retina", "0275-004X", 4.6, 3, "Q2", "眼科"),
    ("British Journal of Ophthalmology", "Br J Ophthalmol", "0007-1161", 4.5, 2, "Q2", "眼科"),
    ("Progress in Retinal and Eye Research", "Prog Retin Eye Res", "1350-9462", 13.7, 1, "Q1", "眼科"),
    ("Eye", "Eye", "0950-222X", 3.0, 4, "Q3", "眼科"),
    # ---------- 耳鼻喉/口腔 ----------
    ("Laryngoscope", "Laryngoscope", "0023-852X", 2.8, 4, "Q3", "耳鼻喉/口腔"),
    ("Journal of Dental Research", "J Dent Res", "0022-0345", 6.0, 1, "Q1", "耳鼻喉/口腔"),
    ("Oral Oncology", "Oral Oncol", "1368-8375", 4.2, 3, "Q2", "耳鼻喉/口腔"),
    # ---------- 皮肤 ----------
    ("Journal of Investigative Dermatology", "J Invest Dermatol", "0022-202X", 5.7, 2, "Q1", "皮肤"),
    ("British Journal of Dermatology", "Br J Dermatol", "0007-0963", 10.0, 1, "Q1", "皮肤"),
    ("JAMA Dermatology", "JAMA Dermatol", "2168-6068", 10.5, 1, "Q1", "皮肤"),
    # ---------- 外科 ----------
    ("Annals of Surgery", "Ann Surg", "0003-4932", 9.0, 1, "Q1", "外科"),
    ("British Journal of Surgery", "Br J Surg", "0007-1323", 8.0, 2, "Q1", "外科"),
    ("JAMA Surgery", "JAMA Surg", "2168-6254", 14.0, 1, "Q1", "外科"),
    ("Journal of Vascular Surgery", "J Vasc Surg", "0741-5214", 4.3, 3, "Q2", "外科"),
    # ---------- 麻醉重症 ----------
    ("Critical Care Medicine", "Crit Care Med", "0090-3493", 7.4, 2, "Q1", "麻醉重症"),
    ("Intensive Care Medicine", "Intensive Care Med", "0342-4642", 17.0, 1, "Q1", "麻醉重症"),
    ("Anesthesiology", "Anesthesiology", "0003-3022", 8.8, 1, "Q1", "麻醉重症"),
    ("Critical Care", "Crit Care", "1364-8535", 8.8, 1, "Q1", "麻醉重症"),
    # ---------- 急诊全科 ----------
    ("Annals of Emergency Medicine", "Ann Emerg Med", "0196-0644", 5.2, 3, "Q2", "急诊全科"),
    ("Academic Emergency Medicine", "Acad Emerg Med", "1069-6563", 3.4, 4, "Q3", "急诊全科"),
    ("British Journal of General Practice", "Br J Gen Pract", "0960-1643", 4.0, 3, "Q2", "急诊全科"),
    ("Family Practice", "Fam Pract", "0263-2136", 2.4, 4, "Q3", "急诊全科"),
    # ---------- 影像 ----------
    ("Radiology", "Radiology", "0033-8419", 15.7, 1, "Q1", "影像"),
    ("European Radiology", "Eur Radiol", "0938-7994", 6.0, 2, "Q1", "影像"),
    ("American Journal of Roentgenology", "AJR Am J Roentgenol", "0361-803X", 4.7, 3, "Q2", "影像"),
    ("Journal of Magnetic Resonance Imaging", "J Magn Reson Imaging", "1053-1807", 4.3, 3, "Q2", "影像"),
    # ---------- 病理 ----------
    ("American Journal of Surgical Pathology", "Am J Surg Pathol", "0147-5185", 4.4, 3, "Q2", "病理"),
    ("Modern Pathology", "Mod Pathol", "0893-3952", 6.5, 2, "Q1", "病理"),
    ("Histopathology", "Histopathology", "0309-0167", 4.5, 3, "Q2", "病理"),
    ("Journal of Pathology", "J Pathol", "0022-3417", 6.0, 2, "Q1", "病理"),
    # ---------- 免疫过敏 ----------
    ("Journal of Allergy and Clinical Immunology", "J Allergy Clin Immunol", "0091-6749", 14.2, 1, "Q1", "免疫过敏"),
    ("Allergy", "Allergy", "0105-4538", 12.0, 1, "Q1", "免疫过敏"),
    ("Clinical & Experimental Allergy", "Clin Exp Allergy", "0954-7894", 4.2, 3, "Q2", "免疫过敏"),
    # ---------- 遗传基因组 ----------
    ("Nature Genetics", "Nat Genet", "1061-4036", 28.0, 1, "Q1", "遗传基因组"),
    ("American Journal of Human Genetics", "Am J Hum Genet", "0002-9297", 9.0, 1, "Q1", "遗传基因组"),
    ("Human Molecular Genetics", "Hum Mol Genet", "0964-6906", 4.5, 3, "Q2", "遗传基因组"),
    ("Genome Medicine", "Genome Med", "1741-7008", 11.0, 2, "Q1", "遗传基因组"),
    # ---------- 基础医学 ----------
    ("Journal of Clinical Investigation", "J Clin Invest", "0021-9738", 15.9, 1, "Q1", "基础医学"),
    ("Journal of Experimental Medicine", "J Exp Med", "0022-1007", 12.6, 1, "Q1", "基础医学"),
    ("EMBO Journal", "EMBO J", "0261-4189", 10.4, 1, "Q1", "基础医学"),
    ("FASEB Journal", "FASEB J", "0892-6638", 4.8, 3, "Q2", "基础医学"),
    # ---------- 细胞发育 ----------
    ("Cell", "Cell", "0092-8674", 64.5, 1, "Q1", "细胞发育"),
    ("Nature Cell Biology", "Nat Cell Biol", "1465-7392", 21.3, 1, "Q1", "细胞发育"),
    ("Cell Research", "Cell Res", "1001-0602", 25.9, 1, "Q1", "细胞发育"),
    ("Developmental Cell", "Dev Cell", "1534-5807", 10.7, 2, "Q1", "细胞发育"),
    # ---------- 药理 ----------
    ("Pharmacological Reviews", "Pharmacol Rev", "0031-6997", 19.3, 1, "Q1", "药理"),
    ("British Journal of Pharmacology", "Br J Pharmacol", "0007-1188", 5.5, 3, "Q2", "药理"),
    ("Clinical Pharmacology & Therapeutics", "Clin Pharmacol Ther", "0009-9236", 6.3, 2, "Q1", "药理"),
    # ---------- 方法学/交叉 ----------
    ("Trials", "Trials", "1745-6215", 2.7, 4, "Q3", "方法学"),
    ("BMJ Open", "BMJ Open", "2044-6055", 2.6, 4, "Q3", "方法学"),
    ("Scientific Reports", "Sci Rep", "2045-2322", 4.0, 3, "Q2", "方法学"),
    ("Nature Communications", "Nat Commun", "2041-1723", 14.7, 1, "Q1", "方法学"),
    ("Proceedings of the National Academy of Sciences of the United States of America", "Proc Natl Acad Sci U S A", "0027-8424", 9.4, 1, "Q1", "方法学"),
    ("eLife", "eLife", "2050-084X", 7.0, 2, "Q1", "方法学"),
    ("Journal of Clinical Epidemiology", "J Clin Epidemiol", "0895-4356", 5.0, 3, "Q2", "方法学"),
    ("Systematic Reviews", "Syst Rev", "2046-4053", 7.5, 2, "Q1", "方法学"),
    ("PLoS ONE", "PLoS One", "1932-6203", 3.7, 3, "Q2", "方法学"),
    # ---------- 医学信息/AI ----------
    ("npj Digital Medicine", "npj Digit Med", "2398-6352", 15.0, 1, "Q1", "医学信息"),
    ("Journal of Medical Internet Research", "J Med Internet Res", "1438-8871", 7.4, 2, "Q1", "医学信息"),
    ("Journal of Biomedical Informatics", "J Biomed Inform", "1532-0464", 3.5, 4, "Q3", "医学信息"),
    ("International Journal of Medical Informatics", "Int J Med Inform", "1386-5056", 3.7, 4, "Q3", "医学信息"),
    ("BMC Medical Informatics and Decision Making", "BMC Med Inform Decis Mak", "1472-6947", 3.5, 4, "Q3", "医学信息"),
    # ---------- 护理 ----------
    ("International Journal of Nursing Studies", "Int J Nurs Stud", "0020-7489", 6.5, 2, "Q1", "护理"),
    ("Journal of Advanced Nursing", "J Adv Nurs", "0309-2402", 3.8, 4, "Q2", "护理"),
    ("Nurse Education Today", "Nurse Educ Today", "0260-6917", 4.0, 3, "Q2", "护理"),
    # ---------- 运动康复 ----------
    ("British Journal of Sports Medicine", "Br J Sports Med", "0306-3674", 12.0, 1, "Q1", "运动康复"),
    ("Journal of Physiotherapy", "J Physiother", "1836-9553", 3.8, 3, "Q2", "运动康复"),
    ("Scandinavian Journal of Medicine & Science in Sports", "Scand J Med Sci Sports", "0905-7188", 4.0, 3, "Q2", "运动康复"),
    # ---------- 营养 ----------
    ("American Journal of Clinical Nutrition", "Am J Clin Nutr", "0002-9165", 7.0, 1, "Q1", "营养"),
    ("Nutrients", "Nutrients", "2072-6643", 5.0, 3, "Q2", "营养"),
    ("Journal of Nutrition", "J Nutr", "0022-3166", 4.0, 3, "Q2", "营养"),
    # ---------- 老年 ----------
    ("Age and Ageing", "Age Ageing", "0002-0729", 9.0, 2, "Q1", "老年"),
    ("Journals of Gerontology Series A: Biological Sciences and Medical Sciences", "J Gerontol A Biol Sci Med Sci", "1079-5006", 4.5, 3, "Q2", "老年"),
    # ---------- 疼痛 ----------
    ("Pain", "Pain", "0304-3959", 6.0, 2, "Q1", "疼痛"),
    ("Regional Anesthesia and Pain Medicine", "Reg Anesth Pain Med", "1098-7339", 5.0, 3, "Q2", "疼痛"),
    # ---------- 姑息/伦理 ----------
    ("Journal of Pain and Symptom Management", "J Pain Symptom Manage", "0885-3924", 4.0, 3, "Q2", "姑息/伦理"),
    ("BMC Medical Ethics", "BMC Med Ethics", "1472-6939", 2.5, 4, "Q3", "姑息/伦理"),
    # ---------- 中医药 ----------
    ("Chinese Journal of Integrative Medicine", "Chin J Integr Med", "1672-0415", 2.2, 4, "Q4", "中医药"),
    ("Phytomedicine", "Phytomedicine", "0944-7113", 6.7, 2, "Q1", "中医药"),
    # ---------- 中国期刊 ----------
    ("Chinese Medical Journal", "Chin Med J (Engl)", "0366-6999", 3.2, 4, "Q3", "中国期刊"),
    ("World Journal of Pediatrics", "World J Pediatr", "1867-0687", 4.2, 3, "Q2", "中国期刊"),
    ("Journal of Geriatric Cardiology", "J Geriatr Cardiol", "1671-5411", 2.8, 4, "Q3", "中国期刊"),
]


def main():
    journals = [
        {
            "name": name,
            "abbrev": abbr,
            "issn": issn,
            "if": if_,
            "cas": cas,
            "q": q,
            "cat": cat,
        }
        for name, abbr, issn, if_, cas, q, cat in JOURNALS
    ]
    data = {
        "meta": {
            "version": "v2026.10",
            "count": len(journals),
            "note": "静态示例库：IF 为约 2024 JCR 公开口径近似整理值，cas 为中科院大类分区，q 为 JCR 分区；生产环境请替换为权威数据源。",
            "generated_by": "data/build_journals.py",
        },
        "journals": journals,
    }
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "journals.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"written {out}: {len(journals)} journals")


if __name__ == "__main__":
    main()
