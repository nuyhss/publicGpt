# PublicGPT

OpenAI API 기반 채팅 전용 FastAPI 프로젝트입니다.

## 포함 기능

- 일반 채팅 UI
- 최근 대화 히스토리 전달
- OpenAI 모델 선택
- 선택적 웹 검색 보강
- OpenAI 호환 `/v1/chat/completions`

## 제거된 기능

- 문서 업로드
- 문서 보관함
- PDF/OCR 파이프라인
- 벡터 문서 검색 UI
- Ollama 실행 경로

## 실행

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

환경 변수 예시:

```bash
set OPENAI_API_KEY=your_key_here
set OPENAI_MODEL=gpt-5.5
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

접속:

- `http://127.0.0.1:8000/ui`
- `http://127.0.0.1:8000/docs`

## 다음 단계

1. 채팅 원문 DB 저장
2. 세션 요약 저장
3. 과거 대화 벡터 검색
4. 최근 대화 + 요약 + 검색 결과 조합 프롬프트
