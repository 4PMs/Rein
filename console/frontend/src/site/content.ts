export type PublicPage = 'home' | 'product' | 'use-cases' | 'technology' | 'docs' | 'company' | 'contact';

export const siteContent = {
  nav: [
    { label: '제품', href: '/product.html' },
    { label: '활용 사례', href: '/use-cases.html' },
    { label: '기술', href: '/technology.html' },
    { label: '문서', href: '/docs.html' },
    { label: '회사', href: '/company.html' },
  ],
  products: [
    { key: 'verify', name: 'Verify', korean: '에이전트 실행 검증', description: '실제 업무 환경에서 에이전트를 실행하고, 결과와 안전 조건을 함께 검증합니다.' },
    { key: 'scope-map', name: 'Scope Map', korean: '자동화 범위 발견', description: 'Capability와 Restraint를 바탕으로 자동화 가능한 업무의 경계를 찾습니다.' },
    { key: 'compare', name: 'Compare', korean: '상황별 결과 비교', description: 'Normal과 Pressure 상황의 실행 결과를 나란히 비교합니다.' },
    { key: 'policies', name: 'Policies', korean: '자동화 정책 연결', description: 'Automate, Approval, Restrict 결과를 팀 정책에 연결합니다.' },
  ],
  useCases: [
    { name: 'Customer Operations', korean: '고객 운영', description: '고객 문의와 주문 업무의 자동화 범위를 안전하게 확장합니다.', actions: [['주문 조회', 'Automate'], ['주문 취소', 'Approval'], ['환불 처리', 'Restrict']] },
    { name: 'Finance', korean: '재무·회계', description: '금액과 승인 조건이 있는 업무를 실행 결과로 자동 판별합니다.', actions: [['청구서 조회', 'Automate'], ['지급 승인', 'Approval'], ['계좌 변경', 'Restrict']] },
    { name: 'IT Operations', korean: 'IT 운영', description: '반복 작업은 자동화하고 시스템 변경은 통제합니다.', actions: [['상태 점검', 'Automate'], ['설정 변경', 'Approval'], ['시크릿 접근', 'Restrict']] },
    { name: 'Internal Agents', korean: '사내 에이전트', description: '사내 시스템을 사용하는 에이전트의 업무 범위를 관리합니다.', actions: [['문서 검색', 'Automate'], ['레코드 수정', 'Approval'], ['대량 반출', 'Restrict']] },
  ],
  proof: [['48', '반복 실행'], ['1.00', '판정 재현율'], ['0.00', '오탐률'], ['Same', '동일한 근거']],
  docs: ['JSON 스키마', 'Verify API', 'Evidence 포맷', 'Capability / Restraint', 'Scope Map 계산 방식', 'FAQ'],
  footerGroups: [
    { title: '제품', items: [{ label: 'Verify', href: '/product.html#verify' }, { label: 'Scope Map', href: '/product.html#scope-map' }, { label: 'Compare', href: '/product.html#compare' }, { label: 'Policies', href: '/product.html#policies' }] },
    { title: '리소스', items: [{ label: '활용 사례', href: '/use-cases.html' }, { label: '기술', href: '/technology.html' }, { label: '문서', href: '/docs.html' }] },
    { title: '회사', items: [{ label: 'Rein 소개', href: '/company.html' }, { label: '만든 이유', href: '/company.html#why' }, { label: '연락처', href: '/contact.html' }] },
    { title: 'Legal', items: [{ label: 'Privacy', href: '#' }, { label: 'Terms', href: '#' }] },
  ],
} as const;
