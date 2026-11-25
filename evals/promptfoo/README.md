# marketing.py LLM 호출 점검 (promptfoo)

`apps/backend/app/services/marketing.py` 의 Claude 호출 두 곳(`_call_district_llm` · `_call_llm`)을
프로덕션과 같은 순서로 부르고, 프로덕션이 쓰는 `ha_guard` 검증기를 다시 돌린다. 위반이 나오면 실패 =
"이 프롬프트·모델은 프로덕션에서 폐기될 출력을 낸다".

```powershell
$env:PROMPTFOO_PYTHON = (py -3.11 -c "import sys;print(sys.executable)")
cd evals/promptfoo
npx promptfoo@latest eval -c promptfooconfig.yaml --repeat 1     # 케이스 5건 = LLM 5회
npx promptfoo@latest view                                         # 결과 보기
```

- 키는 앱 설정(`settings.llm_api_key`)에서만 읽는다. 없으면 provider 가 호출 없이 에러로 멈춘다.
- 호출 1회 = max_tokens 8192 + thinking. 먼저 `--repeat 1` 로 비용을 본 뒤 올린다.
- 11-22 Program 재정의로 `_call_llm` 경로가 지워지면 마지막 케이스(`target: program`)를 뺀다.
- 레드팀(`promptfoo redteam`)은 이 서비스가 입력을 상권 Gold·브리프로만 받아 공격면이 좁아 아직 구성하지 않았다.
