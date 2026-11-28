/**
 * 로그인 전 첫 화면 — 창업자용 랜딩 (2026-10-08).
 *
 * 왜 만들었나. 첫 화면이 로그인 벽이라, 인스타·광고로 온 사람이 이 서비스가 무엇인지 보기도 전에
 * 가입부터 요구받았다. 이 페이지가 그 앞에서 「무엇을 하고, 무엇을 못 하고, 가입하면 무엇을 받는지」를 말한다.
 *
 * 독자는 **창업자**다(2026-09-13 주요 고객 재정의 — 업종이 정해진 창업자 · 업종을 바꾸거나 상권을 옮기려는 사업자).
 * 2026-11-22: **건물주**가 PPPP 세 단계의 두 번째 사용자가 됐다(사용자 정의 → docs/decision-pppp-owner-founder-2026-11-22.md).
 * 투자자를 독자로 못 박은 docs/prd-landing.md(09-07)와 다르다 → docs/spec-landing-founders-2026-10-08.md.
 *
 * 규칙 (어기면 거짓 광고가 된다)
 *   1. 숫자는 lib/landingFacts.ts 한 곳에서만 가져온다(테스트가 서빙 거점 수와 대조한다). 문장에 직접 적지 않는다.
 *   2. 적지 않는 것: 공실 예측 정확도(LSTM 두 축은 확인 대기) · 업종 추천 적중률 · 고객 수·파일럿 실적 · 요금.
 *   3. 「못 하는 것」 절을 빼지 않는다. 시범 운영 단계에서 가장 믿을 만한 문장이 거기에 있다.
 *   4. 금지 표현: AI 기반 · 혁신적인 · 원스톱 · 올인원 · 차세대 · 최적의 · 완벽한 (tests/Landing.test.tsx 가 잠근다).
 *   5. PPPP 세 질문(#how) 절을 빼거나 접지 않는다 — 2026-10-21 PPPP 화면 보존 규칙(src/ppppScreens.test.tsx 가 잠근다).
 *
 * 이동은 해시다 — 앱 전체가 해시 라우팅이다(App.tsx). 「시작하기」는 질문 흐름의 첫 질문(`#/start`, 화면설계서 5판 —
 * 로그인 없이 끝까지 간다), 「로그인」은 `#login`(App 이 Home 을 낸다).
 */
import productShot from "@/design/assets/product-floor-stack.png";
import { IconKey, IconPin, IconSpark } from "@/components/TrackIcons";
import { GOALS } from "@/lib/businessProfile";
import { landingFacts } from "@/lib/landingFacts";
import { SITE_SCOPE_KEY, scopeHref } from "@/lib/siteScope";
import { PRIVACY_POLICY_PATH } from "@/lib/privacyPolicy";
import "./Landing.css";

// 이 탭의 범위(서울 기본 · 고양·파주 전용 — lib/siteScope)가 말하는 지역 이름과 거점 수. 모듈이 불릴 때 한 번 정해진다.
const FACTS = landingFacts();

type Track = "platform" | "page" | "posting";

/** 세 질문 — 전통 4P 와 1:1 (Place▶Platform · Product▶Page · Price▶Proposal). 순서를 바꾸지 말 것.
 *  2026-11-22 사용자 정의로 문구를 옮겼다 — 창업자와 건물주가 같은 세 단계를 각자의 자리에서 쓴다(docs/decision-pppp-owner-founder-2026-11-22.md).
 *  본문에 적는 것은 화면에 **있는** 것뿐이다 — 인스타그램은 수집하지 않고 검색 링크만 있어 적지 않는다(PlatformConsole). */
