# PublicGPT

채팅 전용 FastAPI + Ollama 프로젝트입니다.

## 남긴 기능

- 일반 채팅 UI
- 최근 대화 히스토리 전달
- Ollama 모델 선택
- 선택적 웹 검색 보강
- OpenAI 호환 `/v1/chat/completions`

## 제거한 기능

- 문서 업로드
- 문서 보관함
- PDF/OCR 파이프라인
- 벡터 문서 검색 UI
- 이미지/음성 전용 페이지 흐름

## 실행

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Ollama 예시:

```bash
ollama serve
ollama pull qwen2.5:7b
```

접속:

- `http://127.0.0.1:8000/ui`
- `http://127.0.0.1:8000/docs`

## 다음 단계

이 상태를 베이스로 해서 아래를 붙이면 됩니다.

1. 채팅 원문 DB 저장
2. 세션 요약 저장
3. 과거 대화 벡터 검색
4. 최근 대화 + 요약 + 검색 결과 조합 프롬프트
