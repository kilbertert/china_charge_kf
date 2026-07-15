import ReactECharts from 'echarts-for-react'

type Props = {
  normal: number
  yours: number | null
  thresholds: { normal: number; loss: number }
}

export function TChart({ normal, yours, thresholds }: Props) {
  if (yours === null || yours === undefined || Number.isNaN(yours)) {
    return (
      <div className="hc-chart-empty">
        暂无 T 值数据。请补充完整的骨密度报告后再试。
      </div>
    )
  }
  const option = {
    grid: { left: 50, right: 30, top: 30, bottom: 40 },
    xAxis: {
      type: 'category',
      data: ['正常值', '您的数值'],
      axisLine: { lineStyle: { color: '#999' } },
      axisLabel: { fontSize: 13, color: '#333' },
    },
    yAxis: {
      type: 'value',
      name: 'T 值',
      min: -3,
      max: 1,
      nameTextStyle: { fontSize: 12, color: '#666' },
      axisLine: { show: true, lineStyle: { color: '#ccc' } },
      splitLine: { lineStyle: { color: '#eee' } },
    },
    series: [
      {
        type: 'bar',
        data: [
          { value: normal, itemStyle: { color: '#D9D9D9' } },
          { value: yours, itemStyle: { color: '#5B8FF9' } },
        ],
        barWidth: 60,
        label: {
          show: true,
          position: 'top',
          formatter: '{c}',
          fontSize: 13,
          color: '#333',
        },
      },
    ],
    markLine: {
      symbol: 'none',
      data: [
        {
          yAxis: thresholds.normal,
          lineStyle: { color: '#5AD8A6', type: 'dashed' },
          label: { formatter: '正常 ≥ -1.0', color: '#5AD8A6', position: 'insideEndTop' },
        },
        {
          yAxis: thresholds.loss,
          lineStyle: { color: '#EE6666', type: 'dashed' },
          label: {
            formatter: '骨质疏松 ≤ -2.5',
            color: '#EE6666',
            position: 'insideEndBottom',
          },
        },
      ],
    },
  }
  return <ReactECharts option={option} style={{ height: 240, width: '100%' }} />
}
