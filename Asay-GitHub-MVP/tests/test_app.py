import io
import os
import zipfile

import pytest
from fastapi.testclient import TestClient

from asay.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('ASAY_DATA_DIR', str(tmp_path / 'private_data'))
    with TestClient(app) as c:
        yield c


def make_case(client):
    r = client.post('/cases', data={'title':'악성 댓글 수집', 'description':'댓글 피해 정리'}, follow_redirects=False)
    assert r.status_code == 303
    return int(r.headers['location'].split('/')[-1])


def test_home_and_case_creation(client):
    assert client.get('/').status_code == 200
    case_id = make_case(client)
    response = client.get(f'/cases/{case_id}')
    assert response.status_code == 200
    assert '악성 댓글 수집' in response.text
    assert '0개' in response.text


def test_manual_evidence_and_exports(client):
    case_id = make_case(client)
    r = client.post(f'/cases/{case_id}/manual', data={'title':'악성댓글 A','body':'예시 본문', 'author':'nick123'},
                    files={'attachment':('screen.png', b'\x89PNG\r\n\x1a\n' + b'example', 'image/png')}, follow_redirects=False)
    assert r.status_code == 303
    doc = client.get(f'/cases/{case_id}')
    assert '악성댓글 A' in doc.text and 'nick123' in doc.text
    pdf = client.get(f'/cases/{case_id}/export/pdf')
    assert pdf.status_code == 200 and pdf.content.startswith(b'%PDF-')
    xlsx = client.get(f'/cases/{case_id}/export/xlsx')
    assert xlsx.status_code == 200 and xlsx.content.startswith(b'PK')
    z = client.get(f'/cases/{case_id}/export/zip')
    assert z.status_code == 200
    with zipfile.ZipFile(io.BytesIO(z.content)) as archive:
        names = archive.namelist()
        assert any(n.endswith('.xlsx') for n in names)
        assert any(n.endswith('.pdf') for n in names)
        assert any(n.startswith('attachments/') for n in names)
        assert 'manifest-sha256.json' in names


def test_reject_bad_attachment(client):
    case_id = make_case(client)
    r = client.post(f'/cases/{case_id}/manual', data={'body':'test'},files={'attachment':('bad.html',b'<script>x</script>','text/html')})
    assert r.status_code == 422


def test_reject_external_host(client):
    assert client.get('/', headers={'host':'example.org'}).status_code == 403
    assert client.post('/cases', data={'title':'bad'}, headers={'origin':'https://evil.example'}).status_code == 403


def test_missing_case(client):
    assert client.get('/cases/999').status_code == 404


def test_excel_formula_injection_escaped(client):
    from openpyxl import load_workbook
    case_id = make_case(client)
    client.post(f'/cases/{case_id}/manual', data={'title':'=1+1', 'body':'+SUM(1,2)'})
    document = client.get(f'/cases/{case_id}/export/xlsx')
    workbook = load_workbook(io.BytesIO(document.content))
    sheet = workbook.active
    assert sheet['D2'].data_type != 'f'
    assert sheet['J2'].data_type != 'f'


def test_collect_html_mock(client,monkeypatch):
    import asay.main as main
    from asay.capture import PageCapture
    async def mock_fetch(url):
        return PageCapture(final_url='https://example.org/post/123', platform='example.org',title='예시 페이지',
                           author='abc',posted_at='2026-10-12', body='저장할 본문',html_bytes=b'<html><title>test</title></html>')
    monkeypatch.setattr(main, 'fetch_public_page', mock_fetch)
    case_id = make_case(client)
    res = client.post(f'/cases/{case_id}/collect',data={'url':'https://example.org/post/123'},follow_redirects=False)
    assert res.status_code == 303
    detail = client.get(f'/cases/{case_id}').text
    assert '예시 페이지' in detail
    assert '원본 HTML' in detail
