"""防检测 HTTP 请求模块 — 通过 Tailscale 代理 + TLS 指纹伪装规避反爬。

架构说明:
    腾讯云服务器 ──Tailscale VPN──> 家庭电脑 (Clash Verge) ──> 互联网
    利用家庭住宅 IP 替代机房 IP，同时伪装 Chrome 浏览器 TLS 指纹。

代理策略:
    - 默认仅对财经网站走代理（域名白名单）
    - 其他请求直连，节省家庭带宽
    - 可通过 use_proxy 参数覆盖默认行为

使用方式:
    from stock_service.infrastructure.providers.anti_detection_provider import (
        anti_get,
        async_anti_get,
        verify_proxy_ip,
    )
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Any
from urllib.parse import urlparse

from curl_cffi import requests as curl_requests

from stock_service.infrastructure.config.settings import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 代理域名白名单 — 只有这些域名才走 Tailscale 代理
# 其他域名直连，节省家庭带宽
# ---------------------------------------------------------------------------
PROXY_DOMAIN_WHITELIST: set[str] = {
    # 东方财富
    "eastmoney.com",
    "push2.eastmoney.com",
    "quote.eastmoney.com",
    "data.eastmoney.com",
    "flow.eastmoney.com",
    # 同花顺
    "10jqka.com.cn",
    "www.10jqka.com.cn",
    "basic.10jqka.com.cn",
    "stockpage.10jqka.com.cn",
    # 新浪财经
    "sina.com.cn",
    "finance.sina.com.cn",
    "vip.stock.finance.sina.com.cn",
    # 腾讯财经
    "qq.com",
    "stockapp.finance.qq.com",
    # 雪球
    "xueqiu.com",
    "xueqiu.com.cn",
    # 银行间
    "chinamoney.com.cn",
    # 深交所/上交所
    "szse.cn",
    "sse.com.cn",
}


def _should_use_proxy(url: str) -> bool:
    """判断 URL 是否应该走代理。

    规则:
        1. 如果 use_proxy 参数显式指定，使用该值
        2. 如果 PROXY_HOST 未配置，不走代理
        3. 如果 URL 域名在白名单中，走代理
        4. 其他情况不走代理
    """
    if not settings.proxy_host:
        return False

    try:
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
        # 检查域名是否匹配白名单（支持子域名）
        return any(
            hostname == domain or hostname.endswith(f".{domain}")
            for domain in PROXY_DOMAIN_WHITELIST
        )
    except Exception:
        return False

# ---------------------------------------------------------------------------
# 浏览器配置池 — TLS 指纹与 User-Agent 必须配对
# 每个元组: (curl_cffi impersonate 名称, 对应的 Chrome UA 字符串)
# ---------------------------------------------------------------------------
_BROWSER_PROFILES: list[tuple[str, str]] = [
    (
        "chrome110",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
    ),
    (
        "chrome116",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
    ),
    (
        "chrome120",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    ),
    (
        "chrome124",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    ),
    (
        "chrome131",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    ),
]

# ---------------------------------------------------------------------------
# 默认请求头模板
# ---------------------------------------------------------------------------
_BASE_HEADERS: dict[str, str] = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}


def _build_proxies(url: str | None = None) -> dict[str, str] | None:
    """从 Settings 读取代理配置，构建 curl_cffi 使用的 proxies 字典。

    Args:
        url: 目标 URL，用于域名白名单判断。如果提供且不在白名单中，返回 None。

    Returns:
        {"http": "http://100.x.x.x:7890", "https": "http://100.x.x.x:7890"}
        如果未配置代理或域名不在白名单中则返回 None。
    """
    host = settings.proxy_host
    port = settings.proxy_port
    if not host:
        return None

    # 如果提供了 URL，检查是否在白名单中
    if url is not None and not _should_use_proxy(url):
        logger.debug("域名不在代理白名单中，直连: %s", url)
        return None

    proxy_url = f"http://{host}:{port}"
    return {"http": proxy_url, "https": proxy_url}


def _random_profile() -> tuple[str, str]:
    """随机选择一个配对的 (impersonate, user_agent)。"""
    return random.choice(_BROWSER_PROFILES)


def _random_headers(extra: dict[str, str] | None = None) -> tuple[str, dict[str, str]]:
    """生成带随机 User-Agent 的请求头。

    Returns:
        (impersonate, headers) 元组，impersonate 与 UA 已配对。
    """
    impersonate, ua = _random_profile()
    headers = {**_BASE_HEADERS, "User-Agent": ua}
    if extra:
        headers.update(extra)
    return impersonate, headers


def _random_delay(min_sec: float | None = None, max_sec: float | None = None) -> None:
    """随机延迟，模拟人类操作间隔。

    默认 0.3~1.2 秒，可通过 settings 配置覆盖。
    """
    lo = min_sec if min_sec is not None else settings.proxy_delay_min
    hi = max_sec if max_sec is not None else settings.proxy_delay_max
    # 防止用户误配 min > max
    lo, hi = min(lo, hi), max(lo, hi)
    delay = random.uniform(lo, hi)
    if delay > 0:
        time.sleep(delay)


# ---------------------------------------------------------------------------
# cip.cc 响应解析（公共逻辑）
# ---------------------------------------------------------------------------
def _parse_cip_response(text: str) -> dict[str, str]:
    """解析 cip.cc 返回的文本，提取 IP、位置、运营商。"""
    result: dict[str, str] = {"raw": text}
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("IP：") or line.startswith("IP:"):
            result["ip"] = line.split("：", 1)[-1].split(":", 1)[-1].strip()
        elif line.startswith("位置：") or line.startswith("位置:"):
            result["location"] = line.split("：", 1)[-1].split(":", 1)[-1].strip()
        elif "运营商" in line or "ISP" in line.upper():
            result["isp"] = line.split("：", 1)[-1].split(":", 1)[-1].strip()
    return result


# ---------------------------------------------------------------------------
# 核心请求函数（同步）
# ---------------------------------------------------------------------------
def anti_get(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float | None = None,
    retries: int = 3,
    retry_delay: float = 2.0,
    allow_redirects: bool = True,
    pre_delay: bool = True,
    use_proxy: bool | None = None,
    fallback_to_direct: bool = False,
) -> curl_requests.Response:
    """发起防检测 GET 请求。

    特性:
        1. 自动通过 Tailscale 代理转发流量到家庭 IP
        2. 随机 Chrome TLS 指纹 (JA3) 伪装，与 User-Agent 配对
        3. 指数退避重试 + 随机抖动
        4. 可配置超时

    代理策略:
        - 默认根据域名白名单决定是否走代理（财经网站走代理，其他直连）
        - 通过 use_proxy 参数可以覆盖默认行为

    代理失败行为:
        - 默认（fallback_to_direct=False）：代理连接失败时抛出异常，
          不会回退到直连，避免泄露服务器真实 IP。
        - 设置 fallback_to_direct=True：代理失败后回退到直连请求。

    注意:
        此函数是同步的，会阻塞事件循环。在 async 上下文中请使用
        asyncio.to_thread(anti_get, ...) 或 async_anti_get()。

    Args:
        url: 目标 URL
        params: URL 查询参数
        headers: 额外请求头（会合并到默认头中）
        timeout: 请求超时秒数，默认读 settings.proxy_timeout
        retries: 最大重试次数（含首次请求）
        retry_delay: 重试基础延迟秒数
        allow_redirects: 是否跟随重定向
        pre_delay: 是否在首次请求前添加随机延迟
        use_proxy: 是否使用代理（None=根据域名白名单判断，True=强制走代理，False=强制直连）
        fallback_to_direct: 代理失败时是否回退到直连（默认 False，出于安全考虑）

    Returns:
        curl_cffi Response 对象

    Raises:
        RuntimeError: 所有重试耗尽后抛出
        ConnectionError: 代理连接失败且 fallback_to_direct=False
    """
    # 根据 use_proxy 参数和域名白名单决定是否走代理
    if use_proxy is None:
        proxies = _build_proxies(url)
    elif use_proxy:
        proxies = _build_proxies()  # 强制走代理，忽略白名单
    else:
        proxies = None  # 强制直连

    effective_timeout = timeout if timeout is not None else settings.proxy_timeout
    impersonate, merged_headers = _random_headers(headers)

    # 仅代理模式下添加前置延迟，避免高频请求触发风控
    if pre_delay and proxies:
        _random_delay()

    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            logger.debug(
                "anti_get attempt=%d/%d url=%s impersonate=%s proxy=%s",
                attempt, retries, url, impersonate,
                proxies.get("https", "direct") if proxies else "direct",
            )
            response = curl_requests.get(
                url,
                params=params,
                headers=merged_headers,
                proxies=proxies,
                timeout=effective_timeout,
                impersonate=impersonate,
                allow_redirects=allow_redirects,
            )
            logger.debug(
                "anti_get success url=%s status=%d",
                url, response.status_code,
            )
            response.raise_for_status()
            return response

        except Exception as exc:
            last_error = exc

            # 检测代理连接失败
            is_proxy_error = proxies and _is_proxy_connection_error(exc)

            if is_proxy_error and not fallback_to_direct:
                logger.error(
                    "anti_get 代理连接失败 url=%s proxy=%s error=%s",
                    url, proxies.get("https"), exc,
                )
                raise ConnectionError(
                    f"代理连接失败，请检查 Tailscale 连接和 Clash 代理配置: {exc}"
                ) from exc

            logger.warning(
                "anti_get failed attempt=%d/%d url=%s error=%s",
                attempt, retries, url, exc,
            )
            if attempt < retries:
                # 指数退避 + 随机抖动
                sleep_time = retry_delay * (2 ** (attempt - 1)) + random.uniform(0, 1)
                logger.debug("retrying in %.1fs", sleep_time)
                time.sleep(sleep_time)
                # 每次重试切换 TLS 指纹和 UA（保持配对）
                impersonate, merged_headers = _random_headers(headers)

    raise RuntimeError(f"anti_get 请求失败 (共 {retries} 次尝试): {url}") from last_error


def _is_proxy_connection_error(exc: Exception) -> bool:
    """判断异常是否为代理连接错误。"""
    error_msg = str(exc).lower()
    proxy_indicators = [
        "connection timed out",
        "failed to connect",
        "connection refused",
        "no route to host",
        "connection reset",
    ]
    return any(indicator in error_msg for indicator in proxy_indicators)


# ---------------------------------------------------------------------------
# 异步包装器
# ---------------------------------------------------------------------------
async def async_anti_get(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float | None = None,
    retries: int = 3,
    retry_delay: float = 2.0,
    allow_redirects: bool = True,
    pre_delay: bool = True,
    use_proxy: bool | None = None,
    fallback_to_direct: bool = False,
    executor: Any = None,
) -> curl_requests.Response:
    """anti_get 的异步版本，通过 asyncio.to_thread 避免阻塞事件循环。"""
    return await asyncio.to_thread(
        anti_get,
        url,
        params=params,
        headers=headers,
        timeout=timeout,
        retries=retries,
        retry_delay=retry_delay,
        allow_redirects=allow_redirects,
        pre_delay=pre_delay,
        use_proxy=use_proxy,
        fallback_to_direct=fallback_to_direct,
        executor=executor,
    )


# ---------------------------------------------------------------------------
# 代理 IP 验证
# ---------------------------------------------------------------------------
def verify_proxy_ip() -> dict[str, str]:
    """通过 cip.cc 验证当前外显 IP，确认代理是否生效。

    Returns:
        {"ip": "x.x.x.x", "location": "xxx", "isp": "xxx", "raw": "完整响应"}

    Raises:
        RuntimeError: 代理连接失败时抛出
    """
    try:
        resp = anti_get("https://cip.cc", timeout=10, retries=2)
        text = resp.text.strip()
        logger.info("代理 IP 验证结果:\n%s", text)
        return _parse_cip_response(text)

    except Exception as exc:
        raise RuntimeError(f"代理 IP 验证失败: {exc}") from exc


def verify_direct_ip() -> dict[str, str]:
    """直连（不走代理）验证服务器本身 IP，用于对比。

    Returns:
        同 verify_proxy_ip 格式
    """
    try:
        impersonate, headers = _random_headers()
        resp = curl_requests.get(
            "https://cip.cc",
            headers=headers,
            timeout=10,
            impersonate=impersonate,
        )
        text = resp.text.strip()
        logger.info("直连 IP 验证结果:\n%s", text)
        return _parse_cip_response(text)

    except Exception as exc:
        raise RuntimeError(f"直连 IP 验证失败: {exc}") from exc


# ---------------------------------------------------------------------------
# CLI 快速验证入口
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import json as _json

    print("=" * 60)
    print("1. 验证直连 IP（腾讯云服务器本身）")
    print("=" * 60)
    try:
        direct = verify_direct_ip()
        print(_json.dumps(direct, ensure_ascii=False, indent=2))
    except RuntimeError as e:
        print(f"直连验证失败: {e}")

    print()
    print("=" * 60)
    print("2. 验证代理 IP（通过 Tailscale → 家庭 Clash）")
    print("=" * 60)
    try:
        proxied = verify_proxy_ip()
        print(_json.dumps(proxied, ensure_ascii=False, indent=2))
    except RuntimeError as e:
        print(f"代理验证失败: {e}")

    print()
    print("=" * 60)
    print("3. 对比结果")
    print("=" * 60)
    try:
        d = verify_direct_ip()
        p = verify_proxy_ip()
        print(f"直连 IP: {d.get('ip', 'N/A')} ({d.get('location', 'N/A')})")
        print(f"代理 IP: {p.get('ip', 'N/A')} ({p.get('location', 'N/A')})")
        if d.get("ip") != p.get("ip"):
            print("✅ 代理生效！IP 已切换")
        else:
            print("⚠️  IP 未变化，请检查 Tailscale 连接和 Clash 代理配置")
    except Exception as e:
        print(f"对比失败: {e}")
