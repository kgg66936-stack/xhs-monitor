#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import re
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent
INDEX_HTML = BASE_DIR / "index.html"
PRODUCTS_FILE = BASE_DIR / "products.json"

HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "zh-CN,zh;q=0.9",
    "detail-host": "https://www.xiaohongshu.com",
    "origin": "https://www.xiaohongshu.com",
    "referer": "https://www.xiaohongshu.com/",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
}


def extract_item_id(url):
    m = re.search(r"/goods-detail/([a-f0-9]+)", url)
    return m.group(1) if m else None


def parse_sales_number(text):
    """把 '已售218' 或 '已售 1.5万' 转成整数"""
    if not text:
        return 0
    text = text.replace("已售", "").replace(" ", "").strip()
    if "万" in text:
        return int(float(text.replace("万", "")) * 10000)
    try:
        return int(text)
    except ValueError:
        return 0


def fetch_product(item_id, xsec_token=None):
    url = (
        f"https://mall.xiaohongshu.com/api/store/jpd/edith/detail/h5/toc"
        f"?version=0.0.5&item_id={item_id}&xsec_source=app_share"
    )
    if xsec_token:
        url += f"&xsec_token={urllib.parse.quote(xsec_token)}"

    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError) as e:
        print(f"  [错误] 抓取失败: {e}")
        return None

    template_data = data.get("data", {}).get("template_data", [])
    if not template_data:
        print("  [错误] 接口返回数据为空")
        return None

    obj = template_data[0]
    price_h5 = obj.get("priceH5") or {}
    seller_h5 = obj.get("sellerH5") or {}
    desc_main = obj.get("descriptionMain") or {}

    name = desc_main.get("name") or "未知商品"
    price = price_h5.get("highlightPrice") or 0
    sales_text = price_h5.get("itemAnalysisDataText") or ""
    sales = parse_sales_number(sales_text)
    shop_name = seller_h5.get("name") or ""
    shop_url = seller_h5.get("link") or ""
    shop_sales_text = seller_h5.get("salesVolume") or ""

    return {
        "name": name,
        "price": price,
        "sales": sales,
        "salesText": sales_text,
        "shopName": shop_name,
        "shopUrl": shop_url,
        "shopSalesText": shop_sales_text,
    }


def load_products():
    if not PRODUCTS_FILE.exists():
        return []
    with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_products(products):
    with open(PRODUCTS_FILE, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)


def today_str():
    return datetime.now().strftime("%Y-%m-%d")


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def run_scrape():
    products = load_products()
    if not products:
        print("products.json 为空，没有需要抓取的商品")
        return

    now = now_str()
    today = today_str()
    changed = False

    for p in products:
        item_id = p.get("id")
        print(f"正在抓取: {p.get('name') or item_id}")

        result = fetch_product(item_id, p.get("xsecToken"))
        if result is None:
            print("  跳过（保留旧数据）")
            continue

        # 更新商品基础信息
        p["name"] = result["name"]
        p["price"] = result["price"]
        p["shopName"] = result["shopName"]
        p["shopUrl"] = result["shopUrl"]
        p["shopSalesText"] = result["shopSalesText"]

        # 追加历史记录
        if "history" not in p:
            p["history"] = []

        p["history"].append({
            "time": now,
            "date": today,
            "sales": result["sales"],
            "salesText": result["salesText"],
        })

        print(f"  {result['salesText']}  价格: ￥{result['price']}  店铺: {result['shopName']}")
        changed = True

    if changed:
        save_products(products)
        write_to_html(products)
        print(f"\n完成，数据已写入 index.html")


def write_to_html(products):
    if not INDEX_HTML.exists():
        print(f"[警告] {INDEX_HTML} 不存在，跳过写入")
        return

    content = INDEX_HTML.read_text(encoding="utf-8")
    data_block = json.dumps(products, ensure_ascii=False, indent=2)
    replacement = f"window.__XHS_DATA__ = {data_block};"

    # 替换 <script id="xhs-data"> 和 </script> 之间的内容
    pattern = r'(<script id="xhs-data">)(.*?)(</script>)'
    new_content = re.sub(
        pattern,
        lambda m: m.group(1) + "\n" + replacement + "\n" + m.group(3),
        content,
        flags=re.DOTALL,
    )

    if new_content == content:
        print("[警告] index.html 中未找到 <script id=\"xhs-data\"> 标签，数据未写入")
    else:
        INDEX_HTML.write_text(new_content, encoding="utf-8")


if __name__ == "__main__":
    import urllib.parse
    run_scrape()
