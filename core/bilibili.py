"""B站视频信息查询（尽力而为，网络/风控失败时返回可读错误）。"""

from __future__ import annotations

import re

import requests

from core.context import parse_bvid

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com/",
    "Accept": "application/json, text/plain, */*",
}


def _format_duration(seconds: int) -> str:
    seconds = max(0, int(seconds or 0))
    return f"{seconds // 3600:02d}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"


def fetch_video_info(url_or_bvid: str) -> dict:
    bvid = parse_bvid(url_or_bvid or "")
    if not bvid:
        return {"error": "没有找到 BV 号，请提供完整链接或 BV 号"}
    url = f"https://www.bilibili.com/video/{bvid}/"

    try:
        response = requests.get(
            "https://api.bilibili.com/x/web-interface/view",
            params={"bvid": bvid},
            headers=_HEADERS,
            timeout=12,
        )
        if response.status_code == 200 and response.headers.get("content-type", "").startswith(
            "application/json"
        ):
            payload = response.json()
            if payload.get("code") == 0 and payload.get("data"):
                data = payload["data"]
                return {
                    "bvid": bvid,
                    "title": data.get("title", ""),
                    "owner": (data.get("owner") or {}).get("name", ""),
                    "duration": _format_duration(data.get("duration", 0)),
                    "desc": (data.get("desc") or "")[:500],
                    "pages": [
                        {"page": page.get("page"), "part": page.get("part"), "cid": page.get("cid")}
                        for page in (data.get("pages") or [])[:20]
                    ],
                    "url": url,
                }
            return {"bvid": bvid, "url": url, "error": f"B站接口返回 code={payload.get('code')}"}
    except requests.RequestException as exc:
        api_error = f"{type(exc).__name__}: {exc}"
    else:
        api_error = "接口不可用"

    # 兜底：直接抓视频页 <title>
    try:
        page = requests.get(url, headers=_HEADERS, timeout=12)
        match = re.search(r"<title[^>]*>(.*?)</title>", page.text, re.S)
        if match:
            title = re.sub(r"\s*_哔哩哔哩_bilibili\s*$", "", match.group(1)).strip()
            return {
                "bvid": bvid,
                "title": title,
                "url": url,
                "note": "标题来自视频页面（接口被风控，UP主/时长等不可用）",
            }
        return {"bvid": bvid, "url": url, "error": f"页面无标题；接口错误：{api_error}"}
    except requests.RequestException as exc:
        return {"bvid": bvid, "url": url, "error": f"网络不可用：{type(exc).__name__}: {exc}"}
