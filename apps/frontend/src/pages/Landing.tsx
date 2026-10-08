/**
 * 로그인 전 첫 화면 — 창업자용 랜딩 (2026-10-08).
 *
 * 왜 만들었나. 첫 화면이 로그인 벽이라, 인스타·광고로 온 사람이 이 서비스가 무엇인지 보기도 전에
 * 가입부터 요구받았다. 이 페이지가 그 앞에서 「무엇을 하고, 무엇을 못 하고, 가입하면 무엇을 받는지」를 말한다.
 *
 * 독자는 **창업자**다(2026-09-13 주요 고객 재정의 — 업종이 정해진 창업자 · 업종을 바꾸거나 상권을 옮기려는 사업자).
 * 투자자를 독자로 못 박은 docs/prd-landing.md(09-07)와 다르다 → docs/spec-landing-founders-2026-10-08.md.
 *
 * 규칙 (어기면 거짓 광고가 된다)
 *   1. 숫자는 lib/landingFacts.ts 한 곳에서만 가져온다(테스트가 서빙 거점 수와 대조한다). 문장에 직접 적지 않는다.
 *   2. 적지 않는 것: 공실 예측 정확도(LSTM 두 축은 확인 대기) · 업종 추천 적중률 · 고객 수·파일럿 실적 · 요금.
 *   3. 「못 하는 것」 절을 빼지 않는다. 시범 운영 단계에서 가장 믿을 만한 문장이 거기에 있다.
 *   4. 금지 표현: AI 기반 · 혁신적인 · 원스톱 · 올인원 · 차세대 · 최적의 · 완벽한 (tests/Landing.test.tsx 가 잠근다).
 *
 * 이동은 해시다 — 앱 전체가 해시 라우팅이다(App.tsx). CTA 는 `#signup` · `#login`, App 이 그 해시를 보고 Home(가입·로그인)을 낸다.
 */
import illustration from "@/design/assets/iso-commercial-building.svg";
import { IconKey, IconMegaphone, IconPin, IconSpark } from "@/components/TrackIcons";
import { GOALS } from "@/lib/businessProfile";
import { LANDING_HUBS } from "@/lib/landingFacts";
import { PRIVACY_POLICY_PATH } from "@/lib/privacyPolicy";
import "./Landing.css";

type Track = "platform" | "page" | "posting" | "program";

/** 네 질문 — 전통 4P 와 1:1 (Place▶Platform · Product▶Page · Price▶Posting · Promotion▶Program). 순서를 바꾸지 말 것. */
const STEPS: { track: Track; name: string; question: string; body: string; icon: JSX.Element }[] = [
  {
    track: "platform", name: "Platform", icon: <IconSpark />,
    question: "이 상권은 어떤 곳이지?",
    body: "상권의 성격을 읽고, 자리마다 어울리는 업종을 순위로 봅니다. 내 업종이 이 상권에 맞는지 먼저 가늠합니다.",
  },
  {
    track: "page", name: "Page", icon: <IconPin />,
    question: "어느 건물 몇 층이 비었지?",
    body: "공실 히트맵과 건물·층별 매물 목록, 네이버 거리뷰로 비어 있는 자리를 직접 찾아봅니다.",
  },
  {
    track: "posting", name: "Posting", icon: <IconKey />,
    question: "얼마짜리 자리가 맞지?",
    body: "고급화 · 가성비 · 기능중심, 세 가지 가격대로 비용과 회수 기간을 계산합니다. 임대료와 회수 기간이 곧 가격대 판단입니다.",
  },
  {
    track: "program", name: "Program", icon: <IconMegaphone />,
    question: "여기서 통하는지 어떻게 확인하지?",
    body: "팝업스토어 · 가오픈 · 시험 판매로 확인할 계획을 만듭니다. 모객 방법과 자리 연계, 그리고 「이 숫자가 안 나오면 접는다」는 기각 조건까지 적습니다.",
  },
];

