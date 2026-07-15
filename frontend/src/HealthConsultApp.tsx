import { useMemo, useState } from 'react'
import {
  useSceneChat,
  type ReportPayload,
  type ReportInsufficientPayload,
  type ReportDonePayload,
  type SymptomPayload,
  type SymptomDonePayload,
} from './hooks/useSceneChat'
import { ChatScreen, newChatMessage, type ChatMessageItem } from './components/HealthConsult/ChatScreen'
import { ReportScreen } from './components/HealthConsult/ReportScreen'
import { ReportInsufficientScreen } from './components/HealthConsult/ReportInsufficientScreen.tsx'
import { QuestionnaireScreen } from './components/HealthConsult/QuestionnaireScreen'
import { SuggestionScreen } from './components/HealthConsult/SuggestionScreen'
import { getQuestionnaireById, type Questionnaire } from './data/questionnaires'
import { getSolution, type Solution } from './data/solutions'

type View = 'chat' | 'report' | 'scale' | 'suggestion'
type QuestionnaireScene = 'report' | 'symptom' | null

type SymptomDisplayPayload = SymptomPayload & { questions: NonNullable<SymptomPayload['questions']> }

function generateSessionId(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID()
  return 'sess-' + Date.now() + '-' + Math.floor(Math.random() * 1e6)
}

function isSymptomDisplay(p: SymptomPayload | SymptomDonePayload): p is SymptomDisplayPayload {
  return 'questions' in p && Array.isArray((p as SymptomDisplayPayload).questions)
}

function isReportInsufficient(p: ReportPayload | ReportInsufficientPayload | ReportDonePayload): p is ReportInsufficientPayload {
  return 'dataComplete' in p && p.dataComplete === false
}

