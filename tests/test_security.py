import socket
import pytest
from asay.security import validate_public_url, UnsafeURL


def test_private_ip_blocked():
    with pytest.raises(UnsafeURL):
        validate_public_url('http://127.0.0.1/private')


def test_non_http_blocked():
    with pytest.raises(UnsafeURL):
        validate_public_url('file:///etc/passwd')


def test_credentials_and_port_blocked():
    with pytest.raises(UnsafeURL):
        validate_public_url('https://foo:bar@example.org/')
    with pytest.raises(UnsafeURL):
        validate_public_url('https://example.org:9000/')


def test_public_dns_allowed(monkeypatch):
    def fake_dns(host, port, **kw):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('8.8.8.8',port))]
    monkeypatch.setattr(socket, 'getaddrinfo', fake_dns)
    assert validate_public_url('https://example.org/page') == 'https://example.org/page'


def test_private_dns_blocked(monkeypatch):
    def fake_dns(host, port, **kw):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('10.0.0.1',port))]
    monkeypatch.setattr(socket, 'getaddrinfo', fake_dns)
    with pytest.raises(UnsafeURL):
        validate_public_url('https://example.org/page')
