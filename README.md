# PublicGPT

OpenAI API 기반의 채팅 전용 FastAPI 프로젝트입니다.

## 현재 단계

지금 프로젝트는 `메모리형 챗봇` 완성본이 아니라, 그 전에 필요한 `GPT API 순정 챗봇 베이스` 단계입니다.

현재 포함된 것:

- OpenAI GPT 모델 호출
- 브라우저 채팅 UI
- 세션 단위 UI 채팅 상태 저장
- 선택형 웹 검색 보강
- OpenAI 호환 `/v1/chat/completions`

아직 포함되지 않은 것:

- 메시지 DB 저장
- 세션/사용자 summary
- embedding/vector retrieval
- 장기 기억형 프롬프트 조립

## 실행 준비

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

`.env`에 OpenAI 설정을 넣어둔 뒤 서버를 실행합니다.

## 서버 실행

가장 간단한 실행:

```powershell
.\start_server.ps1
```

또는:

```bat
start_server.bat
```

상태 확인:

```powershell
.\status_server.ps1
```

중지:

```powershell
.\stop_server.ps1
```

직접 명령으로 실행하려면:

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

## 접속 주소

- UI: `http://127.0.0.1:8000/ui`
- Health: `http://127.0.0.1:8000/health`
- Docs: `http://127.0.0.1:8000/docs`

## 주요 구조

- `main.py`
  - FastAPI 앱 생성, 라우터 등록
- `app/api/routes.py`
  - `/chat`, `/models`, `/health`, `/ui-state/chats`
- `app/api/chat_ui.py`
  - 기본 채팅 UI `/ui`
- `app/api/openai_compat.py`
  - OpenAI 호환 `/v1/chat/completions`
- `app/chat/handlers.py`
  - 채팅 요청 처리, 프롬프트 조립
- `app/core/llm.py`
  - OpenAI Responses API 호출
- `static/index.html`
  - 브라우저 채팅 UI

## 현재 동작 방식

- 프론트엔드가 현재 세션의 대화 목록을 들고 있음
- `/chat` 요청 시 현재 세션 history를 함께 서버로 보냄
- 서버가 history와 현재 질문을 프롬프트로 조립
- OpenAI GPT 모델이 응답 생성
- UI 상태는 `data/ui_state/` 아래 JSON으로 저장

## 다음 단계

다음 단계에서 이 베이스 위에 아래를 추가할 예정입니다.

1. 일반 DB에 메시지 저장
2. summary 테이블 추가
3. embedding/vector memory 추가
4. `최근 대화 + 요약 + 관련 과거 대화` 구조로 확장