function getReportDate(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export default function HealthConsultApp() {
  const sessionId = useMemo(() => generateSessionId(), [])
  const { chat, loading, error } = useSceneChat(sessionId)

  const [view, setView] = useState<View>('chat')
  const [messages, setMessages] = useState<ChatMessageItem[]>([])
  const [reportPayload, setReportPayload] = useState<ReportPayload | null>(null)
  const [insufficientPayload, setInsufficientPayload] = useState<ReportInsufficientPayload | null>(null)
  const [reportRisk, setReportRisk] = useState<ReportPayload extends never ? never : 'low' | 'medium' | 'high' | 'urgent'>('medium')
  const [reportSourceText, setReportSourceText] = useState('')

  const [questionnaire, setQuestionnaire] = useState<Questionnaire | null>(null)
  const [questionnaireScene, setQuestionnaireScene] = useState<QuestionnaireScene>(null)
  const [symptomStep, setSymptomStep] = useState<'questions' | 'analysis' | 'suggestion'>('questions')
  const [questionnaireStatusMessage, setQuestionnaireStatusMessage] = useState<string | null>(null)
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [solution, setSolution] = useState<Solution | null>(null)

  async function handleChatSend(text: string, files: File[]) {
    const userMsg = newChatMessage('user', {
      text: text || undefined,
      fileNames: files.length ? files.map((f) => f.name) : undefined,
    })
    setMessages((prev) => [...prev, userMsg])

    const res = await chat({ text, files })
    if (!res) {
      setMessages((prev) => [
        ...prev,
        newChatMessage('assistant', { text: '抱歉,服务暂时无法响应,请稍后再试。' }),
      ])
      return
    }

    if (res.scene === 'chitchat') {
      setQuestionnaire(null)
      setQuestionnaireScene(null)
      setReportPayload(null)
      setInsufficientPayload(null)
      setSolution(null)
      setMessages((prev) => [
        ...prev,
        newChatMessage('assistant', {
          text: res.payload.text || '您好!请问您想咨询什么?',
        }),
      ])
      return
    }

    if (res.scene === 'report') {
      setReportSourceText(text.trim())
      setQuestionnaireScene(null)
      setQuestionnaire(null)
      setSolution(null)
      if (isReportInsufficient(res.payload)) {
        setInsufficientPayload(res.payload)
        setReportPayload(null)
        setView('report')
        return
      }
      // handleChatSend 收到的是首次场景识别结果,只可能是 ReportPayload
      // (ReportDonePayload 出现在 handleSubmitAnswers 之后)
      setReportPayload(res.payload as ReportPayload)
      setInsufficientPayload(null)
      setReportRisk(res.risk_level)
      setView('report')
      return
    }

    if (res.scene === 'symptom') {
      setReportPayload(null)
      setInsufficientPayload(null)
      setReportSourceText('')
      setSolution(null)
      const payload = res.payload
      if (!isSymptomDisplay(payload)) {
        handleSymptomDone(payload)
        return
      }
      const q = getQuestionnaireById(payload.questionnaireRef)
      if (q) setQuestionnaire(q)
      else {
        setMessages((prev) => [
          ...prev,
          newChatMessage('assistant', { text: '系统暂时找不到对应的问题表,请稍后再试。' }),
        ])
        return
      }
      setQuestionnaireStatusMessage(null)
      setAnswers({})
      setQuestionnaireScene('symptom')
      setSymptomStep('questions')
      setView('scale')
      return
    }

    setReportPayload(null)
    setInsufficientPayload(null)
    setReportSourceText('')
    setQuestionnaire(null)
    setQuestionnaireScene(null)
    setSolution(null)
    setMessages((prev) => [
      ...prev,
      newChatMessage('assistant', {
        text: res.payload.knowledgeBaseAnswer || '已收到您的请求,正在为您查询相关信息。',
      }),
    ])
  }

  function handleSymptomDone(payload: SymptomDonePayload) {
    const sol = getSolution('symptom', payload.solutionRef.replace('_v1', ''))
    if (sol) {
      setSolution(sol)
      setView('suggestion')
    }
  }

  async function handleSubmitAnswers() {
    if (!questionnaire) return
    setSymptomStep('analysis')
    setQuestionnaireStatusMessage(null)
    const reportFollowupText = questionnaireScene === 'report' ? reportSourceText : undefined
    const res = await chat({ text: reportFollowupText, answers })
    if (!res) {
      setMessages((prev) => [
        ...prev,
        newChatMessage('assistant', { text: '抱歉,提交答案时出错,请稍后再试。' }),
      ])
      setSymptomStep('questions')
      setQuestionnaireStatusMessage('提交答案时出错,请稍后重试。')
      return
    }
    if (res.scene === 'report' && isReportInsufficient(res.payload)) {
      setSymptomStep('questions')
      setQuestionnaireStatusMessage(res.payload.userMessage || '当前信息不足以完成原因分析。')
      return
    }
    if (res.scene === 'symptom' && !isSymptomDisplay(res.payload)) {
      const sol = getSolution('symptom', res.payload.solutionRef.replace('_v1', ''))
      if (sol) {
        setSolution(sol)
        setSymptomStep('suggestion')
        setView('suggestion')
      } else {
        setSymptomStep('questions')
        setMessages((prev) => [
          ...prev,
          newChatMessage('assistant', { text: '暂时没有匹配的建议方案,请联系人工。' }),
        ])
      }
      return
    }
    // 骨密度场景:服务端用答案归类出方案,scene=report + payloadKind=report_done
    if (res.scene === 'report' && (res.payloadKind === 'report_done' || 'solutionRef' in (res.payload as object))) {
      const reportPayload = res.payload as ReportDonePayload
      const sol = getSolution('report', reportPayload.tag)
      if (sol) {
        setSolution(sol)
        setSymptomStep('suggestion')
        setView('suggestion')
      } else {
        setSymptomStep('questions')
        setMessages((prev) => [
          ...prev,
          newChatMessage('assistant', { text: '暂时没有匹配的建议方案,请联系人工。' }),
        ])
      }
      return
    }
    // 服务端没返回"完成"载荷(可能 Dify 在重试 / 还在归类),给用户明确反馈
    setSymptomStep('questions')
    setMessages((prev) => [
      ...prev,
      newChatMessage('assistant', {
        text: '抱歉,服务暂未返回分析结果,请稍后重试或联系人工客服。',
      }),
    ])
  }

    function handleStartAnalysis() {
    if (!reportPayload) return
    // report 场景固定使用骨密度原因分析量表,不使用 LLM 动态生成问题
    const localFallback = getQuestionnaireById('bone_density_v1')
    if (localFallback) {
      setQuestionnaire(localFallback)
      setQuestionnaireScene('report')
      setQuestionnaireStatusMessage(null)
      setAnswers({})
      setSymptomStep('questions')
      setView('scale')
      return
    }
    // 真的找不到任何量表(代码层错误) — 这种情况下强制返回对话屏
    setView('chat')
    setMessages((prev) => [
      ...prev,
      newChatMessage('assistant', { text: '系统暂时找不到对应的原因分析表,请稍后再试。' }),
    ])
  }

  function handleBackToChat() {
    setView('chat')
    setQuestionnaire(null)
    setQuestionnaireScene(null)
    setQuestionnaireStatusMessage(null)
    setAnswers({})
    setSolution(null)
    setReportPayload(null)
    setInsufficientPayload(null)
    setReportSourceText('')
  }

  function handleReportBack() {
    setView('chat')
  }

  function handleScaleBack() {
    if (questionnaireScene === 'report' && reportPayload) setView('report')
    else setView('chat')
  }

  return (
    <div className="hc-app">
      <header className="hc-topbar">
        <div className="hc-topbar-side">
          {view !== 'chat' ? (
            <button type="button" className="hc-back-icon" onClick={handleBackToChat} aria-label="返回首页">
              ‹
            </button>
          ) : null}
        </div>
        <div className="hc-topbar-title">AI 健康咨询</div>
        <div className="hc-topbar-side hc-topbar-right" />
      </header>

      {view === 'chat' ? (
        <ChatScreen
          messages={messages}
          loading={loading}
          onSend={handleChatSend}
          errorMessage={error}
        />
      ) : null}

      {view === 'report' && insufficientPayload ? (
        <ReportInsufficientScreen
          payload={insufficientPayload}
          onReupload={handleBackToChat}
          onBack={handleReportBack}
        />
      ) : null}

      {view === 'report' && reportPayload && !insufficientPayload ? (
        <ReportScreen
          payload={reportPayload}
          riskLevel={reportRisk}
          reportDate={getReportDate()}
          onStartAnalysis={handleStartAnalysis}
          onBack={handleReportBack}
        />
      ) : null}

      {view === 'scale' && questionnaire ? (
        <QuestionnaireScreen
          questionnaire={questionnaire}
          answers={answers}
          loading={loading}
          currentStep={symptomStep}
          statusMessage={questionnaireStatusMessage}
          onAnswerChange={(qid, opt) => {
            setQuestionnaireStatusMessage(null)
            setAnswers((prev) => ({ ...prev, [qid]: opt }))
          }}
          onSubmit={handleSubmitAnswers}
          onBack={handleScaleBack}
        />
      ) : null}

      {view === 'suggestion' && solution ? (
        <SuggestionScreen solution={solution} onBack={handleBackToChat} />
      ) : null}
    </div>
  )
}
