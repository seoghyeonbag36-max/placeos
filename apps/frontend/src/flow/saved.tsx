/**
 * 저장 — 후보 자리(♡) · 본전 계산 · 예산 점검 · 검증 계획(화면설계서 5판 C5).
 *
 * 저장은 **로그인이 필요한 유일한 일**이다(검증 계획 AI 생성과 함께). 그래서 저장 버튼이 로그인 시트의
 * 입구이고, 로그인하면 누르려던 저장을 이어서 한다. 정본은 백엔드 `/auth/results`(사용자당 30건 · 64KB)다.
 * 자리 저장은 5판에서 `kind: "space"` 로 새로 생겼다.
 */
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { deleteSavedResult, listSavedResults, saveResult, type SavedResult, type SavedResultKind } from "@/lib/api";
import { SavedContext, useFlow, type ResumeKind } from "./context";
import { go } from "./route";
import type { SpaceItem } from "./spaces";

const SAVE_FAILED = "저장하지 못했어요. 잠시 뒤 다시 눌러 주세요.";

export function SavedProvider({ children }: { children: ReactNode }) {
  const { token, state, requireLogin, toast } = useFlow();
  const [results, setResults] = useState<SavedResult[] | null>(null);
  useEffect(() => {
    if (!token) return;
    let alive = true;
    listSavedResults(token).then((r) => { if (alive) setResults(r); }, () => { if (alive) setResults([]); });
    return () => { alive = false; };
  }, [token]);
  const visible = token ? results : null;

  const spaceResult = useCallback((spaceId: string) =>
    visible?.find((r) => r.kind === "space" && r.payload?.spaceId === spaceId) ?? null, [visible]);
  const savedSpaces = useMemo(() => new Set((visible ?? []).filter((r) => r.kind === "space")
    .map((r) => String(r.payload?.spaceId ?? ""))), [visible]);

  const toggleSaveSpace = useCallback((item: SpaceItem, want: boolean | null, resume: ResumeKind | null = null) => {
    const existing = spaceResult(item.id);
    const target = want ?? !existing;
    if (!target) {
      if (!existing || !token) return;
      deleteSavedResult(token, existing.id).then(() => {
        setResults((rs) => rs?.filter((r) => r.id !== existing.id) ?? rs);
        toast("후보에서 뺐어요");
      }, () => toast(SAVE_FAILED));
      return;
    }
    if (existing) return;
    requireLogin("save", resume, (t) => {
      saveResult(t, {
        kind: "space", title: `${item.name} ${item.floor >= 1 ? `${item.floor}층` : "지하"}`, districtId: state.districtId,
        payload: { spaceId: item.id, buildingId: item.buildingId, name: item.name, floor: item.floor, areaPy: item.areaPy,
          monthlyRent: item.monthlyRent, certainty: item.certainty, calculable: item.calculable, lat: item.lat, lng: item.lng },
      }).then((r) => {
        setResults((rs) => [r, ...(rs ?? [])]);
        toast("후보에 저장했어요", { label: "보기", onClick: () => go("/home") });
      }, () => toast(SAVE_FAILED));
    });
  }, [spaceResult, token, requireLogin, toast, state.districtId]);

  const saveOutcome = useCallback((kind: Exclude<SavedResultKind, "space">, title: string, payload: Record<string, unknown>, resume: ResumeKind) => {
    requireLogin("save", resume, (t) => {
      saveResult(t, { kind, title, districtId: state.districtId, payload }).then((r) => {
        setResults((rs) => [r, ...(rs ?? [])]);
        toast("저장했어요", { label: "보기", onClick: () => go("/home") });
      }, () => toast(SAVE_FAILED));
    });
  }, [requireLogin, toast, state.districtId]);

  const removeResult = useCallback((id: string) => {
    if (!token) return;
    deleteSavedResult(token, id).then(() => setResults((rs) => rs?.filter((r) => r.id !== id) ?? rs), () => toast("지우지 못했어요"));
  }, [token, toast]);

  const value = useMemo(() => ({ savedSpaces, toggleSaveSpace, saveOutcome, results: visible, removeResult }),
    [savedSpaces, toggleSaveSpace, saveOutcome, visible, removeResult]);
  return <SavedContext.Provider value={value}>{children}</SavedContext.Provider>;
}
