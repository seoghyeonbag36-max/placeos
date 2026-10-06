/**
 * 저장한 결과 — 「결과 저장」 버튼과 목록(다시 보기·삭제). Posting·Program 이 같이 쓴다 (2026-10-06).
 *
 * 왜: 계산·생성 결과가 화면 상태에만 있어 새로고침·탭 종료에 사라졌다. 파일럿은 "4주 사용 후 피드백"(KPI③)을
 * 재는데, 그동안 만든 계획이 남지 않으면 가치를 체감할 근거도 남지 않는다
 * (docs/finding-project-review-4roles-2026-10-06.md §2-4 · 소유자 결정).
 *
 * - **고른 것만** 남긴다(자동 저장하지 않는다) — 받는 정보를 최소로 한다는 원칙(decision-lightweight-first).
 * - 다시 보기는 **읽기 전용**이다. 저장한 결과를 지금 화면의 입력 상태로 되살리지 않는다 — 자리·상권 목록이
 *   그새 바뀌었을 수 있고, 되살린 입력이 지금 데이터와 어긋나면 결과가 거짓말이 된다. 그래서 저장 시각을 함께 보인다.
 * - 로그인한 사용자만 보인다(서버도 JWT 사용자만 받는다). 익명이면 아무것도 그리지 않는다.
 */
import { useEffect, useState, type ReactNode } from "react";
import { Button } from "@/design/components/Button";
import { useSignedIn } from "@/hooks/useSignedIn";
import { deleteSavedResult, listSavedResults, saveResult, type SavedResult, type SavedResultInput,
  type SavedResultKind } from "@/lib/api";
import { loadToken } from "@/lib/session";
import "./SavedResults.css";

const when = (iso: string) => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString("ko-KR", { dateStyle: "short", timeStyle: "short" });
};

/** 「결과 저장」 — 저장에 성공하면 onSaved 로 목록을 다시 받게 한다. 익명이면 그리지 않는다. */
export function SaveResultButton({ build, onSaved, disabled }: {
  /** 누르는 순간의 결과를 저장 형식으로 만든다(없으면 null — 버튼이 눌리지 않는다) */
  build: () => SavedResultInput | null;
  onSaved: () => void;
  disabled?: boolean;
}) {
  const signedIn = useSignedIn();
  const [state, setState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  if (!signedIn) return null;
  const save = async () => {
    const token = loadToken();
    const body = build();
    if (!token || !body) return;
    setState("saving");
    try {
      await saveResult(token, body);
      setState("saved");
      onSaved();
    } catch {
      setState("error");
    }
  };
  return (
    <span className="saved-save">
      <Button variant="ghost" type="button" onClick={save} disabled={disabled || state === "saving"}>
        {state === "saving" ? "저장 중…" : "결과 저장"}
      </Button>
      {state === "saved" && <span role="status" className="saved-msg">저장했습니다 — 아래 「저장한 결과」에서 다시 볼 수 있습니다.</span>}
      {state === "error" && <span role="alert" className="saved-msg is-bad">저장하지 못했습니다. 다시 시도해 주세요.</span>}
    </span>
  );
}

/** 저장한 결과 목록 — kind 로 거른다. refreshKey 가 바뀌면 다시 받는다. */
export default function SavedResults({ kind, refreshKey, render }: {
  kind: SavedResultKind;
  refreshKey: number;
  render: (item: SavedResult) => ReactNode;
}) {
  const signedIn = useSignedIn();
  const [items, setItems] = useState<SavedResult[] | null>(null);
  const [error, setError] = useState(false);
  const [openId, setOpenId] = useState<string | null>(null);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    const token = loadToken();
    // 로그아웃 상태면 아래 렌더가 아무것도 그리지 않는다 — 여기서 상태를 비울 필요가 없다.
    if (!signedIn || !token) return;
    let alive = true;
    listSavedResults(token)
      .then((all) => { if (alive) { setItems(all.filter((r) => r.kind === kind)); setError(false); } })
      .catch(() => { if (alive) setError(true); });
    return () => { alive = false; };
  }, [signedIn, kind, refreshKey, reload]);

  if (!signedIn) return null;
  const remove = async (id: string) => {
    const token = loadToken();
    if (!token) return;
    try {
      await deleteSavedResult(token, id);
    } catch {
      // 이미 지워졌거나(404) 일시 오류 — 목록을 다시 받아 실제 상태를 보인다.
    }
    if (openId === id) setOpenId(null);
    setReload((n) => n + 1);
  };

  return (
    <section className="saved-results" aria-label="저장한 결과">
      <h3 className="saved-head">저장한 결과 {items ? `(${items.length})` : ""}</h3>
      {error && <p role="alert" className="saved-msg is-bad">저장한 결과를 불러오지 못했습니다.</p>}
      {items && items.length === 0 && <p className="saved-empty">아직 저장한 결과가 없습니다. 결과 아래 「결과 저장」으로 남길 수 있습니다.</p>}
      {items && items.length > 0 && (
        <ul className="saved-list">
          {items.map((it) => (
            <li key={it.id} className="saved-item">
              <div className="saved-row">
                <span className="saved-title">{it.title}</span>
                <span className="saved-when">{when(it.createdAt)} 저장</span>
                <Button variant="ghost" type="button" aria-expanded={openId === it.id}
                  onClick={() => setOpenId(openId === it.id ? null : it.id)}>
                  {openId === it.id ? "접기" : "보기"}
                </Button>
                <Button variant="ghost" type="button" aria-label={`${it.title} 삭제`} onClick={() => remove(it.id)}>삭제</Button>
              </div>
              {openId === it.id && (
                <div className="saved-body">
                  <p className="saved-note">{when(it.createdAt)}에 저장한 결과입니다 — 그 뒤 데이터가 바뀌었을 수 있습니다.</p>
                  {render(it)}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
