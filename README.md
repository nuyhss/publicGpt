# PublicGPT

OpenAI API 기반 채팅 전용 FastAPI 프로젝트입니다.

## 포함 기능

- 일반 채팅 UI
- 최근 채팅 히스토리 저장
- OpenAI 모델 선택
- 선택형 웹 검색 보강
- OpenAI 호환 `/v1/chat/completions`

## 제거한 기능

- 문서 업로드
- 문서 보관함
- PDF/OCR 파이프라인
- 벡터 문서 검색 UI
- Ollama 실행 경로

## 실행 준비

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

`.env`에 OpenAI 설정을 넣어둔 뒤 서버를 실행합니다.

## 서버 실행

가장 안정적인 실행 방법:

```powershell
.\start_server.ps1
```

새 창으로 바로 띄우려면:

```bat
start_server.bat
```

직접 명령으로 실행하려면:

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

## 서버 중지

```powershell
.\stop_server.ps1
```

## 접속 주소

- UI: `http://127.0.0.1:8000/ui`
- Health: `http://127.0.0.1:8000/health`
- Docs: `http://127.0.0.1:8000/docs`
