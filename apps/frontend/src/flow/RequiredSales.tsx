/**
 * 「이 층 조건이면 하루 몇 개를 팔아야 하나」 — 요구 판매량(2026-11-23 · 고양·파주 먼저).
 *
 * 매출 재료가 없는 도시(고양·파주)는 본전 시점을 답하지 않는다(`payback_unavailable_reason`). 그렇다고 아무것도 안 보이면
 * 창업자는 숫자 없이 서야 한다 — 요구 판매량은 **월세 + 내가 아는 비용**만으로 서고, 매출 추정이 필요 없다.
 * 계산은 `lib/menuPlan.menuBep` 그대로(식: BEP 월매출 = (임대료 + 기타 고정비) ÷ (1 − 변동비율)).
 *
 * 기본값을 만들지 않는다 — 객단가·변동비율·기타 고정비·영업일을 **전부** 직접 넣어야 계산한다(`areaBep` 과 같은 원칙).
 * 결과는 「필요한 양」이지 「이 상권에서 팔릴 양」이 아니다 — 화면이 그 구분을 밝힌다.
 */
import { useState } from "react";
import { menuBep } from "@/lib/menuPlan";
import { MoneyField } from "./ui";

const toNumber = (text: string): number => (text.trim() === "" ? NaN : Number(text.replace(/[^\d]/g, "")));

export function RequiredSales({ rentMan, rentIsShared }: { rentMan: number; rentIsShared: boolean }) {
  const [price, setPrice] = useState("");
  const [variable, setVariable] = useState("");
  const [fixed, setFixed] = useState("");
  const [days, setDays] = useState("");
  const complete = [price, variable, fixed, days].every((t) => t.trim() !== "");
  const result = complete
    ? menuBep({ rent: rentMan, otherFixed: toNumber(fixed), avgPrice: toNumber(price),
        costRate: toNumber(variable) / 100, days: toNumber(days) })
    : null;
  return (
    <section className="fl-required-sales" aria-label="요구 판매량">
      <h2 className="fl-h2">이 층 조건이면 몇 개를 팔아야 하나</h2>
      <p className="fl-muted">
        월세 {rentMan.toLocaleString("ko-KR")}만원{rentIsShared ? "(같은 시의 임대 통계를 함께 쓴 추정)" : "(임대 통계 추정)"}에,
        아는 비용을 넣으면 본전에 필요한 하루 판매 개수를 계산해요. 매출 추정은 쓰지 않아요.
      </p>
      <MoneyField label="판매 1건당 평균 금액" suffix="원" value={price} onChange={setPrice} />
      <MoneyField label="매출 대비 재료비·수수료 등" suffix="%" value={variable} onChange={setVariable}
        hint="없으면 0을 직접 넣어요" />
      <MoneyField label="월 기타 고정비 (인건비 등, 월세 제외)" suffix="만원" value={fixed} onChange={setFixed}
        hint="없으면 0을 직접 넣어요" />
      <MoneyField label="한 달 영업일" suffix="일" value={days} onChange={setDays} />
      {!complete && <p role="status" className="fl-muted">네 칸을 모두 넣으면 계산해요. 기본값은 만들지 않아요.</p>}
      {complete && !result && (
        <p role="status" className="fl-muted">입력 범위를 확인해 주세요. 재료비 비율은 100% 미만, 영업일은 1~31일이에요.</p>
      )}
      {result && (
        <dl className="fl-facts-list" aria-label="요구 판매량 결과">
          <div><dt>한 달 본전 매출</dt><dd>{Math.round(result.breakEvenRevenue).toLocaleString("ko-KR")}만원</dd></div>
          <div><dt>하루 필요 판매량</dt><dd>{result.dailySales.toLocaleString("ko-KR")}건</dd></div>
        </dl>
      )}
      <p className="fl-source">
        필요한 양이에요. 이 상권에서 실제로 팔릴 양이 아니에요(고양·파주는 매출 자료가 없어요). 보증금·권리금·인테리어 회수는 빠져 있어요.
      </p>
    </section>
  );
}
