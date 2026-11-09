import { defaultInteriorDesign, type InteriorDesign } from "./interiorDesign";

/** 그대로 두는 칸(2026-11-09 사용자 지정) — 디자인 방향 · 공사 범위 · 기존 내부 화장실 · 공사 전 체크리스트(+ 브랜드 색). */
export default function InteriorDesignControls({ value, onChange }: {
  value: InteriorDesign; onChange: (value: InteriorDesign) => void;
}) {
  const patch = (change: Partial<InteriorDesign>) => onChange({ ...value, ...change });
  return <section aria-label="상권 맞춤 디자인 설정" className="interior-design">
    <div className="interior-fields">
      <label>디자인 방향<select value={value.direction} onChange={(e) => patch({ direction: e.target.value })}>{["상권과 조화", "기본", "차별화"].map((x) => <option key={x}>{x}</option>)}</select></label>
      <label>공사 범위<select value={value.scope} onChange={(e) => patch({ scope: e.target.value })}>{["미정", "전체 공사", "부분 공사 · 바닥과 천장 유지"].map((x) => <option key={x}>{x}</option>)}</select></label>
      <label>기존 내부 화장실<select value={value.reuse} onChange={(e) => patch({ reuse: e.target.value })}>{["미확인", "유지 희망 · 현장 확인 필요", "변경 검토"].map((x) => <option key={x}>{x}</option>)}</select></label>
      <label>브랜드 색·적용 위치<input value={value.brand} maxLength={80} placeholder="예: 청록색 · 간판과 포인트 벽" onChange={(e) => patch({ brand: e.target.value })} /></label>
    </div>
    <h3>공사 전 체크리스트</h3>
    <ul><li>출입문·피난·접근 동선과 실제 내부 도면 대조</li><li>전기·급배수·배기와 업종별 설비 확인</li><li>간판 허가·영업신고와 건물주 원상복구 범위 확인</li><li>자재 실물과 조명 아래 상품 색 확인</li><li>업체 실측 견적 확보 · 기존 Posting 투자비와 중복 합산 금지</li></ul>
    <button type="button" onClick={() => onChange(defaultInteriorDesign())}>디자인 설정 초기화</button>
  </section>;
}
