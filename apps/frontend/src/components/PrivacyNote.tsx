/**
 * 가입할 때 무엇을 받고 언제 지우는지 — 한 단락 (2026-10-05).
 *
 * 개인정보는 받을수록 처리방침·암호화·파기 의무가 따라온다. 그래서 받는 것을 이메일 중심으로
 * 줄였고, 받은 것은 여기서 숨김없이 적는다(docs/decision-lightweight-first-2026-10-05.md §2).
 *
 * ⚠ 이 문단은 코드가 **실제로 하는 일**과 같아야 한다. 저장 항목은 models/auth.py·feedback.py
 *   (저장한 계산·검증 결과는 business_workspaces 행의 `results` — services/business_workspace, 2026-10-06)
 *   (+ 이용 기록 = services/usage.record_access), 파기는 services/auth_service.delete_account 다.
 *   그쪽을 바꾸면 여기도 같이 고친다. 법정 처리방침 전문은 이 단락이 대신하지 않는다 — 전문은 정적 페이지
 *   public/privacy.html 이고(2026-10-08), 항목이 늘면 그쪽도 같이 고친다
 *   (tests/test_privacy_policy_page.py 가 표가 늘어난 것을 잡는다).
 */
import "@/pages/Account.css";
import { PRIVACY_POLICY_PATH } from "@/lib/privacyPolicy";

export default function PrivacyNote() {
  return (
    <p className="acct-privacy acct-muted">
      가입하면 <strong>이메일</strong>(로그인용)과 직접 적은 사업 정보·오프라인 캠페인 기록·피드백, 직접 저장한 후보 자리·계산·검증 결과,
      이용 기록(어떤 분석을 불렀는지)을 보관합니다. 비밀번호는 되돌릴 수 없는 형태로만 저장하고, 구글로 시작하면 구글이 확인한 이메일 말고는
      (이름·사진) 저장하지 않습니다. 네이버·카카오로 시작하면 제공자와 고유 사용자 ID, 제공된 이메일을 저장하며,
      이름·사진·제공자의 로그인 토큰은 저장하지 않습니다. 소요시간을 조회한 출발지는 이 브라우저에만 남고(저희 서버에 저장하지 않습니다),
      조회할 때 입력한 주소는 카카오에, 출발지 좌표는 교통 제공사(카카오모빌리티·ODsay)에 보냅니다.
      인테리어 AI 참고 이미지는 별도 동의 후 생성할 때만 입력 조건·도면·사진을 OpenAI에 보냅니다.
      직거래 기능을 쓰면 직접 올린 빈 자리의 주소·조건과 소유자 확인 정보(등기부등본 고유번호·소유자 이름 — 운영자만 봅니다),
      층 배치도 사진(올릴 때 서버가 촬영 위치·기기 정보를 뗍니다), 주고받은 문의·메시지·방문 시각·조건 제안서, 매물 신고, 정액 상품 신청(입금자명)을 보관합니다. 입점 희망서를 쓰면 희망 조건(건물주에게 이름 없이 보임)·
      사업 개요와 자금 계획(내가 열어 준 건물주에게만)·객단가 등 계산 칸(나만 봄)을 보관하고, 신용 점수는 매기지 않습니다.
      탈퇴하면 이를 지우고, 입금 확인 기록만 계정과의 연결을 끊어 남깁니다.
      계정 화면에서 언제든 탈퇴할 수 있고, 탈퇴하면 바로 지웁니다.{" "}
      <a href={PRIVACY_POLICY_PATH} target="_blank" rel="noopener noreferrer">개인정보 처리방침 전문 (새 창)</a>
    </p>
  );
}
