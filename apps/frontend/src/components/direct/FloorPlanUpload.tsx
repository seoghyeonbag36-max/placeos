/**
 * 건물주의 층 배치도 사진 올리기 — 내 매물(층) 화면에 선다(2026-11-22 · docs/decision-pppp-owner-founder-2026-11-22.md).
 *
 * 올리면 Page 지도의 그 층에서 개략(가상) 배치도 **대신** 이 사진이 보인다(소유자 확인을 거쳐 게시된 매물만 공개 — L3).
 * ⛔ 사진은 건물주 본인이 올린다 — PlaceOS 는 그리거나 고치지 않고, 사진이 실제와 같다고 보증하지도 않는다.
 * 줄이기·EXIF 제거는 브라우저에서 먼저(lib/floorPlanImage) 하고, 서버가 형식·크기·메타데이터를 다시 본다.
 */
import { useEffect, useRef, useState } from "react";
import { deleteDirectFloorPlan, fetchMyFloorPlanUrl, putDirectFloorPlan, type DirectApiError, type DirectOwnerListing } from "@/lib/api";
import { prepareFloorPlan, type PreparedFloorPlan } from "@/lib/floorPlanImage";

const kb = (n: number) => (n >= 1_000_000 ? `${(n / 1_000_000).toFixed(1)}MB` : `${Math.max(1, Math.round(n / 1000))}KB`);

export default function FloorPlanUpload({ listing, token, onChanged }: {
  listing: DirectOwnerListing; token: string; onChanged: (message: string) => void;
}) {
  const plan = listing.floor_plan ?? null;
  // 내 사진 미리보기는 사진 주소(v)로 묶는다 — 바뀌면 지난 사진을 보이지 않는다(효과 안에서 동기로 비우지 않는다)
  const [mine, setMine] = useState<{ key: string; url: string | null } | null>(null);
  const [picked, setPicked] = useState<PreparedFloorPlan | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);

  const planUrl = plan?.url ?? null;
  const current = planUrl && mine?.key === planUrl ? mine.url : null;
  // 올린 사진 미리보기 — 로그인 헤더가 필요해 받아 와 object URL 로 보인다(바뀌면 새로, 사라질 때 revoke)
  useEffect(() => {
    if (!planUrl) return;
    let live = true;
    let made: string | null = null;
    void fetchMyFloorPlanUrl(token, planUrl).then((url) => {
      if (!live) { if (url) URL.revokeObjectURL(url); return; }
      made = url;
      setMine({ key: planUrl, url });
    });
    return () => { live = false; if (made) URL.revokeObjectURL(made); };
  }, [planUrl, token]);

  useEffect(() => () => { if (picked) URL.revokeObjectURL(picked.previewUrl); }, [picked]);

  const choose = async (file: File | undefined) => {
    setError(null);
    if (!file) return;
    try {
      setPicked(await prepareFloorPlan(file));
    } catch (e) {
      setPicked(null);
      setError(e instanceof Error ? e.message : "사진을 읽지 못했어요.");
    }
  };
  const upload = async () => {
    if (!picked) return;
    setBusy(true);
    setError(null);
    try {
      await putDirectFloorPlan(token, listing.id, { mime: picked.mime, data: picked.data });
      setPicked(null);
      if (input.current) input.current.value = "";
      onChanged(plan ? "배치도 사진을 바꿨어요" : "배치도 사진을 올렸어요");
    } catch (e) {
      const err = e as DirectApiError;
      setError(err.status === 503 ? "배치도 사진 기능을 준비하고 있어요. 잠시 뒤 다시 시도해 주세요." : (err.detail ?? "올리지 못했어요. 잠시 뒤 다시 시도해 주세요."));
    } finally {
      setBusy(false);
    }
  };
  const remove = async () => {
    setBusy(true);
    setError(null);
    try {
      await deleteDirectFloorPlan(token, listing.id);
      onChanged("배치도 사진을 지웠어요");
    } catch (e) {
      setError((e as DirectApiError).detail ?? "지우지 못했어요.");
    } finally {
      setBusy(false);
    }
  };

  const public_ = listing.status === "published" && listing.verification?.status === "verified";
  return (
    <section aria-label="층 배치도 사진" className="dr-plan">
      <h2 className="fl-h2">층 배치도 사진</h2>
      <p className="fl-note">
        이 층의 실제 배치도(도면 사진·스캔)를 올리면, Page 지도에서 개략 배치도 <b>대신</b> 이 사진이 보여요.
        {public_ ? " 지금 게시 중이라 올리면 바로 보여요." : " 소유자 확인을 거쳐 게시된 뒤부터 다른 이용자에게 보여요."}{" "}
        올릴 때 촬영 위치·기기 정보는 지워요. 연락처·개인정보가 보이지 않게 가려 주세요.
      </p>
      {plan && (
        <figure className="dr-plan-fig">
          {current ? <img src={current} alt={`${listing.title} 배치도(내가 올린 사진)`} /> : <p className="fl-source">사진을 불러오는 중…</p>}
          <figcaption className="fl-source">올린 사진 · {plan.width}×{plan.height}px · {kb(plan.size_bytes)}{plan.updated_at ? ` · ${plan.updated_at.slice(0, 10)}` : ""}</figcaption>
        </figure>
      )}
      <label className="dr-field">
        <span>{plan ? "다른 사진으로 바꾸기" : "배치도 사진 고르기"}</span>
        <input ref={input} type="file" accept="image/jpeg,image/png,image/webp" disabled={busy}
          onChange={(e) => void choose(e.target.files?.[0])} />
        <small>JPEG·PNG · 올리기 전에 이 브라우저에서 긴 변 1600px 이하로 줄여요.</small>
      </label>
      {picked && (
        <figure className="dr-plan-fig">
          <img src={picked.previewUrl} alt="올릴 배치도 사진 미리보기" />
          <figcaption className="fl-source">줄인 사진 · {picked.width}×{picked.height}px · {kb(picked.bytes)}</figcaption>
        </figure>
      )}
      <div className="fl-actions">
        {picked && <button type="button" className="fl-btn fl-btn-strong" disabled={busy} onClick={() => void upload()}>{plan ? "이 사진으로 바꾸기" : "이 사진으로 올리기"}</button>}
        {plan && <button type="button" className="fl-btn" disabled={busy} onClick={() => void remove()}>사진 지우기</button>}
      </div>
      {error && <p className="dr-error" role="alert">{error}</p>}
    </section>
  );
}
