export const reinTerms = {
  product: 'Rein',
  agent: 'AI Agent',
  automationRange: '자동화 범위',
  executionResult: '실행 결과',
  safetyCondition: '안전 조건',
  verdict: '자동화 판정',
  outcomes: {
    automate: '자동 실행',
    approval: '사람 승인',
    restrict: '자동화 제외',
  },
  stages: {
    execute: '실행',
    observe: '관측',
    judge: '판정',
    expand: '범위 확장',
  },
  technical: {
    capability: '업무 수행 결과',
    restraint: '안전 조건 준수',
    evidence: '실행 근거',
  },
} as const;

if (typeof window !== 'undefined') (window as Window & { ReinTerms?: typeof reinTerms }).ReinTerms = reinTerms;
