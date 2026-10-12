"""수집 URL에 대한 방어적 검증.

주의: DNS 재바인딩, 브라우저/프록시 경계까지 보장하는 격리 수준은 아닙니다.
인터넷에 공개된 서버에서는 강화된 egress firewall / 프록시가 필요합니다.
"""
import ipaddress
import socket
from urllib.parse import urlsplit


class UnsafeURL(ValueError):
    pass


def validate_public_url(url: str) -> str:
    url = url.strip()
    if len(url) > 2048:
        raise UnsafeURL("URL이 너무 깁니다.")
    try:
        p = urlsplit(url)
        port = p.port
    except ValueError as e:
        raise UnsafeURL("올바르지 않은 URL입니다.") from e
    if p.scheme not in ("http", "https") or not p.hostname:
        raise UnsafeURL("http/https 공개 URL만 입력할 수 있습니다.")
    if p.username is not None or p.password is not None:
        raise UnsafeURL("계정 정보를 포함한 URL은 사용할 수 없습니다.")
    if port not in (None, 80, 443):
        raise UnsafeURL("80, 443 포트만 수집할 수 있습니다.")
    hostname = p.hostname.strip('.').lower()
    if hostname in ("localhost",) or hostname.endswith((".localhost", ".local", ".internal")):
        raise UnsafeURL("내부 주소에는 접속할 수 없습니다.")
    try:
        addresses = socket.getaddrinfo(hostname, port or (443 if p.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise UnsafeURL("도메인 주소를 확인하지 못했습니다.") from e
    if not addresses:
        raise UnsafeURL("도메인 주소를 확인하지 못했습니다.")
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
            ip = ip.ipv4_mapped
        if not ip.is_global:
            raise UnsafeURL("사설망·로컬·예약 IP로 향하는 URL은 차단됩니다.")
    return url
