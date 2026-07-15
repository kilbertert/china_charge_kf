import type { ReportInsufficientPayload } from '../../hooks/useSceneChat'
import { HealthDisclaimer } from './HealthDisclaimer'

type Props = {
  payload: ReportInsufficientPayload
  onReupload: () => void
  onBack: () => void
}

const TIPS: { icon: string; title: string; content: string }[] = [
  {
    icon: '📷',
    title: '上传清晰的 DXA 报告图片',
    content: '尽量保证图像清晰,关键指标(T 值、Z 值)可辨认,不要只拍封面。',
  },
  {
    icon: '⌨️',
    title: '直接粘贴报告文字',
    content: '例如:腰椎 L1-L4 T值 -2.1,股骨颈 -1.8,全髋 -1.5,25-OH 维生素 D 18 ng/mL。',
  },
  {
    icon: '🚫',
    title: '不要只描述症状',
    content: '本模块专门解读骨密度报告。如您是关节疼、腿疼等不适,请返回对话重新描述。',
  },
]

export function ReportInsufficientScreen({ payload, onReupload, onBack }: Props) {
  return (
    <div className="hc-screen hc-report-insufficient-screen">
      <div className="hc-section-header">
        <button type="button" className="hc-back-btn" onClick={onBack} aria-label="返回">
          ‹
        </button>
        <h2 className="hc-section-title">未能完成解读</h2>
      </div>

      <div className="hc-insufficient-banner">
        <div className="hc-insufficient-icon" aria-hidden="true">
          ⚠
        </div>
        <div className="hc-insufficient-title">未识别到有效的骨密度数据</div>
        <div className="hc-insufficient-reason">
          {payload.reason === 'no_metrics_extracted'
            ? '本次输入中没有出现可识别的骨密度指标(T 值、DXA 数据等)。'
            : '本次输入的数据不足以进行风险初筛。'}
        </div>
      </div>

      <div className="hc-insufficient-message">{payload.userMessage}</div>

      <div className="hc-insufficient-tips">
        <div className="hc-insufficient-tips-title">您可以这样补全信息</div>
        {TIPS.map((tip) => (
          <div key={tip.title} className="hc-insufficient-tip">
            <span className="hc-insufficient-tip-icon" aria-hidden="true">
              {tip.icon}
            </span>
            <div className="hc-insufficient-tip-body">
              <div className="hc-insufficient-tip-title">{tip.title}</div>
              <div className="hc-insufficient-tip-content">{tip.content}</div>
            </div>
          </div>
        ))}
      </div>

      <HealthDisclaimer
        variant="info"
        text="AI 健康初筛建议,不能替代医生诊断。如症状明显或持续加重,请及时就医。"
      />

      <button type="button" className="hc-primary-btn" onClick={onReupload}>
        重新上传 / 返回对话
      </button>
    </div>
  )
}
