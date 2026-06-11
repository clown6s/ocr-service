"""结果导出工具 - 支持 TXT 和 Excel"""

import os
from datetime import datetime
from typing import List, Dict, Any


async def export_to_txt(results: List[Dict[str, Any]], output_dir: str) -> str:
    """导出为 TXT 文件"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(output_dir, f"ocr_result_{timestamp}.txt")

    with open(filepath, "w", encoding="utf-8") as f:
        for r in results:
            f.write(f"=== {r['filename']} ===\n")
            f.write(f"{r['full_text']}\n\n")

    return filepath


async def export_to_excel(results: List[Dict[str, Any]], output_dir: str) -> str:
    """导出为 Excel 文件"""
    try:
        from openpyxl import Workbook
    except ImportError:
        raise RuntimeError("需要 openpyxl：pip install openpyxl")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(output_dir, f"ocr_result_{timestamp}.xlsx")

    wb = Workbook()
    ws = wb.active
    ws.title = "OCR结果"

    # 表头
    headers = ["文件名", "引擎", "行号", "文字内容", "置信度"]
    ws.append(headers)

    for r in results:
        for idx, line in enumerate(r.get("lines", []), start=1):
            ws.append([
                r["filename"],
                r["engine"],
                idx,
                line["text"],
                line.get("confidence", 0),
            ])

    wb.save(filepath)
    return filepath


async def export_results(results: List[Dict[str, Any]], fmt: str, output_dir: str) -> str:
    """根据格式导出结果"""
    fmt = fmt.lower().replace(".", "")
    if fmt == "txt":
        return await export_to_txt(results, output_dir)
    elif fmt in ("xlsx", "excel"):
        return await export_to_excel(results, output_dir)
    else:
        raise ValueError(f"不支持的导出格式: {fmt}，可选: txt, xlsx")