const METHOD: { title: string; body: string }[] = [
  {
    title: "건물을 하나씩 셉니다",
    body: `건축물대장(국토교통부 건축HUB)과 상가 정보(소상공인시장진흥공단)를 맞춰, 상권 안의 건물을 층 단위로 셉니다. 서울 ${LANDING_HUBS}개 상권이 모두 이 방식입니다.`,
  },
  {
    title: "공식 통계와 나란히 놓습니다",
    body: "한국부동산원 R-ONE 공실률을 같은 화면에서 비교합니다. 재는 대상이 달라 값이 다를 수 있고, 다르면 다른 대로 보여 줍니다.",
  },
  {
    title: "근거 없는 말은 하지 않습니다",
    body: "화면의 수치에는 출처가 붙습니다. 생성한 검증 계획은 입력에 없는 금액이나 경험을 지어내지 않았는지 한 번 더 검사하고, 업종 추천은 「그 상권에서 가장 흔한 업종을 고르는」 단순한 방법과 비교합니다.",
  },
];

const LIMITS: string[] = [
  "지금은 서울만 열려 있습니다. 경기와 지방의 상권은 아직 볼 수 없습니다.",
  "공실 「예측」은 아직 검증을 마치지 못했습니다. 화면의 공실률은 예측이 아니라 센 값이고, 앞날을 맞힌다는 약속은 하지 않습니다.",
  "임대 시세는 공식 통계 기준이라 실제 매물 호가와 다를 수 있습니다.",
  "중개와 계약, 건물주 연결은 하지 않습니다. 자리를 찾고 따져 보는 데까지입니다.",
  "시범 운영 중이라 화면과 수치가 바뀔 수 있습니다.",
];

const FAQ: { q: string; a: JSX.Element | string }[] = [
  {
    q: "비용이 드나요?",
    a: "지금은 시범 운영 중이라 결제 없이 쓸 수 있습니다. 요금은 아직 정해지지 않았고, 정해지기 전에는 결제를 요구하지 않습니다.",
  },
  {
    q: "가입하면 무엇을 받나요?",
    a: <>이메일 주소 하나로 시작합니다. 직접 적은 사업 정보는 본인 계정에서만 보이고, 계정 화면에서 탈퇴하면 바로 지웁니다.
      자세한 내용은 <a href={PRIVACY_POLICY_PATH} target="_blank" rel="noopener noreferrer">개인정보 처리방침</a>에 있습니다.</>,
  },
  {
    q: "데이터는 어디서 오나요?",
    a: "건축물대장(국토교통부 건축HUB), 상가 정보(소상공인시장진흥공단), 한국부동산원 R-ONE, 서울시 상권·생활인구 같은 공공데이터입니다. 지도는 네이버 지도를 씁니다.",
  },
  {
    q: "영업 중인 가게의 마케팅도 도와주나요?",
    a: "아닙니다. Program 은 팝업스토어·가오픈·시험 판매로 아이템이 통하는지 확인하려는 분을 위한 기능입니다. 이미 영업 중인 가게의 홍보는 다루지 않습니다.",
  },
];

