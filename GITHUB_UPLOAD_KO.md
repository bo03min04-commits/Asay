# 기존 GitHub 저장소에 Asay 프로젝트 올리는 방법

대상 저장소: https://github.com/bo03min04-commits/Asay

## 방법 A — GitHub 사이트에서 바로 업로드 (Git 설치 불필요)

1. `Asay-GitHub-MVP.zip` 파일을 다운로드하고 압축을 풉니다.
2. [Asay 저장소](https://github.com/bo03min04-commits/Asay)에 로그인해 이동합니다.
3. 저장소 화면에서 **Add file → Upload files**를 클릭합니다.
4. 압축 해제한 `Asay-GitHub` 안의 프로젝트 파일 및 폴더를 업로드합니다. 가능하면 전체 디렉터리 구조(`asay/`, `tests/`, `.github/` 등)를 유지하세요.
5. 아래 **Commit changes**를 눌러 업로드를 완료합니다.

GitHub 브라우저 업로드에서 일부 숨김 파일/폴더가 누락될 수 있습니다. 그런 경우 방법 B를 사용하세요.

## 방법 B — Git 명령어 (권장)

이미 저장소가 만들어졌다면 **clone → 파일 복사 → push** 순서로 진행하면 기존 기록을 덮어쓰지 않습니다.

```bash
git clone https://github.com/bo03min04-commits/Asay.git
cd Asay
```

압축을 푼 `Asay-GitHub` **안의 파일 전부**를 방금 생성된 `Asay` 폴더에 복사합니다. 그리고 다음을 실행합니다.

```bash
git add .
git commit -m "feat: build Asay evidence management MVP"
git push origin main
```

저장소 기본 브랜치가 `master`라면 마지막 명령어의 `main`을 `master`로 바꾸세요. 저장소가 비어 있을 때는 README의 `git init` 방식도 가능합니다.

## 실행 확인

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn asay.main:app --host 127.0.0.1 --port 8000 --reload
```

주소: http://127.0.0.1:8000

**주의:** GitHub에 소스코드를 올린 것만으로 사이트가 인터넷에 배포되지는 않습니다. 또한 이 MVP는 로그인 기능이 없으므로 공개 서버에 배포하지 마세요.
