import { useEffect } from "react";
import { PRIVACY_POLICY_PATH } from "@/lib/privacyPolicy";
import "./Landing.css";

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

/** 랜딩의 기존 FAQ·문의 수단을 별도 페이지에서 제공한다. */
export default function Help() {
  useEffect(() => { window.scrollTo(0, 0); }, []);
  return (
    <div className="lp">
      <header className="lp-bar">
        <div className="lp-wrap lp-bar-row">
          <a className="lp-logo" href="#" aria-label="PlaceOS 처음으로">
            <span className="lp-logo-mark" aria-hidden>P</span><span>PlaceOS</span>
          </a>
          <a className="lp-textlink" href="#">처음으로</a>
        </div>
      </header>
      <main className="lp-wrap lp-help">
        <h1>고객센터</h1>
        <p className="lp-sub">궁금한 질문을 누르면 답변을 확인할 수 있습니다.</p>
        <section className="lp-help-section" aria-labelledby="help-faq">
          <h2 id="help-faq">자주 묻는 것</h2>
          <div className="lp-faq">
            {FAQ.map((f) => <details key={f.q}>
              <summary>{f.q}</summary><p>{f.a}</p>
            </details>)}
          </div>
        </section>
        <section className="lp-help-section" aria-labelledby="help-contact">
          <h2 id="help-contact">문의하기</h2>
          <p className="lp-sub">찾는 답변이 없으면 이메일로 문의해 주세요.</p>
          <div className="lp-cta-row">
            <a className="lp-btn lp-btn-primary" href="mailto:seoghyeonbag36@gmail.com">이메일로 문의하기</a>
          </div>
        </section>
      </main>
      <footer className="lp-foot">
        <div className="lp-wrap lp-foot-row">
          <p>PlaceOS <span className="lp-foot-status">시범 운영 중</span></p>
          <a href={PRIVACY_POLICY_PATH} target="_blank" rel="noopener noreferrer">개인정보 처리방침</a>
        </div>
      </footer>
    </div>
  );
}