const STEPS: { track: Track; name: string; question: string; body: string; icon: JSX.Element }[] = [
  {
    track: "platform", name: "Platform", icon: <IconSpark />,
    question: "이 상권은 어떤 곳이지?",
    body: "상권의 성격과 온라인 언급(블로그·카페글·뉴스), 검색 트렌드를 한곳에 보여 주고, 어울리는 업종을 순위로 봅니다. 창업자는 내 업종이 맞는지, 건물주는 내 건물이 있는 상권이 어떻게 읽히는지 같은 자료로 확인합니다.",
  },
  {
    track: "page", name: "Page", icon: <IconPin />,
    question: "어느 건물 몇 층이 비었지?",
    body: "건물주가 자기 건물의 빈 층 정보와 층별 배치도 사진을 올리면, 공공데이터로 그린 개략 배치도가 건물주가 올린 실제 배치도로 바뀝니다. 창업자는 공실 히트맵과 건물·층별 목록에서 비어 있는 자리를 찾아봅니다.",
  },
  {
    track: "posting", name: "Proposal", icon: <IconKey />,
    question: "이 자리, 어떤 조건으로 건물주에게 전하지?",
    body: "고른 층의 비용과 회수 기간을 계산한 뒤, 입점 희망서(업종·면적·층·예산)를 건물주에게 전합니다. 건물주와 창업자는 문의·방문 예약·조건 제안을 주고받고, 계약은 두 사람이 직접 합니다. PlaceOS 는 중개하지 않고 수수료를 받지 않습니다.",
  },
];

const METHOD: { title: string; body: string }[] = [
  {
    title: "건물을 하나씩 셉니다",
    body: `건축물대장(국토교통부 건축HUB)과 상가 정보(소상공인시장진흥공단)를 맞춰, 상권 안의 건물을 층 단위로 셉니다. ${FACTS.region} ${FACTS.hubs}개 상권이 모두 이 방식입니다.`,
  },
  {
    title: "공식 통계와 나란히 놓습니다",
    body: "임대 시세 등 공식 통계의 출처와 측정 대상을 함께 보여 줍니다. 실제 계약 조건과 다를 수 있습니다.",
  },
  {
    title: "근거 없는 말은 하지 않습니다",
    // 2026-11-22: 「생성한 검증 계획은 … 한 번 더 검사」 문장을 뺐다 — 검증 계획(가설 설정 · 작게 확인)은 Program 에서 제외돼 화면에서 만들지 않는다.
    body: "화면의 수치에는 출처가 붙습니다. 오프라인 마케팅 실행 카드는 근거가 있는 카드만 내고 예산이나 예상 매출을 지어내지 않으며, 업종 추천은 「그 상권에서 가장 흔한 업종을 고르는」 단순한 방법과 비교합니다.",
  },
];

const LIMITS: string[] = [
  `${FACTS.region}만 제공하며, 시범 운영 중이라 화면과 수치가 바뀔 수 있습니다.`,
  "공실 예측은 검증 중입니다. 앞날을 맞힌다는 약속은 하지 않습니다.",
  "임대 시세는 실제 매물 호가와 다를 수 있습니다. 부동산 중개와 계약 대행은 하지 않습니다. 건물주와 창업자가 직접 이야기하고 계약합니다.",
];

const QUICK_STEPS = [
  { title: "업종 고르기", body: "하려는 업종을 선택해 살펴볼 상권을 찾습니다." },
  { title: "상권 고르기", body: "관심 있는 상권을 선택해 지역 정보를 확인합니다." },
  { title: "빈 층 보기", body: "건물을 선택해 층별 공실과 확인 상태를 살펴봅니다." },
];

