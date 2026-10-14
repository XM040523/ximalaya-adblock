#!/usr/bin/env python3
"""从抓包产物里提取广告域名，生成 Loon 规则行。

支持任意文本输入：Loon 请求记录复制内容、mitmproxy/Charles 导出、tcpdump 输出、
甚至浏览器 DevTools 的 Network 面板复制内容。脚本只做域名抽取和特征打分，
不联网、不上报。

用法：
    python3 extract-ad-domains.py loon-log.txt
    pbpaste | python3 extract-ad-domains.py
    python3 extract-ad-domains.py loon-log.txt --json
"""

import argparse
import json
import re
import sys
from collections import Counter

# 域名总长上限，防止正则吃到畸形串
MAX_HOST_LEN = 253
HOST_RE = re.compile(r"\b((?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,24})\b")

# 强特征：命中即可判定为广告或统计基础设施
STRONG_TOKENS = (
    "adse", "adapi", "adserver", "adx", "adsystem", "adservice", "advert",
    "doubleclick", "googlesyndication", "googleadservices", "adnxs",
    "pangolin", "pangle", "oceanengine", "bytedance", "toutiao", "sgsnssdk",
    "gdt", "pgdt", "gdtv", "topon", "mintegral", "mbridge", "sigmob",
    "applovin", "inmobi", "chartboost", "vungle", "unityads", "ironsrc",
    "mobads", "ksad", "kwad", "admaster", "miaozhen", "talkingdata",
)

# 弱特征：单独出现不足以判定，需配合广告上下文
WEAK_TOKENS = ("splash", "banner", "promote", "promotion", "campaign", "ad_", "_ad", "ad-", "-ad")

# 统计/上报：拦掉只影响统计，不影响功能，默认单列一组
TELEMETRY_TOKENS = ("stat", "track", "report", "beacon", "analytics", "log", "monitor", "metric")

# 业务白名单：命中即跳过，避免打断核心功能
WHITELIST_SUFFIX = (
    "xmcdn.com",              # 音频与图片 CDN，泛解析，拦了直接断播
    "passport.ximalaya.com",  # 登录
    "api.ximalaya.com",
    "www.ximalaya.com",
    "m.ximalaya.com",
    "sourcemap.ximalaya.com",
    "open.ximalaya.com",
)

# 白名单匹配到这些后缀即放行（用于 xmcdn 这类整域保护的场景）
WHITELIST_DOMAIN = ("xmcdn.com",)


def extract_hosts(text: str) -> Counter:
    hosts = Counter()
    for line in text.splitlines():
        # 去掉端口，保留域名部分
        for raw in HOST_RE.findall(line):
            host = raw.strip(".").lower()
            if len(host) > MAX_HOST_LEN:
                continue
            if host.replace(".", "").isdigit():
                continue
            hosts[host] += 1
    return hosts


def classify(host: str):
    """返回 (分组, 依据)。分组为 ad / telemetry / unknown / whitelist。"""
    for suffix in WHITELIST_DOMAIN:
        if host == suffix or host.endswith("." + suffix):
            return "whitelist", f"业务域名 {suffix}"
    for suffix in WHITELIST_SUFFIX:
        if host == suffix or host.endswith("." + suffix):
            return "whitelist", f"业务域名 {suffix}"

    labels = host.split(".")
    for token in STRONG_TOKENS:
        if token in host:
            return "ad", f"强特征 {token}"
    # 标签级精确匹配：ad.ximalaya.com 这类纯 "ad" 标签靠子串规则抓不到
    ad_labels = {"ad", "ads", "adx", "adse", "adapi", "adserver", "advert", "advertising", "adservice"}
    for label in labels:
        if label in ad_labels:
            return "ad", f"标签 {label}"
    for token in WEAK_TOKENS:
        if token in host:
            return "ad", f"弱特征 {token}"
    for token in TELEMETRY_TOKENS:
        # 只认标签级命中，避免 "catalog" 里误命中 "log"
        if any(label == token or label.startswith(token) for label in labels):
            return "telemetry", f"统计特征 {token}"
    return "unknown", ""


def main() -> int:
    ap = argparse.ArgumentParser(description="从抓包产物提取广告域名并生成 Loon 规则")
    ap.add_argument("path", nargs="?", help="输入文件，省略则读 stdin")
    ap.add_argument("--json", action="store_true", help="以 JSON 输出，便于二次处理")
    ap.add_argument("--all", action="store_true", help="同时输出 unknown 组，供人工复核")
    args = ap.parse_args()

    text = open(args.path, encoding="utf-8", errors="replace").read() if args.path else sys.stdin.read()
    if not text.strip():
        print("输入为空。用法：python3 extract-ad-domains.py loon-log.txt", file=sys.stderr)
        return 2

    hosts = extract_hosts(text)
    buckets = {"ad": [], "telemetry": [], "unknown": [], "whitelist": []}
    for host, hits in hosts.most_common():
        group, reason = classify(host)
        buckets[group].append({"host": host, "hits": hits, "reason": reason})

    if args.json:
        json.dump({"total": len(hosts), "buckets": buckets}, sys.stdout, ensure_ascii=False, indent=2)
        print()
        return 0

    print(f"扫描到 {len(hosts)} 个域名\n")

    if buckets["ad"]:
        print("# ── 广告域名（可直接进 A/B 区）──")
        for item in buckets["ad"]:
            print(f"DOMAIN-SUFFIX,{item['host']},REJECT   # {item['reason']} ×{item['hits']}")
        print()

    if buckets["telemetry"]:
        print("# ── 统计上报（拦掉只影响统计，按需启用）──")
        for item in buckets["telemetry"]:
            print(f"# DOMAIN-SUFFIX,{item['host']},REJECT   # {item['reason']} ×{item['hits']}")
        print()

    if args.all and buckets["unknown"]:
        print("# ── 未分类（需人工确认用途后再决定）──")
        for item in buckets["unknown"]:
            print(f"# {item['host']}  ×{item['hits']}")
        print()

    if buckets["whitelist"]:
        print("# ── 已放行的业务域名（确认无误，勿拦）──")
        for item in buckets["whitelist"]:
            print(f"# {item['host']}  # {item['reason']}")
        print()

    print("提示：广告域名进插件 A 区（喜马拉雅自有）或 B 区（第三方平台）。")
    print("      统计域名建议先注释保留，确认不破坏功能后再启用。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
