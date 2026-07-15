import type { RiskLevel } from '../../hooks/useSceneChat'

const COLOR_MAP: Record<RiskLevel, string> = {
  low: '#5AD8A6',
  medium: '#F6BD16',
  high: '#F6BD16',
  urgent: '#EE6666',
}

const LABEL_MAP: Record<RiskLevel, string> = {
  low: '低风险',
  medium: '中等风险',
  high: '中高风险',
  urgent: '紧急',
}

type Props = {
  level: RiskLevel
  size?: 'sm' | 'md' | 'lg'
  showLabel?: boolean
}

export function RiskBadge({ level, size = 'md', showLabel = true }: Props) {
  const fontSize = size === 'lg' ? '18px' : size === 'sm' ? '12px' : '14px'
  const padding = size === 'lg' ? '10px 18px' : size === 'sm' ? '3px 8px' : '6px 12px'
  return (
    <span
      style={{
        display: 'inline-block',
        background: COLOR_MAP[level],
        color: level === 'medium' || level === 'high' ? '#5C4400' : '#fff',
        fontSize,
        fontWeight: 600,
        padding,
        borderRadius: 20,
        whiteSpace: 'nowrap',
      }}
    >
      {showLabel ? LABEL_MAP[level] : level.toUpperCase()}
    </span>
  )
}
