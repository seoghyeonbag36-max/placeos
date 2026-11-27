#!/usr/bin/env bash
# PlaceOS — Oracle VM 배포. VM 에서 ubuntu 사용자로 실행한다.
#   사용: bash /opt/placeos/src/deploy/oracle/deploy.sh [브랜치|커밋SHA]      (기본 main)
#   (첫 배포는 먼저 `git clone --depth 1 -b <브랜치> <저장소> /opt/placeos/src` — 런북 §4-6)
#
# 하는 일: 저장소 받기(얕은 클론) → 이미지 빌드(arm64 · VM 에서) → compose 로 교체 → 배포 검증.
# 검증은 .github/workflows/deploy.yml 의 「배포 검증」과 같은 세 가지다
#   (/health 200 · 분석 API 가 gold · 상권 50곳 이상) — 200 인데 데이터가 빈 고장이 이 저장소의 반복 실패 양식이다.
set -euo pipefail

REPO="${REPO:-https://github.com/seoghyeonbag36-max/placeos.git}"
SRC="${SRC:-/opt/placeos/src}"
REF="${1:-main}"
BASE="http://127.0.0.1:8080"          # compose 가 루프백에만 연 포트
COMPOSE=(docker compose --env-file /opt/placeos/build.env -f "$SRC/deploy/oracle/docker-compose.yml")

for f in /opt/placeos/placeos.env /opt/placeos/build.env; do
  [ -s "$f" ] || { echo "중단: $f 가 없거나 비어 있다 (런북 §3 참고)"; exit 1; }
done

if [ ! -d "$SRC/.git" ]; then
  git clone --depth 1 "$REPO" "$SRC"
fi
git -C "$SRC" fetch --depth 1 origin "$REF"
git -C "$SRC" reset --hard FETCH_HEAD
SHA="$(git -C "$SRC" rev-parse --short=12 HEAD)"
echo "배포 커밋: $SHA"

PREV_IMAGE="$(docker inspect -f '{{.Config.Image}}' placeos-web-1 2>/dev/null || true)"

export IMAGE_TAG="$SHA"
"${COMPOSE[@]}" up -d --build

fail() {
  echo "검증 실패: $1"
  if [ -n "$PREV_IMAGE" ]; then
    echo "되돌리려면: IMAGE_TAG=${PREV_IMAGE##*:} ${COMPOSE[*]} up -d"
  fi
  exit 1
}

code=000
for _ in $(seq 1 30); do
  code="$(curl -sS -m 10 -o /dev/null -w '%{http_code}' "$BASE/health" 2>/dev/null || true)"
  [ "$code" = "200" ] && break
  sleep 5
done
[ "$code" = "200" ] || fail "health ${code}"

body="$(curl -sSL -m 60 "$BASE/api/v1/commercial-districts")"
echo "$body" | grep -q '"vacancy_source":"gold"' || fail "분석 API 에 gold 데이터가 없다"
n="$(echo "$body" | python3 -c 'import json,sys; print(len(json.load(sys.stdin)))')"
[ "$n" -ge 50 ] || fail "상권이 ${n}곳뿐이다 (50 미만)"
echo "검증 통과: 상권 ${n}곳 · gold 데이터 있음 · 커밋 ${SHA}"

# 이미지 정리 — 최근 3개 태그만 남긴다(롤백용). 실행 중인 것은 rmi 가 거절한다.
docker image prune -f >/dev/null
docker images placeos-web --format '{{.Tag}}' | tail -n +4 | xargs -r -I{} docker rmi "placeos-web:{}" 2>/dev/null || true
