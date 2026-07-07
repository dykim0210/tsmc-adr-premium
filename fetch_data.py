#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_data.py — GitHub Actions에서 실행되는 TSMC ADR 괴리율 데이터 파이프라인

- TSM (NYSE ADR, USD), 2330.TW (본주, TWD), TWD=X (USD/TWD) 전체 히스토리 수집
- 괴리율 = TSM / (2330 종가 * 5 / USDTWD) - 1   (1 ADR = 보통주 5주)
- 출력:
    data/tsmc_adr_premium.csv  : 전체 일별 시계열
    data/premium.json          : 대시보드용 (요약 통계 포함)

원칙: 주가 결측은 채우지 않음(환율만 최대 5영업일 ffill), 추정치 생성 금지,
      괴리율 정상범위(-50% ~ +60%) 이탈 시 경고, 데이터 없으면 실패 처리.
"""

import json
import os
import sys
import time

import pandas as pd
import yfinance as yf

START = "1997-10-08"          # TSM ADR 상장일
ADR_RATIO = 5                 # 1 ADR = 보통주 5주
SANITY = (-0.50, 0.60)        # 괴리율 정상범위
OUT_DIR = "data"


def fetch(ticker: str, retries: int = 3, wait: int = 20) -> pd.Series:
    """종가 시계열 수집. 실패 시 재시도, 최종 실패 시 예외."""
    last_err = None
    for i in range(retries):
        try:
            df = yf.download(ticker, start=START, auto_adjust=False,
                             progress=False)
            if df is not None and not df.empty:
                close = df["Close"]
                if isinstance(close, pd.DataFrame):
                    close = close.iloc[:, 0]
                close = close.dropna()
                close.index = (pd.to_datetime(close.index)
                               .tz_localize(None).normalize())
                close.name = ticker
                print(f"[OK] {ticker}: {close.index.min().date()} ~ "
                      f"{close.index.max().date()} ({len(close)}일)")
                return close
        except Exception as e:  # noqa: BLE001
            last_err = e
        print(f"[재시도 {i+1}/{retries}] {ticker} ... ({last_err})")
        time.sleep(wait)
    raise RuntimeError(f"{ticker} 데이터 수집 실패: {last_err}")


def main():
    tsm = fetch("TSM")        # ADR (USD)
    tw = fetch("2330.TW")     # 본주 (TWD)
    fx = fetch("TWD=X")       # USD/TWD

    df = pd.concat({"tsm_usd": tsm, "twse_twd": tw, "usdtwd": fx}, axis=1)
    df = df.sort_index()
    # 환율만 휴장일 대비 전일값 사용 (최대 5영업일). 주가는 채우지 않음.
    df["usdtwd"] = df["usdtwd"].ffill(limit=5)

    # ADR 종가가 있는 날만 남김 (미국 거래일 기준 시계열)
    df = df.dropna(subset=["tsm_usd"])

    both = df["twse_twd"].notna() & df["usdtwd"].notna()
    df.loc[both, "twse_usd_per_adr"] = (
        df.loc[both, "twse_twd"] * ADR_RATIO / df.loc[both, "usdtwd"])
    df.loc[both, "premium"] = (
        df.loc[both, "tsm_usd"] / df.loc[both, "twse_usd_per_adr"] - 1.0)

    # --- 불량 틱 필터링 ---
    # (1) 절대 범위: 차익거래 구조상 불가능한 수준의 괴리율
    lo, hi = SANITY
    bad = (df["premium"] < lo) | (df["premium"] > hi)
    # (2) 상대 기준: 21일 롤링 중앙값 대비 30%p 이상 이탈 (단일 불량 틱 감지)
    med = df["premium"].rolling(21, center=True, min_periods=5).median()
    bad = bad | ((df["premium"] - med).abs() > 0.30)
    if bad.any():
        for d in df.index[bad]:
            print(f"[제외] {d.date()} 괴리율 {df.loc[d, 'premium']:+.1%} "
                  f"— 불량 틱으로 판단, 통계/차트에서 제외")
        df.loc[bad, ["twse_usd_per_adr", "premium"]] = float("nan")

    df["premium_ma60"] = df["premium"].rolling(60, min_periods=30).mean()

    valid = df["premium"].dropna()
    if valid.empty:
        sys.exit("[실패] 괴리율 계산 가능한 데이터가 없음")

    os.makedirs(OUT_DIR, exist_ok=True)
    df.round(4).to_csv(f"{OUT_DIR}/tsmc_adr_premium.csv",
                       index_label="date", encoding="utf-8-sig")

    def col(name, nd=2):
        return [None if pd.isna(v) else round(float(v), nd)
                for v in df[name]]

    one_year = valid[valid.index >= valid.index.max() - pd.Timedelta(days=365)]

    payload = {
        "updated": pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%d %H:%M UTC"),
        "premium_start": str(valid.index.min().date()),
        "dates": [d.strftime("%Y-%m-%d") for d in df.index],
        "tsm": col("tsm_usd"),
        "local": col("twse_usd_per_adr"),
        "premium_pct": [None if pd.isna(v) else round(float(v) * 100, 2)
                        for v in df["premium"]],
        "premium_ma60_pct": [None if pd.isna(v) else round(float(v) * 100, 2)
                             for v in df["premium_ma60"]],
        "stats": {
            "latest_date": str(valid.index[-1].date()),
            "latest": round(float(valid.iloc[-1]) * 100, 2),
            "mean": round(float(valid.mean()) * 100, 2),
            "median": round(float(valid.median()) * 100, 2),
            "mean_1y": round(float(one_year.mean()) * 100, 2),
            "max": round(float(valid.max()) * 100, 2),
            "max_date": str(valid.idxmax().date()),
            "min": round(float(valid.min()) * 100, 2),
            "min_date": str(valid.idxmin().date()),
        },
    }
    with open(f"{OUT_DIR}/premium.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)

    s = payload["stats"]
    print(f"\n[요약] 최근 {s['latest']:+.2f}% ({s['latest_date']}) | "
          f"전체평균 {s['mean']:+.2f}% | 1년평균 {s['mean_1y']:+.2f}% | "
          f"최대 {s['max']:+.2f}% ({s['max_date']}) | "
          f"최소 {s['min']:+.2f}% ({s['min_date']})")
    print(f"[완료] 괴리율 시계열 시작일: {payload['premium_start']}")


if __name__ == "__main__":
    main()