export default function Landing() {
  return (
    <div className="lp">
      <header className="lp-bar">
        <div className="lp-wrap lp-bar-row">
          <a className="lp-logo" href="#" aria-label="PlaceOS 처음으로">
            <span className="lp-logo-mark" aria-hidden>P</span>
            <span>PlaceOS</span>
          </a>
          <nav className="lp-bar-actions" aria-label="계정">
            <a className="lp-textlink" href="#login">로그인</a>
            <a className="lp-btn lp-btn-primary lp-btn-sm" href="#signup">시작하기</a>
          </nav>
        </div>
      </header>

      <main>
        <section className="lp-hero" aria-labelledby="lp-h1">
          <div className="lp-wrap lp-hero-grid">
            <div className="lp-hero-copy">
              <p className="lp-eyebrow">창업 · 업종 바꾸기 · 상권 옮기기</p>
              <h1 id="lp-h1">계약하기 전에,<br />어느 건물 몇 층이 비었는지<br />먼저 봅니다.</h1>
              <p className="lp-lede">
                업종은 정했는데 어느 상권, 어느 자리가 맞는지 모르겠다면. PlaceOS 는 서울 {LANDING_HUBS}개 상권의 공실을
                건물·층 단위로 보여 주고, 그 자리의 비용과 회수 기간, 그리고 장사가 통하는지 확인하는 방법까지 이어서 알려 줍니다.
              </p>
              <div className="lp-cta-row">
                <a className="lp-btn lp-btn-primary" href="#signup">시작하기</a>
                <a className="lp-btn lp-btn-ghost" href="#login">이미 계정이 있어요</a>
              </div>
              <p className="lp-fine">시범 운영 중 · 지금은 결제 없이 사용 · 이메일 하나로 가입</p>
            </div>
            <figure className="lp-hero-art">
              <img src={illustration} width={800} height={800}
                alt="4층 상가 건물 일러스트 — 1층과 4층은 입주해 있고 2~3층이 비어 있다" />
              <figcaption>비어 있는 층을 층 단위로 가려냅니다.</figcaption>
            </figure>
          </div>
        </section>

        <section className="lp-section" aria-labelledby="lp-who">
          <div className="lp-wrap">
            <h2 id="lp-who">이런 고민이라면</h2>
            <ul className="lp-cards lp-cards-3">
              {GOALS.map((g) => (
                <li key={g.key} className="lp-card">
                  <h3>{g.label}</h3>
                  <p>{g.hint}</p>
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section className="lp-section lp-section-alt" id="how" aria-labelledby="lp-how">
          <div className="lp-wrap">
            <h2 id="lp-how">네 가지 질문이 한 줄로 이어집니다</h2>
            <p className="lp-sub">상권을 하나의 플랫폼으로 읽는 데서 출발해, 자리를 찾고, 가격대를 정하고, 통하는지 확인하는 순서입니다.</p>
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

        <section className="lp-section" aria-labelledby="lp-method">
          <div className="lp-wrap">
            <h2 id="lp-method">숫자는 이렇게 만듭니다</h2>
            <ul className="lp-cards lp-cards-3">
              {METHOD.map((m) => (
                <li key={m.title} className="lp-card">
                  <h3>{m.title}</h3>
                  <p>{m.body}</p>
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section className="lp-section lp-section-alt" aria-labelledby="lp-limits">
          <div className="lp-wrap lp-narrow">
            <h2 id="lp-limits">아직 못 하는 것</h2>
            <p className="lp-sub">시범 운영 단계라 먼저 밝혀 둡니다.</p>
            <ul className="lp-limits">
              {LIMITS.map((l) => <li key={l}>{l}</li>)}
            </ul>
          </div>
        </section>

        <section className="lp-section" aria-labelledby="lp-faq">
          <div className="lp-wrap lp-narrow">
            <h2 id="lp-faq">자주 묻는 것</h2>
            <div className="lp-faq">
              {FAQ.map((f) => (
                <details key={f.q}>
                  <summary>{f.q}</summary>
                  <p>{f.a}</p>
                </details>
              ))}
            </div>
          </div>
        </section>

        <section className="lp-final" aria-labelledby="lp-final-h">
          <div className="lp-wrap">
            <h2 id="lp-final-h">내 업종으로 상권을 먼저 읽어 보세요.</h2>
            <div className="lp-cta-row lp-cta-center">
              <a className="lp-btn lp-btn-primary" href="#signup">시작하기</a>
            </div>
            <p className="lp-fine">시범 운영 중 · 지금은 결제 없이 사용</p>
          </div>
        </section>
      </main>

      <footer className="lp-foot">
        <div className="lp-wrap lp-foot-row">
          <p>PlaceOS · 시범 운영 중</p>
          <p>
            <a href={PRIVACY_POLICY_PATH} target="_blank" rel="noopener noreferrer">개인정보 처리방침</a>
            {" · "}
            <a href="mailto:seoghyeonbag36@gmail.com">문의</a>
          </p>
        </div>
      </footer>
    </div>
  );
}
