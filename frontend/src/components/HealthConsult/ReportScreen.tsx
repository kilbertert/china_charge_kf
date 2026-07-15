import type { ReportPayload, RiskLevel } from '../../hooks/useSceneChat'
import { RiskBadge } from './RiskBadge'
import { TChart } from './TChart'
import { DonutChart } from './DonutChart'
import { HealthDisclaimer } from './HealthDisclaimer'

type Props = {
  payload: ReportPayload
  riskLevel: RiskLevel
  reportDate?: string
  onStartAnalysis: () => void
  onBack: () => void
}

const RISK_TITLE: Record<RiskLevel, string> = {
  low: '当前风险程度:低',
  medium: '当前风险程度:中等',
  high: '当前风险程度:中高',
  urgent: '需要尽快就医',
}

export function ReportScreen({ payload, riskLevel, reportDate, onStartAnalysis, onBack }: Props) {
  const tValueChart =
    payload.tValueChart && payload.tValueChart.yours !== null ? payload.tValueChart : null
  const hasTChart = tValueChart !== null
  const hasDistribution = Array.isArray(payload.riskDistribution) && payload.riskDistribution.length > 0

  return (
    <div className="hc-screen hc-report-screen">
      <div className="hc-section-header">
        <button type="button" className="hc-back-btn" onClick={onBack} aria-label="返回">
          ‹
        </button>
        <h2 className="hc-section-title">分析报告</h2>
        {reportDate ? <span className="hc-meta-date">{reportDate}</span> : null}
      </div>

      <div className={`hc-risk-card hc-risk-${riskLevel}`}>
        <RiskBadge level={riskLevel} size="lg" />
        <div className="hc-risk-title">{RISK_TITLE[riskLevel]}</div>
        <div className="hc-risk-source">来源:体检报告 · {payload.reportType}</div>
      </div>

      <HealthDisclaimer
        variant="info"
        text="AI 健康初筛建议,不能替代医生诊断。建议结合专业医师评估。"
      />

      {hasTChart ? (
        <div className="hc-chart-card">
          <div className="hc-chart-title">骨密度 T 值对比</div>
          <TChart
            normal={tValueChart.normal}
            yours={tValueChart.yours}
            thresholds={tValueChart.thresholds}
          />
        </div>
      ) : null}

      {hasDistribution ? (
        <div className="hc-chart-card">
          <div className="hc-chart-title">风险分布</div>
          <DonutChart data={payload.riskDistribution} />
        </div>
      ) : null}

      <div className="hc-conclusion-card">
        <div className="hc-conclusion-label">一句话结论</div>
        <div className="hc-conclusion-text">{payload.oneLineConclusion}</div>
      </div>

      {payload.problemPriority.length > 0 ? (
        <div className="hc-priority-card">
          <div className="hc-priority-title">问题优先级</div>
          {payload.problemPriority.map((p) => (
            <div key={p.rank} className="hc-priority-item">
              <span className="hc-priority-rank">{p.rank}</span>
              <span className="hc-priority-name">{p.name}</span>
              <span className="hc-priority-level">{p.level}</span>
            </div>
          ))}
        </div>
      ) : null}

      <button type="button" className="hc-primary-btn" onClick={onStartAnalysis}>
        开始分析原因
      </button>
    </div>
  )
}
