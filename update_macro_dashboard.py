import csv
import io
import os
import re
from datetime import datetime
import requests
import yfinance as yf

HTML_FILE = "index.html"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def fetch_fred_series(series_id: str) -> list[tuple[str, float]]:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    rows = []
    reader = csv.reader(io.StringIO(resp.text))
    next(reader, None)
    for row in reader:
        if len(row) >= 2 and row[1] not in ("", "."):
            try:
                rows.append((row[0], float(row[1])))
            except ValueError:
                continue
    return rows


def fetch_yf_latest(ticker: str) -> float:
    data = yf.Ticker(ticker).history(period="5d")
    if data.empty:
        raise ValueError(f"無法取得 {ticker} 報價")
    return float(data["Close"].dropna().iloc[-1])


def collect_indicators() -> dict[str, float]:
    results = {}

    try:
        payems = fetch_fred_series("PAYEMS")
        results["in-nfp"] = round(payems[-1][1] - payems[-2][1], 1)
    except Exception as e:
        print(f"[略過] NFP 抓取失敗: {e}")

    try:
        unrate = fetch_fred_series("UNRATE")
        results["in-unemp"] = round(unrate[-1][1], 1)
    except Exception as e:
        print(f"[略過] 失業率抓取失敗: {e}")

    try:
        cpi = fetch_fred_series("CPIAUCSL")
        cpi_yoy = (cpi[-1][1] / cpi[-13][1] - 1) * 100
        results["in-cpi"] = round(cpi_yoy, 1)
    except Exception as e:
        print(f"[略過] CPI 抓取失敗: {e}")

    try:
        fed = fetch_fred_series("DFF")
        results["in-fed"] = round(fed[-1][1], 2)
    except Exception as e:
        print(f"[略過] Fed 利率抓取失敗: {e}")

    try:
        curve = fetch_fred_series("T10Y2Y")
        results["in-curve"] = round(curve[-1][1], 2)
    except Exception as e:
        print(f"[略過] 10Y-2Y 利差抓取失敗: {e}")

    try:
        hy = fetch_fred_series("BAMLH0A0HYM2")
        results["in-hy"] = round(hy[-1][1], 2)
    except Exception as e:
        print(f"[略過] 高收益債利差抓取失敗: {e}")

    yf_map = {
        "in-tnx": ("^TNX", 2),
        "in-vix": ("^VIX", 1),
        "in-dxy": ("DX-Y.NYB", 1),
        "in-twd": ("TWD=X", 2),
    }
    for input_id, (ticker, digits) in yf_map.items():
        try:
            results[input_id] = round(fetch_yf_latest(ticker), digits)
        except Exception as e:
            print(f"[略過] {ticker} 抓取失敗: {e}")

    return results


def inject_into_html(html_path: str, data: dict[str, float]) -> None:
    if not os.path.exists(html_path):
        raise FileNotFoundError(f"找不到 {html_path}")

    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    for input_id, val in data.items():
        pattern = rf'(<input[^>]*id="{re.escape(input_id)}"[^>]*value=")[^"]*(")'
        html, count = re.subn(pattern, rf"\g<1>{val}\g<2>", html, count=1)
        if count:
            print(f"  ✓ {input_id:<10} ➔ {val}")

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    html = re.sub(
        r"基準數據：[^<]+",
        f"基準數據：Python 自動同步（{now_str}）",
        html,
        count=1,
    )

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)


if __name__ == "__main__":
    print("開始抓取 FRED 與 Yahoo Finance 最新總經指標...")
    latest_data = collect_indicators()
    if latest_data:
        inject_into_html(HTML_FILE, latest_data)
        print("完成更新 index.html")
