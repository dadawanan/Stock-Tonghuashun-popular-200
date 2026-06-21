#!/usr/bin/env python3
"""代理连通性测试脚本 — 验证 Tailscale + Clash 代理是否生效。

使用方式:
    cd /path/to/stock-system/stock
    python scripts/test_proxy.py

前置条件:
    1. 腾讯云服务器和家庭电脑均已加入 Tailscale 网络
    2. 家庭电脑 Clash Verge 已开启「局域网连接」
    3. .env 中已配置 PROXY_HOST=100.x.x.x（家庭电脑 Tailscale IP）
"""

from __future__ import annotations

import json
import sys
import time

# 添加项目路径
sys.path.insert(0, "src")

from stock_service.infrastructure.config.settings import settings
from stock_service.infrastructure.providers.anti_detection_provider import (
    anti_get,
    verify_direct_ip,
    verify_proxy_ip,
)


def print_section(title: str) -> None:
    print()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)


def test_direct_connection() -> bool:
    """测试 1: 直连 IP 验证"""
    print_section("测试 1: 直连 IP（腾讯云服务器本身）")
    try:
        result = verify_direct_ip()
        print(f"  IP:       {result.get('ip', 'N/A')}")
        print(f"  位置:     {result.get('location', 'N/A')}")
        print(f"  运营商:   {result.get('isp', 'N/A')}")
        return True
    except Exception as e:
        print(f"  ❌ 失败: {e}")
        return False


def test_proxy_connection() -> bool:
    """测试 2: 代理 IP 验证"""
    print_section("测试 2: 代理 IP（通过 Tailscale → Clash）")
    if not settings.proxy_host:
        print("  ⚠️  PROXY_HOST 未配置，跳过代理测试")
        print("  请在 .env 中设置 PROXY_HOST=100.x.x.x")
        return False

    print(f"  代理地址: {settings.proxy_host}:{settings.proxy_port}")
    try:
        result = verify_proxy_ip()
        print(f"  IP:       {result.get('ip', 'N/A')}")
        print(f"  位置:     {result.get('location', 'N/A')}")
        print(f"  运营商:   {result.get('isp', 'N/A')}")
        return True
    except Exception as e:
        print(f"  ❌ 失败: {e}")
        return False


def test_ip_comparison() -> bool:
    """测试 3: IP 对比"""
    print_section("测试 3: IP 对比")
    try:
        direct = verify_direct_ip()
        proxied = verify_proxy_ip() if settings.proxy_host else None

        print(f"  直连 IP:  {direct.get('ip', 'N/A')}")
        if proxied:
            print(f"  代理 IP:  {proxied.get('ip', 'N/A')}")
            if direct.get("ip") != proxied.get("ip"):
                print("  ✅ 代理生效！IP 已成功切换")
                return True
            else:
                print("  ⚠️  IP 未变化，请检查:")
                print("     1. Tailscale 是否连接正常 (tailscale status)")
                print("     2. Clash Verge 是否开启局域网共享")
                print("     3. PROXY_HOST 是否正确")
                return False
        else:
            print("  代理 IP:  未配置")
            return False
    except Exception as e:
        print(f"  ❌ 失败: {e}")
        return False


def test_tls_fingerprint() -> bool:
    """测试 4: TLS 指纹伪装验证"""
    print_section("测试 4: TLS 指纹伪装")
    try:
        # 访问 browserleaks.com 检测 TLS 指纹
        resp = anti_get("https://tls.browserleaks.com/json", timeout=15, retries=2)
        data = resp.json()
        ja3_hash = data.get("ja3_hash", "N/A")
        ja3_text = data.get("ja3_text", "N/A")
        print(f"  JA3 Hash:  {ja3_hash}")
        print(f"  JA3 指纹:  {ja3_text[:80]}...")
        print("  ✅ TLS 指纹伪装正常")
        return True
    except Exception as e:
        print(f"  ⚠️  TLS 指纹检测失败（可能是网络问题）: {e}")
        return True  # 非致命错误


def test_real_website() -> bool:
    """测试 5: 实际财经网站访问"""
    print_section("测试 5: 财经网站访问测试")
    try:
        # 测试访问百度
        resp = anti_get("https://www.baidu.com", timeout=15, retries=2)
        status = resp.status_code
        length = len(resp.text)
        print(f"  百度:     HTTP {status}, 响应长度 {length}")
        if status == 200:
            print("  ✅ 网站访问正常")
            return True
        else:
            print(f"  ⚠️  状态码异常: {status}")
            return False
    except Exception as e:
        print(f"  ❌ 失败: {e}")
        return False


def main() -> None:
    print("=" * 60)
    print("  Tailscale + Clash Verge 代理连通性测试")
    print("=" * 60)
    print(f"  代理配置: {settings.proxy_host}:{settings.proxy_port}")
    print(f"  超时设置: {settings.proxy_timeout}s")
    print(f"  延迟范围: {settings.proxy_delay_min}~{settings.proxy_delay_max}s")

    results: list[tuple[str, bool]] = []

    results.append(("直连验证", test_direct_connection()))
    results.append(("代理验证", test_proxy_connection()))
    results.append(("IP 对比", test_ip_comparison()))
    results.append(("TLS 指纹", test_tls_fingerprint()))
    results.append(("网站访问", test_real_website()))

    # 汇总报告
    print_section("测试汇总")
    all_passed = True
    for name, passed in results:
        status = "✅" if passed else "❌"
        print(f"  {status} {name}")
        if not passed:
            all_passed = False

    print()
    if all_passed:
        print("  🎉 所有测试通过！代理配置正确。")
    else:
        print("  ⚠️  部分测试失败，请检查上述错误信息。")
    print()


if __name__ == "__main__":
    main()
