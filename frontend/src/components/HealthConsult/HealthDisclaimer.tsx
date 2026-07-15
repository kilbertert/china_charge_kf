type Props = {
  variant?: 'warn' | 'info'
  text?: string
}

export function HealthDisclaimer({
  variant = 'warn',
  text = '本服务由 AI 提供参考,不替代医生诊断。',
}: Props) {
  const bg = variant === 'warn' ? '#FFF4E5' : '#EAF3FF'
  const border = variant === 'warn' ? '#F6BD16' : '#5B8FF9'
  const icon = variant === 'warn' ? '⚠' : 'ⓘ'
  return (
    <div
      style={{
        background: bg,
        borderLeft: `3px solid ${border}`,
        padding: '10px 14px',
        fontSize: 13,
        color: '#5C4400',
        borderRadius: 8,
        margin: '8px 0',
        lineHeight: 1.5,
      }}
    >
      <span style={{ marginRight: 6 }}>{icon}</span>
      {text}
    </div>
  )
}
