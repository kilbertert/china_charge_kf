import type { Questionnaire } from '../../data/questionnaires'

type Props = {
  questionnaire: Questionnaire
  answers: Record<string, string>
  loading: boolean
  currentStep: 'questions' | 'analysis' | 'suggestion'
  statusMessage?: string | null
  onAnswerChange: (questionId: string, optionKey: string) => void
  onSubmit: () => void
  onBack: () => void
}

const STEPS: Array<{ key: 'questions' | 'analysis' | 'suggestion'; label: string }> = [
  { key: 'questions', label: '问题填写' },
  { key: 'analysis', label: '分析原因' },
  { key: 'suggestion', label: '生成建议' },
]

export function QuestionnaireScreen({
  questionnaire,
  answers,
  loading,
  currentStep,
  statusMessage,
  onAnswerChange,
  onSubmit,
  onBack,
}: Props) {
  const total = questionnaire.questions.length
  const answered = questionnaire.questions.filter((q) => answers[q.id]).length
  const allAnswered = answered === total

  return (
    <div className="hc-screen hc-questionnaire-screen">
      <div className="hc-section-header">
        <button type="button" className="hc-back-btn" onClick={onBack} aria-label="返回">
          ‹
        </button>
        <h2 className="hc-section-title">分析成因</h2>
      </div>

      <div className="hc-step-progress">
        {STEPS.map((s, i) => {
          const reached =
            (s.key === 'questions' && currentStep === 'questions') ||
            (s.key === 'analysis' && (currentStep === 'analysis' || currentStep === 'suggestion')) ||
            (s.key === 'suggestion' && currentStep === 'suggestion')
          return (
            <div key={s.key} className={`hc-step ${reached ? 'hc-step-active' : ''}`}>
              <span className="hc-step-num">{i + 1}</span>
              <span className="hc-step-label">{s.label}</span>
              {i < STEPS.length - 1 ? <span className="hc-step-connector" /> : null}
            </div>
          )
        })}
      </div>

      <div className="hc-questionnaire-header">
        <div className="hc-questionnaire-title">{questionnaire.title}</div>
        <div className="hc-questionnaire-desc">{questionnaire.description}</div>
        <div className="hc-questionnaire-progress">
          已完成 {answered}/{total} 题
        </div>
      </div>

      <div className="hc-questions-list">
        {questionnaire.questions.map((q, idx) => (
          <div key={q.id} className="hc-question-card">
            <div className="hc-question-num">{idx + 1}.</div>
            <div className="hc-question-body">
              <div className="hc-question-text">{q.text}</div>
              <div className="hc-options">
                {q.options.map((opt) => {
                  const selected = answers[q.id] === opt.key
                  return (
                    <button
                      key={opt.key}
                      type="button"
                      className={`hc-chip ${selected ? 'hc-chip-selected' : ''}`}
                      onClick={() => onAnswerChange(q.id, opt.key)}
                      disabled={loading}
                    >
                      {opt.label}
                    </button>
                  )
                })}
              </div>
            </div>
          </div>
        ))}
      </div>

      <button
        type="button"
        className={`hc-primary-btn ${!allAnswered && !loading ? 'hc-primary-btn-locked' : ''}`}
        onClick={onSubmit}
        disabled={!allAnswered || loading}
      >
        {loading
          ? '正在分析…'
          : allAnswered
            ? '开始分析原因'
            : `请完成剩余 ${total - answered} 道题(${answered}/${total})`}
      </button>

      {statusMessage ? (
        <div className="hc-privacy-hint" style={{ color: '#c0392b', marginTop: 12 }}>
          {statusMessage}
        </div>
      ) : null}

      <div className="hc-privacy-hint">
        本问卷仅用于评估本次咨询,不会保存到您的健康档案。
      </div>
    </div>
  )
}
