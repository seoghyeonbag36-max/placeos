import { DESIGN_CONCEPTS, DESIGN_KEYWORDS, defaultInteriorDesign, type InteriorDesign } from "./interiorDesign";

export default function InteriorDesignControls({ value, onChange }: {
  value: InteriorDesign; onChange: (value: InteriorDesign) => void;
}) {
  const concept = DESIGN_CONCEPTS.find((c) => c.name === value.concept);
  const patch = (change: Partial<InteriorDesign>) => onChange({ ...value, ...change });
  return <section aria-label="상권 맞춤 디자인 설정" className="interior-design">
    <h3>키워드로 공간 구상하기</h3>
    <p>참고 HTML의 디자인 예시입니다. 상권별 리뷰 비율과 적합도는 확인된 자료가 없어 표시하지 않습니다. 원하는 요소를 직접 선택하세요.</p>
    <div className="interior-design-keywords">{DESIGN_KEYWORDS.map((keyword) => <article key={keyword.name}>
      <h4>#{keyword.name}</h4><p>{keyword.element}</p>
      <div className="interior-strength" role="group" aria-label={`${keyword.name} 강도`}>{["끔", "약", "중", "강"].map((level, index) =>
        <button type="button" key={level} aria-pressed={(value.levels[keyword.name] ?? 0) === index}
          onClick={() => patch({ levels: { ...value.levels, [keyword.name]: index } })}>{level}</button>)}</div>
      {!!value.levels[keyword.name] && <p>확인: {keyword.check}</p>}
    </article>)}</div>
    {!!value.levels["노출 콘크리트"] && !!value.levels["우드톤"] && <p role="status">바닥 소재가 겹칩니다. 콘크리트와 원목의 적용 구역을 구조·운영 제약에 적어주세요.</p>}
    <h3>인테리어 콘셉트</h3>
    <p>자동 추천 순위가 없는 선택용 예시 · 실제 자리에 대한 설계안이 아닙니다.</p>
    <div className="interior-concepts">{DESIGN_CONCEPTS.map((item) => <button type="button" key={item.name}
      aria-pressed={value.concept === item.name} onClick={() => patch({ concept: item.name })}>
      <strong>{item.name}</strong><span>{item.material}</span><span>{item.lighting}</span>
    </button>)}</div>
    <div className="interior-fields">
      <label>디자인 방향<select value={value.direction} onChange={(e) => patch({ direction: e.target.value })}>{["상권과 조화", "기본", "차별화"].map((x) => <option key={x}>{x}</option>)}</select></label>
      <label>공사 범위<select value={value.scope} onChange={(e) => patch({ scope: e.target.value })}>{["미정", "전체 공사", "부분 공사 · 바닥과 천장 유지"].map((x) => <option key={x}>{x}</option>)}</select></label>
      <label>기존 내부 화장실<select value={value.reuse} onChange={(e) => patch({ reuse: e.target.value })}>{["미확인", "유지 희망 · 현장 확인 필요", "변경 검토"].map((x) => <option key={x}>{x}</option>)}</select></label>
      <label>브랜드 색·적용 위치<input value={value.brand} maxLength={80} placeholder="예: 청록색 · 간판과 포인트 벽" onChange={(e) => patch({ brand: e.target.value })} /></label>
      <label>참고 이미지 시간대<select value={value.time} onChange={(e) => patch({ time: e.target.value })}><option>낮</option><option>밤</option></select></label>
    </div>
    {concept && <section aria-label="선택 콘셉트 상세"><h4>{concept.name} · 선택한 참고 방향</h4>
      <dl><dt>자재·색 배합 방향</dt><dd>{concept.material}</dd><dt>조명</dt><dd>{concept.lighting}</dd><dt>촬영 포인트</dt><dd>{concept.photo}</dd></dl>
      <p>키워드 강도와 공사 조건은 AI 참고 이미지 및 저장하는 지시문에 반영됩니다. 정확한 치수·좌석 수·색 배합 비율·견적은 도면과 업체 확인 후 결정하세요.</p>
    </section>}
    <h3>공사 전 체크리스트</h3>
    <ul><li>출입문·피난·접근 동선과 실제 내부 도면 대조</li><li>전기·급배수·배기와 업종별 설비 확인</li><li>간판 허가·영업신고와 건물주 원상복구 범위 확인</li><li>자재 실물과 조명 아래 상품 색 확인</li><li>업체 실측 견적 확보 · 기존 Posting 투자비와 중복 합산 금지</li></ul>
    <button type="button" onClick={() => onChange(defaultInteriorDesign())}>디자인 설정 초기화</button>
  </section>;
}
