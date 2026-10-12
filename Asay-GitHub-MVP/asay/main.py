import hashlib
import json
import os
import re
import secrets
import zipfile
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Optional
from urllib.parse import urlsplit

import httpx
from fastapi import FastAPI, Form, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import db
from .capture import fetch_public_page
from .exports import make_pdf, make_xlsx, make_complaint_draft
from .security import UnsafeURL

BASE = Path(__file__).parent

@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield

app = FastAPI(title='Asay', description='온라인 악성 콘텐츠 증거 정리 로컬 MVP', lifespan=lifespan, docs_url=None, redoc_url=None)
app.mount('/static', StaticFiles(directory=BASE / 'static'), name='static')
templates = Jinja2Templates(directory=BASE / 'templates')


def now():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')


def digest(record: dict) -> str:
    # 정규화된 텍스트를 해시합니다. 제3자 원본성 인증은 제공하지 않습니다.
    return hashlib.sha256(json.dumps(record, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()


def get_case(case_id: int):
    case = db.row('SELECT * FROM cases WHERE id = ?', (case_id,))
    if case is None:
        raise HTTPException(404, '사건을 찾을 수 없습니다.')
    return case


def get_evidence(case_id: int):
    return db.rows('SELECT * FROM evidence WHERE case_id = ? ORDER BY id DESC', (case_id,))


def put_evidence(case_id: int, *, source_kind='web', source_url='', platform='', title='', author='', posted_at='', body='',
                 status='ok', html_file='', screenshot_file='', notes='', warning='', parent_id=None):
    captured_at = now()
    value = dict(source_url=source_url, platform=platform, title=title, author=author, posted_at=posted_at, body=body,
                 captured_at=captured_at, source_kind=source_kind)
    sha = digest(value)
    return db.execute('''INSERT INTO evidence(case_id, source_kind, source_url, platform, title, author, posted_at,
                    body, captured_at, capture_status, sha256, raw_html_file, screenshot_file, notes, warning, parent_id)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                    (case_id,source_kind,source_url,platform,title,author,posted_at,body,captured_at,status,sha,html_file,
                    screenshot_file,notes,warning,parent_id))


def page(request, name, **kwargs):
    return templates.TemplateResponse(request=request, name=name, context=kwargs)


@app.middleware('http')
async def local_only_host(request: Request, call_next):
    # 인터넷 배포용 인증이 구현되지 않은 MVP이므로 DNS rebinding 형태의 접근을 완화합니다.
    host_header = request.headers.get('host', '')
    try:
        host = urlsplit('//' + host_header).hostname or ''
    except ValueError:
        host = ''
    host = host.lower()
    if host not in ('127.0.0.1', 'localhost', '::1', 'testserver'):
        return Response('로컬 호스트에서만 이용할 수 있습니다.', status_code=403)
    if request.method in ('POST','PUT','PATCH','DELETE'):
        origin = request.headers.get('origin')
        if origin:
            origin_host = urlsplit(origin).hostname
            if origin_host not in ('127.0.0.1','localhost','::1','testserver'):
                return Response('외부 페이지의 요청은 차단됩니다.', status_code=403)
    return await call_next(request)


@app.get('/', response_class=HTMLResponse)
async def home(request: Request, q: str = ''):
    cases = db.rows('SELECT c.*, (SELECT count(*) FROM evidence e WHERE e.case_id=c.id) AS evidence_count FROM cases c ORDER BY c.id DESC')
    total_cases = len(cases)
    if q:
        cases = [c for c in cases if q.casefold() in (c['title']+' '+c['description']).casefold()]
    evidence_count = db.row('SELECT count(*) AS n FROM evidence')['n']
    return page(request, 'index.html', cases=cases, total_cases=total_cases, evidence_count=evidence_count, q=q)


@app.post('/cases')
async def create_case(title: str = Form(...), description: str = Form('')):
    title = title.strip()[:120]
    if not title:
        raise HTTPException(422, '사건 이름을 입력하세요.')
    case_id = db.execute('INSERT INTO cases(title, description, created_at) VALUES (?,?,?)', (title, description.strip()[:2000], now()))
    return RedirectResponse(f'/cases/{case_id}', status_code=303)


@app.get('/cases/{case_id}', response_class=HTMLResponse)
async def case_detail(request: Request, case_id: int, info: str = ''):
    return page(request, 'case.html', case=get_case(case_id), evidence=get_evidence(case_id), info=info)


async def optional_screenshot(url: str, evid_id: int) -> str:
    if os.environ.get('ASAY_SCREENSHOTS') != '1':
        return ''
    # 명시적 opt-in + Chromium 설치 필요. 공개 서버에선 네트워크 격리 선행.
    from .security import validate_public_url
    from playwright.async_api import async_playwright
    validate_public_url(url)
    target = db.data_dir() / 'attachments' / f'evidence-{evid_id}.png'
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            context = await browser.new_context(viewport={'width': 1280, 'height': 900}, service_workers='block')
            async def route_guard(route):
                try:
                    validate_public_url(route.request.url)
                    await route.continue_()
                except Exception:
                    await route.abort()
            await context.route('**/*', route_guard)
            ppage = await context.new_page()
            await ppage.goto(url, wait_until='domcontentloaded', timeout=12000)
            await ppage.screenshot(path=str(target), full_page=True, timeout=10000)
        finally:
            await browser.close()
    return target.name


@app.post('/cases/{case_id}/collect')
async def collect(case_id: int, url: str = Form(...), parent_id: Optional[int] = Form(None)):
    get_case(case_id)
    url = url.strip()
    if parent_id is not None and not db.row('SELECT 1 FROM evidence WHERE id=? AND case_id=?', (parent_id,case_id)):
        raise HTTPException(404, '이전 증거를 찾을 수 없습니다.')
    try:
        page_data = await fetch_public_page(url)
    except (UnsafeURL, ValueError, httpx.HTTPError, UnicodeError) as e:
        message = str(e)[:250]
        # 실패 자체를 채증 성공으로 기록하지 않습니다. 나중에 수동등록할 수 있습니다.
        return RedirectResponse(f'/cases/{case_id}?info=collect-failed', status_code=303,
                                headers={'X-Asay-Error': message.encode('ascii','ignore').decode('ascii')[:100]})
    evid_id = put_evidence(case_id, source_url=page_data.final_url, platform=page_data.platform, title=page_data.title,
                           author=page_data.author, posted_at=page_data.posted_at, body=page_data.body,
                           warning=page_data.warning, parent_id=parent_id)
    attachments = db.data_dir()/'attachments'
    attachments.mkdir(parents=True, exist_ok=True)
    html_file = f'evidence-{evid_id}.html'
    (attachments/html_file).write_bytes(page_data.html_bytes)
    shot_file = ''
    try:
        shot_file = await optional_screenshot(page_data.final_url, evid_id)
    except Exception:
        # HTML 채증을 취소하지 않고 이미지 미생성 사실을 분리 기록합니다.
        pass
    screenshot_hash = hashlib.sha256((attachments/shot_file).read_bytes()).hexdigest() if shot_file else ''
    html_hash = hashlib.sha256(page_data.html_bytes).hexdigest()
    with db.connect() as con:
        con.execute('UPDATE evidence SET raw_html_file=?, screenshot_file=?, attachment_sha256=?, html_sha256=? WHERE id=?', (html_file,shot_file,screenshot_hash,html_hash,evid_id))
    return RedirectResponse(f'/cases/{case_id}?info=collected', status_code=303)


def validate_upload(content: bytes, filename: str) -> tuple[str,str]:
    suffix = Path(filename or '').suffix.lower()
    if suffix == '.png' and content.startswith(b'\x89PNG\r\n\x1a\n'):
        return '.png', 'image/png'
    if suffix in ('.jpg','.jpeg') and content.startswith(b'\xff\xd8\xff'):
        return '.jpg', 'image/jpeg'
    if suffix == '.webp' and content.startswith(b'RIFF') and content[8:12] == b'WEBP':
        return '.webp', 'image/webp'
    if suffix == '.pdf' and content.startswith(b'%PDF-'):
        return '.pdf', 'application/pdf'
    raise ValueError('PNG, JPG, WebP, PDF 파일만 등록할 수 있습니다.')


@app.post('/cases/{case_id}/manual')
async def manual(case_id: int, source_url: str = Form(''), platform: str = Form(''), title: str = Form(''),
                 author: str = Form(''), posted_at: str = Form(''), body: str = Form(''),
                 notes: str = Form(''), attachment: Optional[UploadFile] = File(None)):
    get_case(case_id)
    content = b''
    suffix = ''
    if attachment and attachment.filename:
        content = await attachment.read(8_000_001)
        if len(content) > 8_000_000:
            raise HTTPException(413, '첨부파일은 8MB 이하만 가능합니다.')
        try:
            suffix,_ = validate_upload(content, attachment.filename)
        except ValueError as e:
            raise HTTPException(422, str(e)) from e
    if not any((source_url.strip(),body.strip(),content)):
        raise HTTPException(422, 'URL, 본문, 첨부파일 중 하나는 필요합니다.')
    evid_id = put_evidence(case_id, source_kind='manual',source_url=source_url.strip()[:2048], platform=platform.strip()[:120],
                           title=title.strip()[:500],author=author.strip()[:255],posted_at=posted_at.strip()[:120],
                           body=body.strip()[:30000],notes=notes.strip()[:3000],
                           warning='사용자가 직접 등록한 자료입니다. 원본과 대조가 필요합니다.')
    if content:
        attachments = db.data_dir()/'attachments'
        attachments.mkdir(parents=True, exist_ok=True)
        safe_name = f'evidence-{evid_id}-{secrets.token_hex(5)}{suffix}'
        (attachments/safe_name).write_bytes(content)
        with db.connect() as con:
            con.execute('UPDATE evidence SET screenshot_file=?, attachment_sha256=? WHERE id=?', (safe_name,hashlib.sha256(content).hexdigest(),evid_id))
    return RedirectResponse(f'/cases/{case_id}?info=manual-added', status_code=303)


@app.post('/cases/{case_id}/evidence/{evid_id}/note')
async def update_notes(case_id: int, evid_id: int, notes: str = Form('')):
    get_case(case_id)
    with db.connect() as con:
        result = con.execute('UPDATE evidence SET notes=? WHERE id=? AND case_id=?', (notes.strip()[:3000],evid_id,case_id))
        if result.rowcount == 0:
            raise HTTPException(404, '증거를 찾을 수 없습니다.')
    return RedirectResponse(f'/cases/{case_id}#evidence-{evid_id}', status_code=303)


@app.post('/cases/{case_id}/evidence/{evid_id}/refresh')
async def refresh(case_id: int, evid_id: int):
    get_case(case_id)
    item = db.row('SELECT * FROM evidence WHERE id=? AND case_id=?', (evid_id,case_id))
    if item is None or not item['source_url'] or item['source_kind']!='web':
        raise HTTPException(404, '자동 재수집할 수 없는 자료입니다.')
    # 기존 자료를 덮어쓰지 않고 새 기록을 생성합니다.
    return await collect(case_id, item['source_url'], parent_id=evid_id)


@app.get('/cases/{case_id}/attachment/{evid_id}')
async def attachment(case_id: int, evid_id: int, kind: str = 'image'):
    get_case(case_id)
    item = db.row('SELECT * FROM evidence WHERE id=? AND case_id=?', (evid_id,case_id))
    if item is None:
        raise HTTPException(404, '파일을 찾을 수 없습니다.')
    if kind not in ('image','html'):
        raise HTTPException(400, '지원하지 않는 유형입니다.')
    basename = item['screenshot_file'] if kind=='image' else item['raw_html_file']
    if not basename or Path(basename).name != basename:
        raise HTTPException(404, '파일을 찾을 수 없습니다.')
    path = db.data_dir()/'attachments'/basename
    if not path.is_file():
        raise HTTPException(404, '파일을 찾을 수 없습니다.')
    # HTML은 인라인 렌더링하지 않고 항상 첨부로 전송합니다 (저장된 악성 스크립트 방지).
    return FileResponse(path, filename=basename, media_type='application/octet-stream', content_disposition_type='attachment',
                        headers={'X-Content-Type-Options':'nosniff'})


@app.get('/cases/{case_id}/export/{format}')
async def export(case_id: int, format: str):
    case = get_case(case_id)
    evidence = get_evidence(case_id)
    if format == 'pdf':
        content = make_pdf(case, evidence)
        media = 'application/pdf'
        filename=f'asay-case-{case_id}.pdf'
    elif format == 'xlsx':
        content = make_xlsx(case, evidence)
        media = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        filename=f'asay-case-{case_id}.xlsx'
    elif format == 'complaint':
        content = make_complaint_draft(case,evidence).encode('utf-8-sig')
        media = 'text/plain; charset=utf-8'
        filename=f'asay-case-{case_id}-draft.txt'
    elif format == 'zip':
        out = BytesIO()
        with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_DEFLATED) as z:
            manifest = {'case_id':case_id,'note':'SHA-256 비교용 해시 목록; 원본성·법적 효력 인증 아님','files':{}}
            def add_file(name, data):
                z.writestr(name, data)
                manifest['files'][name] = hashlib.sha256(data).hexdigest()
            add_file(f'asay-case-{case_id}.pdf', make_pdf(case, evidence))
            add_file(f'asay-case-{case_id}.xlsx', make_xlsx(case, evidence))
            add_file(f'asay-case-{case_id}-draft.txt', make_complaint_draft(case,evidence).encode('utf-8-sig'))
            for item in evidence:
                for field in ('raw_html_file','screenshot_file'):
                    basename = item[field]
                    if basename and Path(basename).name==basename:
                        path=db.data_dir()/'attachments'/basename
                        if path.is_file():
                            add_file(f'attachments/{basename}', path.read_bytes())
            z.writestr('manifest-sha256.json', json.dumps(manifest, ensure_ascii=False, indent=2).encode('utf-8'))
        content=out.getvalue()
        media='application/zip'
        filename=f'asay-case-{case_id}-package.zip'
    else:
        raise HTTPException(404, '지원하지 않는 출력 형식입니다.')
    return Response(content, media_type=media, headers={
        'Content-Disposition':f'attachment; filename="{filename}"',
        'X-Content-Type-Options':'nosniff',
        'Cache-Control':'no-store'
    })


@app.get('/health')
async def health():
    return {'status':'ok', 'app':'Asay', 'mode':'local-mvp'}
