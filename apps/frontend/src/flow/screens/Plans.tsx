/**
 * 정액 상품 — 정액 광고 · 구독 · 정보 판매(2026-11-18 · docs/decision-owner-direct-matching-2026-11-18.md).
 *
 * ⛔ 성사·중개 수수료는 없다 — 정해진 금액(또는 무료)의 상품뿐이다(공인중개사법 제2조·제48조).
 * 결제는 PG 없이 「신청 → 계좌이체 → 운영자 입금 확인」(docs/decision-lightweight-first-2026-10-05.md §3).
 * 가격이 정해지기 전에는 「가격 확정 전」으로 보이고 신청만 받는다.
 */
import { useState } from "react";
import {
  getDirectProducts, myDirectListings, myDirectPurchases, requestDirectPurchase,
  type DirectApiError, type DirectProduct, type DirectPurchaseResult,
} from "@/lib/api";
import DirectNotice from "@/components/direct/DirectNotice";
import "@/components/direct/direct.css";
import { useFlow } from "../context";
import { useLoad } from "../data";
import { go, useHash } from "../route";
import { FlowScreen, LoadError, SkeletonRows } from "../ui";

const price = (p: DirectProduct) => (p.price_krw === 0 ? "무료" : p.price_krw == null ? "가격 확정 전" : `${p.price_krw.toLocaleString("ko-KR")}원`);
const KIND: Record<DirectProduct["kind"], string> = { free: "무료", ad: "광고", report: "리포트", subscription: "구독" };
const PURCHASE_STATUS = { requested: "입금 확인 대기", paid: "입금 확인됨", fulfilled: "이행 완료", cancelled: "취소" } as const;

/** `#/plans?target=…&product=…` — 매물 화면에서 넘어올 때 대상·상품을 미리 고른다 */
function useQuery(): URLSearchParams {
  const hash = useHash();
  return new URLSearchParams(hash.split("?")[1] ?? "");
}

function Apply({ product, presetTarget, onDone }: { product: DirectProduct; presetTarget: string | null; onDone: (r: DirectPurchaseResult) => void }) {
  const { token, requireLogin } = useFlow();
  const mine = useLoad(token && product.side === "owner" ? `direct-mine-plans:${token}` : null, () => myDirectListings(token!));
  const [target, setTarget] = useState(presetTarget ?? "");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const send = () => requireLogin("login", null, (t) => {
    setError(null);
    requestDirectPurchase(t, { product: product.key, target_id: target, depositor_name: name.trim() })
      .then(onDone).catch((e: DirectApiError) => setError(e.detail ?? "신청하지 못했어요."));
  });
  return (
    <div className="dr-form">
      {product.side === "owner" ? (
        <label className="dr-field"><span>대상 매물</span>
          <select value={target} onChange={(e) => setTarget(e.target.value)}>
            <option value="">고르세요</option>
            {mine.status === "ready" && mine.data.items.map((l) => <option key={l.id} value={l.id}>{l.title} · {l.status_label}</option>)}
          </select>
        </label>
      ) : (
        <p className="fl-note">{target ? "고른 매물로 신청해요." : "매물 상세에서 「계약 전 확인 리포트」를 눌러 오면 대상이 채워져요."}</p>
      )}
      <label className="dr-field"><span>입금자명</span><input value={name} maxLength={50} onChange={(e) => setName(e.target.value)} /></label>
      {error && <p className="dr-error" role="alert">{error}</p>}
      <button type="button" className="fl-btn fl-btn-strong" disabled={!target || !name.trim()} onClick={send}>신청하기</button>
    </div>
  );
}

export function Plans() {
  const { token } = useFlow();
  const q = useQuery();
  const presetTarget = q.get("target");
  const presetProduct = q.get("product");
  const products = useLoad("direct-products", getDirectProducts);
  const mine = useLoad(token ? `direct-purchases:${token}` : null, () => myDirectPurchases(token!));
  const [open, setOpen] = useState<string | null>(presetProduct);
  const [done, setDone] = useState<DirectPurchaseResult | null>(null);
  if (products.status === "loading") return <FlowScreen back="/me" title="정액 상품"><SkeletonRows n={4} /></FlowScreen>;
  if (products.status === "error") return <FlowScreen back="/me" title="정액 상품"><LoadError what="상품" error={products.error} onRetry={products.retry} /></FlowScreen>;
  const list = products.data.products;
  const section = (side: "owner" | "founder") => (
    <ul className="dr-products" aria-label={side === "owner" ? "건물주 상품" : "창업자 상품"}>
      {list.filter((p) => p.side === side).map((p) => (
        <li key={p.key} className="dr-product">
          <h3>{p.title} <span className="fl-badge is-obs">{KIND[p.kind]}</span></h3>
          <p>{p.desc}</p>
          <p><span className="dr-price">{price(p)}</span> · {p.unit}</p>
          {p.kind !== "free" && (p.available
            ? (open === p.key
              ? <Apply product={p} presetTarget={presetTarget} onDone={(r) => { setDone(r); setOpen(null); mine.retry(); }} />
              : <button type="button" className="fl-btn fl-btn-weak" onClick={() => setOpen(p.key)}>신청</button>)
            : <p className="fl-note">준비 중이에요.</p>)}
          {p.kind === "free" && <button type="button" className="fl-btn fl-btn-weak" onClick={() => go("/owner/new")}>빈 자리 올리기</button>}
        </li>
      ))}
    </ul>
  );
  return (
    <FlowScreen back="/me" title="정액 상품" sub="정해진 금액의 상품만 있어요. 성사·중개 수수료는 받지 않아요.">
      {done && (
        <div className="dr-missing" role="status">
          신청했어요 — {done.title}. {done.instructions.message} {done.instructions.payment}
        </div>
      )}
      <h2 className="fl-h2">건물주</h2>
      {section("owner")}
      <h2 className="fl-h2">창업자</h2>
      {section("founder")}
      <p className="fl-source">{products.data.payment}</p>
      {mine.status === "ready" && mine.data.items.length > 0 && <>
        <h2 className="fl-h2">내 신청</h2>
        <ul className="fl-facts">
          {mine.data.items.map((p) => <li key={p.id}>{p.title} · {PURCHASE_STATUS[p.status]}{p.amount_krw != null ? ` · ${p.amount_krw.toLocaleString("ko-KR")}원` : ""}</li>)}
        </ul>
      </>}
      <DirectNotice text={products.data.notice} />
    </FlowScreen>
  );
}
