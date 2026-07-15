import type { RiskLevel } from '../../hooks/useSceneChat'
import type { Solution, SolutionSection } from '../../data/solutions'
import { RiskBadge } from './RiskBadge'
import { HealthDisclaimer } from './HealthDisclaimer'

type Props = {
  solution: Solution
  onBack: () => void
}

function SectionCard({
  title,
  tone,
  sections,
}: {
  title: string
  tone: 'green' | 'blue' | 'red' | 'gray'
  sections: SolutionSection[]
}) {
  const headerBg: Record<typeof tone, string> = {
    green: '#E8F8F0',
    blue: '#EAF3FF',
    red: '#FDECEC',
    gray: '#F0F2F5',
  } as Record<typeof tone, string>
  const border: Record<typeof tone, string> = {
    green: '#5AD8A6',
    blue: '#5B8FF9',
    red: '#EE6666',
    gray: '#C0C4CC',
  } as Record<typeof tone, string>
  return (
    <div className="hc-suggestion-section">
      <div
        className="hc-suggestion-section-header"
        style={{ background: headerBg[tone], borderLeft: `4px solid ${border[tone]}` }}
      >
        {title}
      </div>
      <div className="hc-suggestion-section-body">
        {sections.map((s, i) => (
          <div key={i} className="hc-suggestion-subcard">
            <span className="hc-suggestion-icon">{s.icon}</span>
            <div className="hc-suggestion-subcard-body">
              <div className="hc-suggestion-subtitle">{s.title}</div>
              <div className="hc-suggestion-content">{s.content}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

const RISK_LEVEL: RiskLevel = 'medium'

export function SuggestionScreen({ solution, onBack }: Props) {
  return (
    <div className="hc-screen hc-suggestion-screen">
      <div className="hc-section-header">
        <button type="button" className="hc-back-btn" onClick={onBack} aria-label="返回">
          ‹
        </button>
        <h2 className="hc-section-title">健康建议</h2>
      </div>

      <div className="hc-solution-summary">
        <div className="hc-solution-summary-top">
          <div className="hc-solution-title">{solution.title}</div>
          <RiskBadge level={solution.riskLevel ?? RISK_LEVEL} size="sm" />
        </div>
        <div className="hc-solution-department">建议就诊:{solution.department}</div>
        <div className="hc-solution-one-liner">{solution.oneLineConclusion}</div>
      </div>

      <HealthDisclaimer
        variant="info"
        text="AI 健康初筛建议,不能替代医生诊断。请结合专业医师评估与复查结果综合管理。"
      />

      <SectionCard
        title="① 生活方式干预"
        tone="green"
        sections={solution.lifestyle}
      />
      <SectionCard
        title="② 补充特定营养"
        tone="blue"
        sections={solution.nutrition}
      />
      <SectionCard
        title="③ 严重情况请及时就医"
        tone="red"
        sections={solution.alert}
      />
      <SectionCard
        title="④ 综合管理建议"
        tone="gray"
        sections={[
          {
            icon: '👨‍⚕️',
            title: '医生评估',
            content: '请将本建议带给主治医生,结合您的完整病史和检查结果综合判断。',
          },
          {
            icon: '📅',
            title: '复查安排',
            content: '按医嘱定期复查骨密度或相关指标,跟踪变化趋势。',
          },
        ]}
      />

      <button type="button" className="hc-secondary-btn" onClick={onBack}>
        返回对话
      </button>
    </div>
  )
}