export default function Landing() {
  return (
    <div className="lp">
      <header className="lp-bar">
        <div className="lp-wrap lp-bar-row">
          <a className="lp-logo" href="#" aria-label="PlaceOS 처음으로">
            <span className="lp-logo-mark" aria-hidden>P</span>
            <span>{SITE_SCOPE_KEY === "gwangju" ? "PlaceOS 광주" : "PlaceOS"}</span>
          </a>
          <nav className="lp-bar-actions" aria-label="이용 안내 및 계정">
            <a className="lp-textlink" href="#help">고객센터</a>
            <a className="lp-textlink" href="#login">로그인</a>
            <a className="lp-btn lp-btn-primary lp-btn-sm" href="#/start">시작하기</a>
          </nav>
        </div>
      </header>

      <main>
        <section className="lp-hero" aria-labelledby="lp-h1">
          <div className="lp-wrap lp-hero-grid">
            <div className="lp-hero-copy">
              {SITE_SCOPE_KEY !== "seoul" && (
                <p className="lp-scope-note">{FACTS.region} 전용 화면 · <a href={scopeHref("seoul")}>서울 상권 보기</a></p>
              )}
              <h1 id="lp-h1">계약하기 전에,<br />어느 건물 몇 층이 비었는지<br />먼저 봅니다</h1>
              <p className="lp-lede">
                창업자와 건물주를 잇는 부동산 앱. {FACTS.region} {FACTS.hubs}개 상권의 공실을 건물·층 단위로 살펴보고,
                고른 자리의 비용과 회수 기간을 따져 입점 희망서로 건물주에게 먼저 말을 겁니다.
              </p>
              <div className="lp-cta-row">
                <a className="lp-btn lp-btn-primary" href="#/start">시작하기</a>
                <a className="lp-btn lp-btn-ghost" href="#login">이미 계정이 있어요</a>
              </div>
              {/* 2026-11-28: 문은 하나인데 손님이 둘이었다 — 건물주는 네 번째 절에서야 만났다. 첫 화면에서 건물주 소개로 바로 간다. */}
              <p className="lp-owner-hint">건물주이신가요? <a href="#owners">빈 자리 올리는 방법 보기</a></p>
              <p className="lp-fine"><span>시범 운영 중</span><span>지금은 결제 없이 사용</span><span>로그인 없이 끝까지, 저장할 때만 가입</span></p>
            </div>
            {/* 2026-11-28: 일러스트 대신 실제 화면이다 — 빈 자리 상세의 「이 건물의 층」(불광 · 실데이터 · 로컬 백엔드 캡처).
                건물 이름·주소·지도는 잘라 건물이 특정되지 않게 했고, 월세 줄과 「호가가 아닌 추정」 안내는 그대로 남겼다.
                화면이 바뀌면 이 그림도 낡는다 — 다시 찍는 법은 scripts/capture_landing_product_shot.py 머리말. */}
            <figure className="lp-hero-art">
              <img src={productShot} width={750} height={734}
                alt="빈 자리 상세 화면의 이 건물의 층. 5층 건물에서 1층·3층·4층이 비어 있고 2층은 영업 중이며 5층은 상가가 아니거나 알 수 없다. 월세는 호가가 아닌 추정이라는 안내가 함께 나온다" />
              <figcaption className="lp-hero-cap">실제 화면입니다. 건물 정보는 가렸고, 월세는 호가가 아닌 추정입니다.</figcaption>
            </figure>
          </div>
        </section>

        <section className="lp-section lp-overview" aria-labelledby="lp-results">
          <div className="lp-wrap">
            {/* 2026-11-28 디자인 정리: 단어 네 개짜리 「살펴보고 얻는 것」 목록을 걷었다 — 바로 아래 이용 순서와 아래 세 질문이 같은 이야기를 이미 한다.
                제목은 이어지는 이용 순서에 맞췄다(라벨 「주요 이용 순서」와 목록은 Help.test 가 잠근다). */}
            <h2 id="lp-results">이렇게 이용합니다</h2>
            {/* 2026-11-19 사용자 결정(랜딩 점검 #3): 이용 순서는 접지 않고 펼쳐 둔다. 10-17 간소화가 <details> 로 접었다(「보기」 토글 → 정적 라벨). */}
            <div className="lp-quick">
              <p className="lp-quick-label" id="lp-quick-label">주요 이용 순서</p>
              <ol className="lp-quick-steps" aria-labelledby="lp-quick-label">
                {QUICK_STEPS.map((step) => <li key={step.title}>
                  <h3>{step.title}</h3><p>{step.body}</p>
                </li>)}
              </ol>
            </div>
            <p className="lp-audience">{GOALS.map((g) => g.label).join(" · ")}를 준비하는 분과, 빈 자리를 직접 올리는 건물주를 위한 서비스입니다.</p>
          </div>
        </section>

        {/* ⛔ PPPP 세 질문은 접지 않는다(2026-10-21 PPPP 화면 보존 규칙). 10-17 간소화가 이 절을 「기능 자세히 보기」
            <details> 안에 넣어 첫 화면에서 Platform·Page·Posting·Program 이 사라졌고, 10-21 에 되돌렸다. */}
        <section className="lp-section lp-section-alt" id="how" aria-labelledby="lp-how">
          <div className="lp-wrap">
            <h2 id="lp-how">세 가지 질문이 한&nbsp;줄로 이어집니다</h2>
            <p className="lp-sub">상권을 읽고, 빈 자리를 찾고, 입점 희망서로 건물주에게 전하는 순서입니다. 창업자와 건물주가 같은 세 단계를 각자의 자리에서 씁니다</p>
            <ol className="lp-steps">
              {STEPS.map((s, i) => (
                <li key={s.track} className="lp-step" data-track={s.track}>
                  <span className="lp-step-badge" aria-hidden>{s.icon}</span>
                  <div>
                    <p className="lp-step-name">{i + 1}. {s.name}</p>
                    <h3>{s.question}</h3>
                    <p>{s.body}</p>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* 직거래 연결 층(2026-11-18) — 건물주 소개를 **더한다**. 위 #how 의 PPPP 세 질문은 그대로 펼쳐 둔다(PPPP 화면 보존 규칙). */}
        <section className="lp-section" id="owners" aria-labelledby="lp-owners">
          <div className="lp-wrap">
            <h2 id="lp-owners">건물주이신가요? 빈 자리를 직접 올리세요</h2>
            {/* 2026-11-28: 다섯 줄 한 덩어리를 둘로 나눴다(문장은 그대로) — 건물주가 얻는 것 / PlaceOS 가 하지 않는 것. 주 버튼은 건물주의 첫 행동 하나. */}
            <p className="lp-sub">
              소유자 확인을 거친 매물만 창업자에게 보이고, 창업자의 문의·방문 예약·조건 제안을 직접 받습니다. 오래 비어 있는 자리 · 2층 이상 · 팝업(단기 사용)도 올릴 수 있고,
              층별 배치도 사진을 올리면 지도의 개략 배치도가 실제 배치도로 바뀝니다. 등록·게시는 무료입니다.
              창업자가 남긴 입점 희망서(업종·면적·층·예산)를 보고 내 매물로 먼저 제안할 수도 있습니다.
            </p>
            <p className="lp-sub">PlaceOS 는 부동산 중개를 하지 않으며 중개보수·성사 수수료를 받지 않습니다.</p>
            <div className="lp-cta-row">
              <a className="lp-btn lp-btn-primary" href="#/owner">빈 자리 직접 올리기</a>
              <a className="lp-btn lp-btn-ghost" href="#/listings">건물주 확인 매물 보기</a>
              <a className="lp-btn lp-btn-ghost" href="#/brief">입점 희망서 쓰기(창업자)</a>
            </div>
          </div>
        </section>

        <section className="lp-section lp-detail-section" aria-labelledby="lp-method">
          <div className="lp-wrap">
            {/* 2026-11-19 사용자 결정(랜딩 점검 #4): 기본으로 펼쳐 둔다 — 근거 문장 세 개가 닫힌 채 얇은 띠로만 보였다. 접을 수는 있다. */}
            <details className="lp-details" open>
              <summary id="lp-method">데이터 출처·산출 방법 보기</summary>
              <ul className="lp-cards lp-cards-3">
                {METHOD.map((m) => (
                  <li key={m.title} className="lp-card">
                    <h3>{m.title}</h3>
                    <p>{m.body}</p>
                  </li>
                ))}
              </ul>
            </details>
          </div>
        </section>

        <section className="lp-section lp-section-alt" aria-labelledby="lp-limits">
          <div className="lp-wrap lp-narrow">
            <h2 id="lp-limits">아직 못 하는 것</h2>
            <p className="lp-sub">시범 운영 단계라 먼저 밝혀 둡니다</p>
            <ul className="lp-limits">
              {LIMITS.map((l) => <li key={l}>{l}</li>)}
            </ul>
          </div>
        </section>

        <section className="lp-final" aria-labelledby="lp-final-h">
          <div className="lp-wrap">
            <h2 id="lp-final-h">내 업종으로 상권을 먼저 읽어 보세요</h2>
            <div className="lp-cta-row lp-cta-center">
              <a className="lp-btn lp-btn-primary" href="#/start">시작하기</a>
            </div>
            <p className="lp-fine"><span>시범 운영 중</span><span>지금은 결제 없이 사용</span></p>
          </div>
        </section>
      </main>

      <footer className="lp-foot">
        <div className="lp-wrap lp-foot-row">
          <p>PlaceOS <span className="lp-foot-status">시범 운영 중</span></p>
          <p>
            <a href={PRIVACY_POLICY_PATH} target="_blank" rel="noopener noreferrer">개인정보 처리방침</a>
            {" "}
            <a href="#help">자주 묻는 것 · 고객센터</a>
            {SITE_SCOPE_KEY !== "seoul" && <a href={scopeHref("seoul")}>서울 상권 보기</a>}
            <a href="mailto:seoghyeonbag36@gmail.com">문의</a>
          </p>
        </div>
      </footer>
    </div>
  );
}
