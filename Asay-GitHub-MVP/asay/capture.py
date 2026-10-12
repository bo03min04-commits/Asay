import html
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup

from .security import UnsafeURL, validate_public_url

MAX_HTML_BYTES = 2_000_000
MAX_REDIRECTS = 4


@dataclass
class PageCapture:
    final_url: str
    platform: str
    title: str
    author: str
    posted_at: str
    body: str
    html_bytes: bytes
    warning: str = ""


async def fetch_public_page(url: str) -> PageCapture:
    current = validate_public_url(url)
    headers = {"User-Agent": "AsayEvidenceMVP/0.1 (+manual local archival tool)", "Accept": "text/html,application/xhtml+xml"}
    async with httpx.AsyncClient(follow_redirects=False, timeout=httpx.Timeout(15, connect=5), trust_env=False, headers=headers) as client:
        for _ in range(MAX_REDIRECTS + 1):
            # 리다이렉트마다 대상 도메인을 다시 검증합니다.
            validate_public_url(current)
            async with client.stream("GET", current) as response:
                if response.status_code in (301, 302, 303, 307, 308):
                    location = response.headers.get("location")
                    if not location:
                        raise ValueError("이동할 주소를 찾을 수 없습니다.")
                    current = validate_public_url(urljoin(current, location))
                    continue
                if response.status_code >= 400:
                    raise ValueError(f"원본 사이트가 HTTP {response.status_code}로 응답했습니다.")
                ctype = response.headers.get("content-type", "").lower()
                if "text/html" not in ctype and "application/xhtml+xml" not in ctype:
                    raise ValueError("HTML 게시물만 자동 수집할 수 있습니다. 수동 등록을 이용하세요.")
                data = bytearray()
                async for block in response.aiter_bytes():
                    data.extend(block)
                    if len(data) > MAX_HTML_BYTES:
                        raise ValueError("페이지 용량이 2MB를 초과하여 수집을 중단했습니다.")
                html_bytes = bytes(data)
                encoding = response.encoding or "utf-8"
                page = BeautifulSoup(html_bytes.decode(encoding, errors="replace"), "html.parser")
                def meta(*names):
                    for name in names:
                        tag = page.find("meta", attrs={"property": name}) or page.find("meta", attrs={"name": name})
                        if tag and tag.get("content"):
                            return tag["content"].strip()[:2000]
                    return ""
                title_tag = page.find("title")
                title = meta("og:title", "twitter:title") or (title_tag.get_text(" ", strip=True) if title_tag else "")
                author = meta("article:author", "author", "twitter:creator")
                published = meta("article:published_time", "datePublished", "pubdate", "date")
                for element in page(["script", "style", "noscript", "svg", "nav", "footer"]):
                    element.decompose()
                main = page.find("article") or page.find("main") or page.body or page
                body = "\n".join(s.strip() for s in main.stripped_strings if s.strip())[:30_000]
                warning = "사이트 구조 및 로그인/JavaScript 제한으로 작성자·시각·본문이 누락될 수 있습니다."
                return PageCapture(current, urlsplit(current).netloc, html.unescape(title)[:500],
                                   author[:255], published[:100], body, html_bytes, warning)
    raise ValueError("페이지 이동 횟수가 너무 많습니다.")
