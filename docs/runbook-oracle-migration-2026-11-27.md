# Oracle Cloud 이전 런북 (2026-11-27)

Cloud Run(GCP 체험 결제계정 만료) → **Oracle Cloud Always Free VM** 한 대로 옮긴다. 사용자 결정(11-26): **전환 없이 체험을 만료시키고 30일 유예 안에 이전**(A안) —
다운타임은 만료일부터 컷오버까지. 코드·DB(Neon)·도메인(가비아)은 GCP 밖에 있어 GCP 가 멈춰도 사라지지 않는다.

> ⚠ **이 문서의 `deploy/oracle/` 파일은 아직 실제 VM 에서 돌려 본 적이 없다.** 검증한 것은 compose 문법(`docker compose config`)과 쉘 문법(`bash -n`)뿐이다.
> 미검증 목록은 §7.

## 1. 한눈에

| 항목 | 값 | 근거 |
|---|---|---|
| 대상 | Oracle A1 `VM.Standard.A1.Flex` **2 OCPU · 12GB**(무료 상한 그대로) · Ubuntu 24.04 aarch64 | A1 은 06-15 에 4/24 → 2/12 로 반감 · 춘천은 A1 불가(Oracle 문서) |
| 필요 사양 | 상시 ~800MB · 피크 ~950MB(Cloud Run 1GiB 에서 p99 93%) | Cloud Monitoring 14일(11-26) → 512MB 급 무료 PaaS 는 탈락 |
| 이미지 | **저장소 루트 `Dockerfile` 그대로** — VM 에서 arm64 로 새로 빌드(gold = git 추적분 245MB) | Dockerfile 수정 0 |
| 앞단 | Caddy(80/443 · Let's Encrypt 자동 · www → 본 주소 301 · gzip/zstd) | Firebase Hosting 은 임의 서버로 리라이트 불가 |
| 비밀값 | `/opt/placeos/placeos.env`(17개) · `/opt/placeos/build.env`(네이버 지도 키 1개) | 저장소 밖 · 권한 700/600 |
| 상태 | VM 은 **무상태** — 계정 DB 는 Neon, 층 배치도 사진도 DB 에 바이트로 있다 | 인증서(caddy_data)만 지워도 재발급 |

## 2. 이미 해 둔 것 (11-27)

- Cloud Run 환경변수 17개를 **이 PC 의 `C:\Users\USER\placeos-migration\placeos.env`** 로 내보냈다. 저장소·OneDrive 밖 · 본인만 읽기/쓰기 · BOM 없음 · LF.
  이름: JWT_SECRET · ADMIN_TOKEN · LLM_API_KEY · DATABASE_URL · GOOGLE_CLIENT_ID · KAKAO_MOBILITY_API_KEY · ODSAY_API_KEY · KAKAO_REST_API_KEY ·
  NAVER_LOGIN_REDIRECT_URI/CLIENT_ID/CLIENT_SECRET · KAKAO_LOGIN_REDIRECT_URI/CLIENT_ID/CLIENT_SECRET · DATA_GO_KR_SERVICE_KEY · BIZINFO_SUPPORT_API_KEY · BIZINFO_EVENT_API_KEY.
  확인: 17줄 · `DATABASE_URL` 150자(08-28 문서의 온전한 길이와 같다 — `&` 에서 안 잘렸다) · 값에 `$` · 따옴표 · 줄바꿈 · 비ASCII 없음(compose 가 해석할 것이 없다).
  **만료 뒤에는 Cloud Run 에서 다시 못 읽는다 — 이 파일을 지우기 전에 안전한 곳에 한 벌 더 둘 것**(비밀번호 관리자 등. 클라우드 동기화 폴더·메신저 금지).
- `build.env`(네이버 지도 키)는 **못 만들었다** — `.env` 를 읽는 동작이 권한 분류기에 막혔다. §4-5 의 한 줄을 직접 실행한다.
- 코드 점검: 레이트리밋은 **클라이언트 IP 를 쓰지 않는다**(이메일·전역 키) → 프록시가 한 홉 바뀌어도 영향 없다. `APP_ENV=prod` 는 Dockerfile 에 박혀 있어 Cloud Run 밖에서도 운영 모드로 뜬다.
  앱에 GZip 미들웨어가 없다 → Caddy `encode`. 보안 헤더·Cache-Control 은 앱이 직접 낸다 → Caddy 는 건드리지 않는다.

## 3. 이 PR 이 올라가야 VM 이 받을 수 있다

`deploy.sh` 는 GitHub 에서 `git clone` 한다(저장소는 공개 — 인증 불필요). `deploy/oracle/` 이 아직 main 에 없으므로 **브랜치 `chore/oracle-migration-20261127` 를 푸시**해야
VM 이 받는다(머지는 선택 — 머지 전엔 `deploy.sh chore/oracle-migration-20261127` 처럼 브랜치를 넘긴다). 커밋·푸시는 사용자가 지시할 때 한다.
`setup-vm.sh` 는 저장소가 필요 없어 §4-4 처럼 scp 로 먼저 올릴 수 있다.

## 4. 순서

담당: **[사용자]** = 콘솔·카드·DNS·비밀값 · **[Claude]** = 요청하면 하는 것.

1. **[사용자] 체험 만료일 확인** — 콘솔 결제 화면 배너(CLI 로 못 읽는다). 이 날짜가 마감이다. 컷오버를 만료 **전에** 끝내면 다운타임이 없다.
2. **[사용자] VM 만들기**(Oracle 콘솔 → 컴퓨트 → 인스턴스 → 인스턴스 생성)

   | 칸 | 값 |
   |---|---|
   | 이름 | `placeos-web` |
   | 이미지 | Canonical Ubuntu 24.04 (aarch64) |
   | 셰이프 | **VM.Standard.A1.Flex · OCPU 2 · 메모리 12GB** — 이보다 크게 고르면 무료 한도를 넘는다. 「Always Free 사용 가능」 표시를 확인 |
   | 부트 볼륨 | 100GB(최소 47 · 전체 무료 200GB 이하) |
   | 네트워크 | 공용 서브넷 · **공용 IPv4 할당** |
   | SSH 키 | 키 쌍을 만들어 **개인 키를 내려받아 보관**(잃으면 접속 불가) |

   「out of host capacity」가 나오면 시간을 두고 다시 시도한다(서울은 AD 가 하나라 다른 AD 로 옮길 수 없다). 그래도 안 되면 PAYG 로 올리는 길이 있다 —
   Oracle 문서는 올려도 무료 한도 안은 과금하지 않는다고 하지만 **카드가 청구 대상이 되므로 예산 알림부터** 걸 것(이 선택은 사용자 몫).
3. **[사용자] VCN 보안 목록** — 인스턴스의 서브넷 → 보안 목록 → 수신 규칙 추가: `0.0.0.0/0` TCP **80** · **443**(22 는 기본으로 있다. 내 IP 로 좁히면 더 안전).
   HTTP/3 용 UDP 443 은 필요 없다(Caddyfile 에서 껐다).
4. **[사용자] VM 첫 설정** — 내 PC 에서(워크트리 `.claude\worktrees\oracle-migration` 에서):
   ```powershell
   scp -i <개인키> deploy\oracle\setup-vm.sh ubuntu@<VM_IP>:~/
   ssh -i <개인키> ubuntu@<VM_IP>
   ```
   VM 안에서 `bash setup-vm.sh` → 끝나면 **로그아웃 후 다시 로그인**(docker 그룹 적용). Docker·compose·git 설치, 80/443 방화벽, `/opt/placeos`(700) 생성.
5. **[사용자] 비밀 파일 올리기** — 내 PC 에서:
   ```powershell
   # build.env 만들기(네이버 지도 키 한 줄 — 값은 화면에 안 찍힌다)
   $l = Select-String -Path 'C:\Users\USER\Documents\Claude\Projects\SpaceOS\spaceos\apps\frontend\.env' -Pattern '^VITE_NAVER_MAPS_KEY_ID='
   [IO.File]::WriteAllText("$env:USERPROFILE\placeos-migration\build.env", ($l.Line.Trim() + "`n"), (New-Object Text.UTF8Encoding $false))

   scp -i <개인키> "$env:USERPROFILE\placeos-migration\placeos.env" ubuntu@<VM_IP>:/opt/placeos/placeos.env
   scp -i <개인키> "$env:USERPROFILE\placeos-migration\build.env"   ubuntu@<VM_IP>:/opt/placeos/build.env
   ```
   VM 에서 `chmod 600 /opt/placeos/*.env`.
6. **[사용자] 첫 배포**(VM — 이 PR 이 푸시된 뒤):
   ```bash
   git clone --depth 1 -b chore/oracle-migration-20261127 https://github.com/seoghyeonbag36-max/placeos.git /opt/placeos/src
   bash /opt/placeos/src/deploy/oracle/deploy.sh chore/oracle-migration-20261127
   ```
   빌드는 몇 분 걸린다(npm ci + pip + arm64). 끝에 「검증 통과: 상권 N곳 · gold 데이터 있음」이 나와야 한다 — CI 의 배포 검증과 같은 세 조건이다.
   실패하면 그 줄의 메시지를 그대로 가져온다. 의존성의 aarch64 휠이 없어 빌드가 멈추면 어느 패키지인지 보인다.
7. **외부에서 열리는지 먼저 본다**(DNS 를 바꾸기 **전**, 내 PC 에서):
   ```powershell
   curl.exe -sS -i http://<VM_IP>/ -H "Host: placeos.co.kr"
   ```
   `308` + `Location: https://placeos.co.kr/` 이면 VCN·방화벽·Caddy 가 맞다. 연결이 안 되면 3번(VCN)이나 setup-vm 의 iptables 를 본다.
8. **[사용자] DNS 전환(가비아)** — 현재 레코드는 [runbook-custom-domain-placeos-co-kr-2026-10-10.md](runbook-custom-domain-placeos-co-kr-2026-10-10.md) 참조.
   - 하루 전이면 `placeos.co.kr` TTL 을 300초로 낮춘다(이미 낮으면 생략).
   - 루트 `placeos.co.kr` **A 레코드를 `<VM_IP>` 로**(Firebase 의 A 레코드는 지운다 — 남기면 절반이 옛 곳으로 간다). AAAA 가 있으면 지운다.
   - `www`: CNAME 을 `placeos.co.kr` 로 바꾸거나 A 레코드 `<VM_IP>`.
   - 전환 뒤 첫 HTTPS 요청에서 Caddy 가 인증서를 받는다(수초~1분). `docker compose -f /opt/placeos/src/deploy/oracle/docker-compose.yml logs caddy` 로 `certificate obtained` 를 본다.
   - ⚠ 사이트 `placeos`(Firebase)를 **지우지 않는다**는 11-01 규칙은 이 전환으로 풀린다 — 도메인이 더는 그 사이트에 붙어 있지 않기 때문이다. 그래도 지우는 것은 안정화 뒤에 한다.
9. **[사용자] ODsay 허용 IP** — ODsay 콘솔에서 서버 키의 허용 IP 를 **VM 공용 IP 로 추가**(옛 `34.122.121.96` 은 만료 뒤 쓸모없다). 허용 IP 는 호출 서버의 송신 공인 IP 이고 이 VM 은 자기 공용 IP 로 나간다.
   등록 뒤 운영 사이트에서 대중교통 소요시간을 실제로 불러 확인한다([travel-times.md](travel-times.md) §Cloud Run 운영 연동).
   같은 이유로 **계정 DB(Neon)에 IP 허용 목록을 쓰고 있다면** 새 IP 를 넣어야 한다 — 쓰는지 확인 안 함. 다른 외부 키(DATA_GO_KR · BIZINFO · 카카오)에 IP 제한이 있는지도 같이 본다.
10. **컷오버 뒤 실화면 확인**(`https://placeos.co.kr`):
    - `/health` 200 · 지도 렌더(네이버) · 상권 목록 · 구글/네이버/카카오 로그인(리다이렉트 URI 는 도메인이 같아 바꿀 것 없다) · 교통 소요시간 · 로그인 없이 PPPP 네 화면.
    - 로컬 확인 스크립트: `py -3.11 scripts/pppp_screens_check.py` — 대상이 로컬이라 운영 확인은 사람이 눈으로 한다.
11. **정리**(안정화 뒤 · 모두 **사용자 승인 뒤**):
    - **Deploy 워크플로 끄기** — 체험이 만료되면 main 푸시마다 Cloud Run 배포가 실패한다: `gh workflow disable Deploy`. 이후 배포는 VM 에서 `bash /opt/placeos/src/deploy/oracle/deploy.sh`
      (원하면 SSH 로 그 한 줄을 부르는 새 워크플로를 후속 PR 로 — SSH 비밀키를 GitHub 시크릿에 두는 일이라 따로 정한다).
    - **업타임 감시 대체** — Cloud Monitoring 체크 4개는 GCP 와 함께 멈춘다. 외부 무료 모니터(예: `/health` + 분석 API 의 `"vacancy_source":"gold"` 본문 검사)를 사용자가 정한다.
    - **옛 주소** — `placeos.web.app` · `spaceos-twin.web.app` 은 Cloud Run 이 죽으면 깨진다. 사이트 설정을 `**` → `https://placeos.co.kr` 301 로 바꿔 `firebase deploy` 할지는 사용자 결정(Hosting 이 결제 비활성 프로젝트에서도 서빙되는지는 확인 안 함).
    - [deploy-cloud-run.md](deploy-cloud-run.md) 맨 위에 「2026-11-xx 부터 Oracle VM — 이 문서는 이전 기록」을 붙이고 CLAUDE.md 의 Infra 줄을 고친다(컷오버 확인 뒤 같은 PR).

## 5. 롤백

- **컷오버 전**(DNS 를 바꾸기 전): 아무것도 안 바뀐 것이다. Cloud Run 이 계속 서빙한다.
- **컷오버 후 · 만료 전**: 가비아 A 레코드를 Firebase 값으로 되돌린다(전환 직전에 현재 레코드를 **스크린샷으로 남겨 둔다**). 만료 뒤에는 Cloud Run 이 없어 되돌릴 곳이 없다.
- **새 배포가 깨졌을 때**: `deploy.sh` 가 검증 실패 시 되돌리는 명령(`IMAGE_TAG=<이전> docker compose … up -d`)을 출력한다. 이미지는 최근 3개를 남긴다.

## 6. 이 구성이 Cloud Run 과 다른 점

- **단일 VM = 단일 장애점.** Cloud Run 은 최대 3 인스턴스였다. 재부팅·Oracle 점검 때 수 분 내려갈 수 있다(`restart: unless-stopped` 로 자동 복귀).
- **유휴 회수 위험.** Oracle 은 7일간 CPU p95 · 네트워크 · (A1 은) 메모리가 모두 20% 미만이면 회수할 수 있다. 12GB 에 ~800MB 면 메모리는 20% 미만이다.
  VM 이 무상태이고 이미지가 코드에서 재현되므로 **잃어도 이 런북으로 다시 세운다.** PAYG 로 올리면 회수에서 빠지는지는 확인 못 했다.
- **좋아지는 점.** 서울 리전이면 지연이 us-central1 의 150~200ms 에서 수 ms 로 준다(KPI② 목표에 가까워진다). Cloud NAT 의 콜드 스타트 첫 연결 멈춤(30초~1분)이 사라진다 — 상시 가동이다.
- **압축·CDN.** Firebase 가 하던 CDN 캐시가 없다. 정적 파일은 앱이 직접 낸다(Oracle 송신 무료 한도가 크다). 느리면 그때 Cloudflare 무료 프록시를 앞에 둔다.
- **접속 로그** 를 켜지 않았다(받는 개인정보를 늘리지 않는다). 장애 추적이 필요해지면 Caddyfile 에 `log` 를 더하고 `PrivacyNote`·`privacy.html` 을 같이 고친다.

## 7. 미검증 (실제로 돌려야 안다)

- `setup-vm.sh` 전체(docker.io · docker-compose-v2 패키지명 · iptables 규칙 · netfilter-persistent).
- **arm64 빌드** — 확인한 aarch64 휠은 bcrypt · psycopg2-binary · SQLAlchemy 뿐이다. pydantic-core · cryptography · uvloop · httptools · greenlet 은 확인이 중단됐다(없으면 gcc 로 소스 빌드 — Dockerfile 에 gcc 가 있어 대부분 통과하나 느릴 수 있다).
- Caddyfile 문법(`caddy validate` 를 못 돌렸다 — Docker 데몬이 꺼져 있었다) · Let's Encrypt 발급.
- compose 의 `FORWARDED_ALLOW_IPS=*` 가 uvicorn 에 적용되는지.
- 서울 리전 A1 의 용량 · 홈 리전이 서울인지(가입 화면에서 서울이 안 보인다는 보고가 11-27 에 있었다 — 어느 리전이 됐는지 확인 필요).
- Neon · 외부 API 키의 IP 제한 여부(§4-9).
