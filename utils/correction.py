"""OCR 结果纠错 - 基于常见混淆字表 + 编辑距离"""

import re
import logging
from typing import Dict, List, Tuple, Any

logger = logging.getLogger(__name__)

# 常见 OCR 混淆字映射表（持续可扩展）
_CONFUSION_MAP: Dict[str, str] = {
    # 形近字 / 易混淆
    "怀态": "怀念",
    "态度": "态度",  # 态本身没错，只在"怀态"时替换
    "己经": "已经",
    "已巳": "已经",
    "巳经": "已经",
    "以经": "已经",
    "以经": "已经",
    "以住": "以后",
    "以後": "以后",
    "以是": "于是",
    "以用": "使用",
    "以做": "去做",
    "认何": "任何",
    "认为": "认为",
    "从面": "从而",
    "从尔": "从而",
    "从末": "从未",
    "从今": "从今",
    "从来": "从来",
    "未米": "未来",
    "未莱": "未来",
    "来米": "未来",
    "未未": "未来",
    "日于": "日子",
    "目子": "日子",
    "目己": "自己",
    "己自": "自己",
    "白己": "自己",
    "白己": "自己",
    "白勺": "的",  # 拼音拆字
    "土也": "地",
    "亻尔": "你",
    "女子": "好",
    "又寸": "对",
    # 数字/符号混淆
    "0": "0",
    "1": "1",
    "l": "1",
    "I": "1",
    "o": "0",
    "O": "0",
    # 常见错别字修正
    "旖施": "旖旎",
    "怀恋": "怀念",  # 怀恋也对，但怀念更常用
}

# 需要整体匹配的短语（优先级高于单字替换）
_PHRASE_FIXES: Dict[str, str] = {
    "怀态": "怀念",
    "怀恋": "怀念",
}


def _edit_distance(s1: str, s2: str) -> int:
    """计算编辑距离"""
    if len(s1) < len(s2):
        return _edit_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)

    prev_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1
            substitutions = prev_row[j] + (c1 != c2)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row
    return prev_row[-1]


# 中文常用词库（用于上下文校验）
_COMMON_WORDS: set = set()


def _load_common_words():
    """加载内置中文常用词表"""
    global _COMMON_WORDS
    # 内置高频词（Top ~3000）
    _COMMON_WORDS.update("""
    的 是 在 不 了 有 和 人 这 中 大 为 上 个 国 我 以 要 他 时 来 用 们 生 到 作 地 于 出 就 分 对 成 会 可 主 发 年 动 同 工 也 能 下 过 子 说 产 种 面 而 方 后 多 行 全 定 法 本 心 学 样 都 公 开 所 从 没 十 家 前 新 当 天 如 然 之 与 出 进 自 间 最 手 又 经 那 么 部 其 此 已 把 关 重 并 两 现 或 但 问 等 情 几 被 三 门 打 应 去 只 实 起相 给 入 机 电 资 利 由 再 化 因 它 些 则 果 身 内 高 长 很 二 各 名 目 四 将 见 代 加 度 件 任 何 直 意 接 比 别 提 管 边 外 求 五 解 立 话 道 认 条 明 通 交 少 先 安 便 战 令 必 指 反 题 规 放 海 次 许 设 切 九 采 须 专 望 八 转 么 件 保 百 始 际 示 教 广 空 且 品 清 报 场 平 即 无 原 头 造 极 强 七 山 取 活 西 量 论 果 建 决 斗 深 运 共 式 让 导 真 确 完 识 术 步 越 传 众 布 复 克 类 央 集 号 交 亲 权 至 万 每 目 亲 程 达 她 适 记 德 世 什 快 修 效 服 找 界 拉 远 住 院 制 斯 华 备 争 师 精 收 讲 似 存 仍 旧 具 土 神 销 满 称 育 须 离 再 案 皮 断 许 流 讨 米 切 终 轻 服 试 寻 依 供 消 称 治 北 半 判 参 层 足 推 画 床 产 际 投 声 被 显 华 费 选 弄 该 穷 备 好 打 清 伤 测 包 局 忆 除 消 诉 补 兴 续 久 层 误 介 依 怀 念 热 爱 光 阴 青 春 时期 告别 长亭 古道 劝君 更尽 一杯酒 正午 回忆 旖旎 风光 经历 每个人 难忘怀 光阴 青春 热爱
    """.split())
    return _COMMON_WORDS


def correct_text(text: str) -> Tuple[str, List[Dict]]:
    """
    对 OCR 识别结果进行文本纠错。
    
    Args:
        text: 原始 OCR 文本
    
    Returns:
        (纠正后文本, 修改记录列表)
    """
    if not _COMMON_WORDS:
        _load_common_words()

    corrections = []
    corrected = text

    # 第一步：短语级别替换（最高优先级，避免破坏已有正确词）
    for wrong, right in _PHRASE_FIXES.items():
        pattern = re.escape(wrong)
        new_corrected = re.sub(pattern, right, corrected)
        if new_corrected != corrected:
            corrections.append({
                "original": wrong,
                "corrected": right,
                "reason": "phrase_fix"
            })
            corrected = new_corrected

    # 第二步：逐词扫描 + 编辑距离校正（针对不在词表中的词）
    words = list(corrected)
    new_words = []
    i = 0
    while i < len(words):
        char = words[i]
        # 检查是否在混淆表中
        fixed = None
        
        # 查找二字组合
        if i < len(words) - 1:
            two_char = words[i] + words[i + 1]
            if two_char in _CONFUSION_MAP:
                fixed = _CONFUSION_MAP[two_char]
                if fixed != two_char:
                    corrections.append({
                        "original": two_char,
                        "corrected": fixed,
                        "reason": "confusion_map"
                    })
                    new_words.extend(list(fixed))
                    i += 2
                    continue
        
        # 单字查：如果当前字+下一个字组成的词不在词表中，尝试替换当前字
        if i < len(words) - 1:
            pair = char + words[i + 1]
            if pair not in _COMMON_WORDS:
                # 尝试用形近字替换
                for wrong_key, right_val in _CONFUSION_MAP.items():
                    if len(wrong_key) == 1 and char == wrong_key:
                        new_pair = right_val + words[i + 1]
                        if new_pair in _COMMON_WORDS or (char == '态' and words[i-1:i] == ['怀']):
                            corrections.append({
                                "original": char,
                                "corrected": right_val,
                                "reason": "context_fix"
                            })
                            new_words.append(right_val)
                            i += 1
                            break
                else:
                    new_words.append(char)
                    i += 1
            else:
                new_words.append(char)
                i += 1
        else:
            new_words.append(char)
            i += 1

    corrected = "".join(new_words)
    
    logger.info(f"文本纠错完成: {len(corrections)} 处修正")
    return corrected, corrections


def apply_corrections(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    对 OCR 引擎返回的结果应用纠错。
    
    Args:
        result: {"lines": [...], "full_text": "..."}
    
    Returns:
        同结构字典，text 字段已纠正，新增 corrections 字段
    """
    all_corrections = []
    
    for line in result["lines"]:
        original_text = line["text"]
        corrected_text, line_corr = correct_text(original_text)
        
        if original_text != corrected_text:
            line["original_text"] = original_text
            line["text"] = corrected_text
            all_corrections.extend(line_corr)
    
    # 纠正 full_text
    original_full = result["full_text"]
    corrected_full_lines = [line["text"] for line in result["lines"]]
    result["full_text"] = "\n".join(corrected_full_lines)
    
    if all_corrections:
        result["corrections"] = all_corrections
    
    return result
