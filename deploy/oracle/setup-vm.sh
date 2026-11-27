#!/usr/bin/env bash
# PlaceOS — Oracle VM(Ubuntu 24.04 · aarch64) 첫 설정. 한 번만, ubuntu 사용자로 실행한다.
#   ⚠ 2026-11-27 작성 · 실제 VM 에서 돌려 본 적 없다(미검증). 실패하면 그 줄에서 멈추니(set -e) 출력부터 읽는다.
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
sudo apt-get update
# Ubuntu 저장소 패키지만 쓴다(원격 스크립트를 내려받아 root 로 돌리지 않는다).
sudo apt-get install -y docker.io docker-compose-v2 git curl python3 iptables-persistent
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"     # 적용은 다시 로그인한 뒤

# 호스트 방화벽 — Oracle 이미지의 INPUT 체인에는 REJECT 가 있다.
# Docker 가 게시한 포트는 보통 이 체인을 안 타지만, 막혀 있으면 80/443 이 안 열리는 것이 Oracle 의 고전적 함정이라
# 미리 ACCEPT 를 REJECT 앞에 넣는다(앞에 넣는 것이라 SSH 를 끊을 일은 없다). VCN 보안 목록 규칙은 콘솔에서 따로 연다.
for p in 80 443; do
  if ! sudo iptables -C INPUT -p tcp --dport "$p" -m state --state NEW -j ACCEPT 2>/dev/null; then
    n="$(sudo iptables -L INPUT --line-numbers -n | awk '/REJECT/ {print $1; exit}')"
    if [ -n "$n" ]; then
      sudo iptables -I INPUT "$n" -p tcp --dport "$p" -m state --state NEW -j ACCEPT
    else
      sudo iptables -A INPUT -p tcp --dport "$p" -m state --state NEW -j ACCEPT
    fi
  fi
done
sudo netfilter-persistent save

# 비밀값·빌드 변수·소스가 놓이는 곳. 소유자만 읽는다.
sudo mkdir -p /opt/placeos
sudo chown "$USER":"$USER" /opt/placeos
chmod 700 /opt/placeos

echo
echo "끝. 다시 로그인(docker 그룹 적용) → /opt/placeos/placeos.env · build.env 를 놓고 ./deploy.sh (런북 §3~4)"
