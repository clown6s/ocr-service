"""快速测试 OCR API 是否正常运行"""

import requests
import sys

BASE = "http://127.0.0.1:8000"


def test_health():
    resp = requests.get(f"{BASE}/health")
    print(f"[Health] {resp.json()}")
    assert resp.status_code == 200


def test_engines():
    resp = requests.get(f"{BASE}/api/v1/ocr/engines")
    print(f"[Engines] {resp.json()}")


def test_recognize(image_path: str):
    with open(image_path, "rb") as f:
        files = {"file": (image_path, f, "image/jpeg")}
        # 用 Tesseract 测试（不需要下载大模型）
        data = {"engine": "tesseract"}
        resp = requests.post(
            f"{BASE}/api/v1/ocr/recognize",
            files=files, data=data
        )
        result = resp.json()
        print(f"[OCR] 文件: {result['filename']}")
        print(f"      引擎: {result['engine']}")
        print(f"      行数: {len(result['lines'])}")
        if result['lines']:
            print(f"      前3行:")
            for line in result["lines"][:3]:
                print(f'        [{line[\"confidence\"]}] {line["text"]}')
        print(f"      全文:\n{result['full_text'][:200]}")


if __name__ == "__main__":
    print("=== OCR API 测试 ===\n")

    try:
        test_health()
        test_engines()

        image_path = sys.argv[1] if len(sys.argv) > 1 else "test.jpg"
        test_recognize(image_path)
        print("\n✅ 全部通过")
    except Exception as e:
        print(f"\n❌ 失败: {e}")
        sys.exit(1)
