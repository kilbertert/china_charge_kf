import ReactECharts from 'echarts-for-react'
import type { RiskDistributionItem } from '../../hooks/useSceneChat'

type Props = {
  data: RiskDistributionItem[]
}

const COLOR_PALETTE = ['#EE6666', '#F6BD16', '#5AD8A6']

export function DonutChart({ data }: Props) {
  if (!data || data.length === 0) {
    return <div className="hc-chart-empty">暂无风险分布数据。</div>
  }
  const option = {
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c}%',
    },
    legend: {
      bottom: 0,
      left: 'center',
      icon: 'circle',
      textStyle: { fontSize: 12, color: '#333' },
    },
    series: [
      {
        type: 'pie',
        radius: ['50%', '75%'],
        center: ['50%', '45%'],
        avoidLabelOverlap: false,
        label: {
          show: true,
          formatter: '{b}\n{d}%',
          fontSize: 12,
        },
        labelLine: { show: true },
        itemStyle: {
          borderRadius: 6,
          borderColor: '#fff',
          borderWidth: 2,
        },
        data: data.map((d, i) => ({
          name: d.name,
          value: d.value,
          itemStyle: { color: COLOR_PALETTE[i % COLOR_PALETTE.length] },
        })),
      },
    ],
  }
  return <ReactECharts option={option} style={{ height: 240, width: '100%' }} />
}
