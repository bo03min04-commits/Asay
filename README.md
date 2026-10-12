# Asay — 온라인 악성 콘텐츠 대응을 위한 증거 정리 MVP

> **아름답게 말하도록 선도하자.** 온라인 악성 댓글·게시물의 URL과 메타데이터를 사건별로 기록하고, PDF·Excel·ZIP 자료를 만들어 상담 및 신고 준비를 돕는 로컬 웹앱입니다.

사용자가 제공한 `Asay.pdf` 기획서 기반으로 작성했습니다. 원본 PDF에는 팀원의 학번 등 개인정보가 있어 공개 저장소용 압축파일에는 포함하지 않았습니다. 현재 코드는 시연 가능한 **1단계 MVP**입니다. 법률 자문, 고소 접수 자동화 또는 증거능력 보장 서비스가 아닙니다.

## 지금 가능한 기능

- 사건 등록 / 검색 / 사건별 증거 목록 확인
- 공개 웹페이지 URL의 HTML, 제목, 본문 및 일부 메타데이터(작성자·게시시각) 수집
- PNG·JPG·WebP·PDF 증거 파일 및 수동 증거 기록 등록
- 수집 일시, 기록 및 첨부파일 SHA-256 해시와 원본 HTML(수집 성공 시) 보관
- 같은 URL 재수집 시 기존 기록을 보존하고 새 증거를 추가
- 검토 메모 편집(원본 수집 내용과 분리)
- 사건 단위 PDF 보고서, Excel 목록, 상담용 사실관계 초안, 첨부파일 및 해시 목록(manifest)을 포함한 ZIP 출력
- 반응형 한글 대시보드 / SQLite 데이터베이스 / 로컬 보관

## 실행 (Python 3.10 이상)

```bash
# 1. 프로젝트 폴더에서 가상환경 생성
python -m venv .venv

# 2. 가상환경 활성화
# macOS / Linux
source .venv/bin/activate
# Windows PowerShell
# .venv\Scripts\Activate.ps1

# 3. 의존성 설치
pip install -r requirements.txt

# 4. 개발 서버 시작 (로컬 접속 전용)
uvicorn asay.main:app --host 127.0.0.1 --port 8000 --reload
```

브라우저에서 **http://127.0.0.1:8000** 을 엽니다.

데이터는 기본적으로 `.data/asay.sqlite3`, `.data/attachments/` 에 저장되며 `.gitignore`로 Git 추적에서 제외됩니다. 이 폴더를 삭제하면 저장 데이터도 삭제되므로 백업하세요.

## 사용 순서

1. 메인 화면에서 **새 사건 등록**
2. 해당 사건에서 **URL 수집** 또는 **자료 직접 등록**
3. 자동 추출된 작성자·게시 일시·본문을 원본에서 대조
4. 필요하면 **검토 메모**를 적고 동일 URL을 **재수집**
5. **전체 패키지 ZIP**, PDF, Excel, 사실관계 초안 출력

### 선택: 자동 스크린샷

기본 상태에서는 HTML 수집과 수동 이미지 첨부를 지원합니다. URL 자동 스크린샷을 사용하려면 다음을 **로컬의 신뢰 가능한 환경에서만** 설정하세요.

```bash
pip install playwright
python -m playwright install chromium
# macOS / Linux
export ASAY_SCREENSHOTS=1
# Windows PowerShell
# $env:ASAY_SCREENSHOTS="1"
uvicorn asay.main:app --host 127.0.0.1 --port 8000
```

일부 플랫폼은 로그인·CAPTCHA·JavaScript·접근 정책 때문에 자동 수집 또는 화면 캡처에 실패합니다. 자동 HTML 수집이 성공해도 화면 캡처는 별도로 실패할 수 있습니다. 원본 파일을 직접 첨부하여 보완하세요.

## 테스트

```bash
pip install -r requirements-dev.txt
pip install httpx
pytest -q
```

## GitHub 저장소에 업로드

간단한 한글 가이드는 [`GITHUB_UPLOAD_KO.md`](GITHUB_UPLOAD_KO.md) 참조.

저장소: https://github.com/bo03min04-commits/Asay

빈 저장소라면 압축파일을 풀어 이 디렉터리 안에서 다음을 실행합니다.

```bash
git init
git branch -M main
git remote add origin https://github.com/bo03min04-commits/Asay.git
git add .
git commit -m "feat: initial Asay evidence management MVP"
git push -u origin main
```

이미 `origin`이 설정된 저장소를 clone했다면 `git init`, `git remote add` 는 생략하고 파일을 복사해 `git add .`, `git commit`, `git push`만 하세요. GitHub 저장소가 README/초기 커밋을 포함하고 있다면 먼저 `git clone https://github.com/bo03min04-commits/Asay.git` 한 뒤 이 파일들을 복사하는 방식을 권장합니다. 코드를 올려도 GitHub Pages에서 Python 백엔드가 자동 실행되는 것은 아닙니다.

## 기술 스택

| 영역 | 기술 |
|---|---|
| 서버 | Python, FastAPI, Uvicorn |
| 프론트엔드 | Jinja2, HTML/CSS, Vanilla JavaScript |
| 저장소 | SQLite, 로컬 첨부파일 |
| 수집 | httpx, BeautifulSoup, (선택) Playwright |
| 내보내기 | ReportLab(PDF), openpyxl(Excel), ZIP |

## 주의 및 제한

- **공개 배포 금지:** 사용자 계정 인증, 접근 제어, HTTPS, 암호화·보존정책, 운영 감사로그가 없는 **로컬 단일 사용자 데모**입니다. 민감한 자료의 인터넷 서버 공개를 권장하지 않습니다.
- **URL 보안:** 사설 IP, 로컬 주소, 예약 IP, 비표준 포트를 차단하지만 DNS 재바인딩 등의 고급 공격은 네트워크 격리로 별도 방어해야 합니다.
- **개인정보·서비스 정책:** 제3자 정보의 수집·보관·공유는 개인정보보호법, 저작권, 각 플랫폼의 약관 및 관련법을 확인해야 합니다. 접근 제한 우회 기능은 없습니다.
- **증거 한계:** 자동 추출 정보에 오류가 있을 수 있고, 로컬 시각은 공인 타임스탬프가 아닙니다. SHA-256은 저장한 레코드의 비교 값일 뿐 공적 채증 인증, 무결성 증명 절차 또는 법적 증거능력을 보장하지 않습니다.
- **법률 문서:** 초안은 객관적 사건 정보 정리 용도입니다. 자동으로 죄명·처벌 가능성 등을 판단하지 않습니다.
- **미구현:** 실시간 모니터링·알림, 다중 계정, 결제, 변호사 연결, ECRM 직접 제출 및 고소장 자동 접수는 후속 개발 범위입니다.

## 다음 단계 제안

1. 인증/암호화/보존정책과 운영 감사로그 설계
2. 플랫폼별 공식 API 또는 적법한 수집 연동
3. 사용자 승인형 모니터링 및 변경 알림(작업 큐)
4. 수집 누락·오분류 검증, 사건 관리 협업, 배포/운영 보안 점검

---

**Asay** · 팀 프로젝트 MVP · 제안서 기준 핵심 1단계 기능 구현
