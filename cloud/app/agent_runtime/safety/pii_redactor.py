"""Redacts PII (phone, ID, email, Chinese names) from text."""

import logging
import re

PHONE_PATTERN = re.compile(r"1[3-9]\d{9}")
ID_PATTERN = re.compile(r"\b[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]\b")
EMAIL_PATTERN = re.compile(r"\b[\w.+-]+@[\w-]+\.\w+\b")

_SURNAMES = frozenset(
    "李王张刘陈杨赵黄周吴徐孙马胡朱郭何罗高林郑梁谢唐许宋韩冯邓曹彭曾肖田董潘袁蔡蒋余于叶杜苏魏吕丁贾程沈任姚卢傅钟崔段谭廖金刚"
    "阎章汪范石姚谭邹熊金陆郝孔白崔康毛邱秦江史顾侯邵孟龙万段钱汤尹黎易常武乔贺赖龚"
)

_NONNAME_BIGRAMS = frozenset(
    {
        "文字",
        "文章",
        "文化",
        "文学",
        "文献",
        "文本",
        "文件",
        "方式",
        "方法",
        "方向",
        "社会",
        "金刚",
        "可以",
        "可能",
        "可是",
        "其他",
        "知道",
        "知识",
        "不同",
        "不是",
        "不要",
        "时候",
        "时间",
        "国家",
        "国外",
        "国内",
        "关系",
        "关于",
        "中心",
        "中间",
        "世界",
        "进行",
        "主要",
        "生产",
        "经济",
        "工作",
        "发展",
        "建设",
        "服务",
        "管理",
        "研究",
        "教育",
        "政府",
        "市场",
        "利益",
        "分析",
        "数据",
        "报告",
        "提供",
        "使用",
        "通过",
        "根据",
        "基础",
        "活动",
        "计划",
        "制度",
        "行为",
        "业务",
        "人员",
        "信息",
        "资源",
        "能力",
        "质量",
        "标准",
        "任务",
        "技术",
        "系统",
        "平台",
        "工具",
        "功能",
        "支持",
        "需求",
        "目标",
        "结果",
        "效果",
        "问题",
        "原因",
        "条件",
        "环境",
        "过程",
        "程序",
        "结构",
        "阶段",
        "方式",
    }
)


def _redact_name(text: str) -> str:
    """脱敏中文姓名：2字姓名脱第2字，3字姓名脱第2-3字。
    规则：姓氏 + 1-2 个中文字，
    - 前面是标点/空格/开头，或常见人物指示词尾（者、生、士、友、客、理、任、师、长等）
    - 后面是标点/空格/结尾，或常见动词/介词（的、了、已、和、在、会、是等）
    避免切碎普通词汇。"""
    _AFTER_NAME = frozenset("的了已在和就会是有被把对但可与要到没让从")
    _PREV_ALLOWED = frozenset(
        "者生士友客理任师长家医和与同跟了吗的"  # 患者、医生、先生、和、了、的...
    )
    result = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch in _SURNAMES:
            matched = False
            for length in (3, 2):
                if i + length > len(text):
                    continue
                candidate = text[i : i + length]
                if not all("\u4e00" <= c <= "\u9fa5" for c in candidate):
                    continue
                if length == 2 and candidate in _NONNAME_BIGRAMS:
                    continue
                # 前面不能是中文，除非是标点/指示词尾
                prev_char = text[i - 1] if i > 0 else ""
                prev_cjk = prev_char and "\u4e00" <= prev_char <= "\u9fa5"
                prev_ok = (
                    not prev_char  # 开头
                    or not prev_cjk  # 非中文
                    or prev_char in _PREV_ALLOWED
                )  # 指示词尾
                if not prev_ok:
                    continue
                # 后面不能是中文，除非是常见动词/介词
                next_char = text[i + length] if i + length < len(text) else ""
                next_cjk = next_char and "\u4e00" <= next_char <= "\u9fa5"
                if next_cjk and next_char not in _AFTER_NAME:
                    continue
                result.append(ch + "*" * (length - 1))
                i += length
                matched = True
                break
            if not matched:
                result.append(ch)
                i += 1
        else:
            result.append(ch)
            i += 1
    return "".join(result)


def redact(text: str) -> str:
    text = ID_PATTERN.sub("[ID]", text)
    text = PHONE_PATTERN.sub("[PHONE]", text)
    text = EMAIL_PATTERN.sub("[EMAIL]", text)
    text = _redact_name(text)
    return text


class PIIRedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.msg)
        return True
