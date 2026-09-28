<template>
  <div class="output-display">
    <!-- 1) Plain Text Output -->
    <div v-if="textOutput" class="text-output">
      <pre class="whitespace-pre-wrap p-4 bg-gray-100 rounded-lg">
        {{ textOutput }}
      </pre>
    </div>

    <!-- 2) Chart Output (if there's parsed JSON) -->
    <div v-if="rawChartData" class="chart-output mt-4">
      <div class="chart-container">
        <!-- Loop over each "chart object" built in `chartObjects` -->
        <section v-for="chart in chartObjects" :key="chart.key" class="chart-panel">
          <div class="chart-title" role="heading" aria-level="4">{{ chart.title }}</div>
          <div v-if="chart.axisCaption" class="chart-axis-caption">{{ chart.axisCaption }}</div>
          <!-- Use ClientOnly to avoid SSR issues with ECharts -->
          <ClientOnly>
            <VChart class="chart" :option="chart.option" :aria-label="`${chart.title}: ${chart.axisCaption}`" role="img" autoresize />
          </ClientOnly>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import { defineAsyncComponent } from 'vue'
import { formatChartTick, formatChartValue } from './chart-format.js'

// Dynamically import VChart to prevent SSR processing
const VChart = defineAsyncComponent(() => import('vue-echarts'))

import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, BarChart, ScatterChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  MarkLineComponent,
  VisualMapComponent
} from 'echarts/components'

// 1) Register ECharts components
use([
  CanvasRenderer,
  LineChart,
  BarChart,
  ScatterChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  MarkLineComponent,
  VisualMapComponent
])

// 2) Define the "output" prop containing both text and <ECHARTS_DATA> JSON
const props = defineProps({
  output: {
    type: String,
    default: ''
  }
})

const textOutput = ref('')
const rawChartData = ref(null)

watch(() => props.output, (newVal) => {
  rawChartData.value = null
  if (!newVal) {
    textOutput.value = ''
    return
  }

  // Split at <ECHARTS_DATA>
  const parts = newVal.split('<ECHARTS_DATA>')
  textOutput.value = parts[0].trim()

  if (parts[1]) {
    try {
      rawChartData.value = JSON.parse(parts[1])
    } catch (err) {
      console.error('Failed to parse chart data:', err)
    }
  } else {
    rawChartData.value = null
  }
}, { immediate: true })

// 4) Compute chart options based on parsed JSON data
const chartObjects = computed(() => {
  if (!rawChartData.value) return []

  // Extract xData and crisis information if available
  const xData = rawChartData.value.dates || rawChartData.value.x || []
  const crisis = rawChartData.value.crisis || []

  // Exclude special keys from chartSets
  const { x, dates, crisis: _, ...chartSets } = rawChartData.value
  const result = []

  for (const key of Object.keys(chartSets)) {
    const dataObj = chartSets[key]
    if (!dataObj || typeof dataObj !== 'object' || !dataObj.series) continue

    // Extract metadata from dataObj
    const chartType  = ['line', 'bar', 'scatter'].includes(dataObj.type) ? dataObj.type : 'line'
    const yAxisName  = dataObj.yAxisName || ''
    const subKeys    = Object.keys(dataObj.series)
    const chartTitle = dataObj.title || key.replace(/([a-z])([A-Z])/g, '$1 $2')

    // Build sub-series for the chart
    const series = subKeys.map(subKey => {
      const rawData = dataObj.series[subKey] || []
      let finalType = chartType
      if (subKey === 'Portfolios') {
        finalType = 'scatter'
      } else if (subKey === 'Frontier') {
        finalType = 'line'
      } else if (subKey === 'GMV' || subKey === 'MSR') {
        finalType = 'scatter'
      }
      let encodeObj = {}
      if (dataObj.xAxis?.type === 'value') {
        encodeObj = { x: 0, y: 1 }
      }
      let itemStyle = {}
      let symbol = 'circle'
      let symbolSize = 8
      let zIndex = 1

      if (subKey === 'GMV') {
        finalType = 'scatter'
        itemStyle = { color: 'black' }
        symbol = 'diamond'
        symbolSize = 12
        zIndex = 10
      } else if (subKey === 'Frontier') {
        finalType = 'line'
      } else if (subKey === 'MSR') {
        finalType = 'scatter'
        itemStyle = { color: 'red' }
        symbol = 'rect'
        symbolSize = 12
        zIndex = 10
      } else if (subKey === 'MinVolForTarget') {
        finalType = 'scatter'
        itemStyle = { color: 'black' }
        symbol = 'diamond'
        symbolSize = 12
        zIndex = 10
      } else if (subKey === 'MaxSharpePort') {
        finalType = 'scatter'
        itemStyle = { color: 'red' }
        symbol = 'diamond'
        symbolSize = 12
        zIndex = 10
      } else if (subKey === 'CML') {
        finalType = 'line'
      } else if (subKey === 'EWP') {
        finalType = 'scatter'
        itemStyle = { color: 'goldenrod' }
        symbol = 'rect'
        symbolSize = 12
        zIndex = 10
      }
      return {
        name: subKey,
        type: finalType,
        data: rawData,
        encode: encodeObj,
        itemStyle,
        symbol,
        symbolSize,
        z: zIndex,
        showSymbol: finalType !== 'line',
        lineStyle: finalType === 'line' && (/floor/i.test(subKey) || subKey === 'Target')
          ? { type: 'dashed', width: 2 } : { width: 2 },
      }
    })

    // Configure xAxis based on dataObj specifications
    let xAxisOption
    if (dataObj.xAxis?.type === 'value') {
      xAxisOption = { type: 'value', ...dataObj.xAxis }
      delete xAxisOption.data
    } else {
      xAxisOption = { type: 'category', data: xData, ...dataObj.xAxis }
    }
    if (!xAxisOption.name && xAxisOption.type === 'category' && /^\d{4}-\d{2}$/.test(String(xData[0]))) {
      xAxisOption.name = 'Month'
    }
    xAxisOption = {
      nameLocation: 'middle', nameGap: 32,
      ...xAxisOption,
      axisLine: { onZero: false, ...xAxisOption.axisLine },
      axisLabel: {
        hideOverlap: true, showMinLabel: true, showMaxLabel: true, fontSize: 12,
        ...(xAxisOption.type === 'value' ? { formatter: formatChartTick } : {}),
        ...xAxisOption.axisLabel,
      },
    }

    // NEW: Support dual yAxis. If dataObj.yAxis exists and is not an array, wrap it in an array.
    let yAxisOption = []
    if (dataObj.yAxis) {
      yAxisOption = Array.isArray(dataObj.yAxis) ? dataObj.yAxis : [dataObj.yAxis]
    } else {
      yAxisOption = [{ type: 'value', name: yAxisName }]
    }
    // Put units above the canvas so long names remain readable on narrow screens.
    const axisCaption = yAxisOption.map(axis =>
      `${axis.name || yAxisName}${axis.type === 'log' ? ' · logarithmic scale' : ''}`
    ).filter(Boolean).join(' / ')
    yAxisOption = yAxisOption.map(axis => ({
      ...axis,
      name: '',
      axisLabel: { formatter: formatChartTick, hideOverlap: true, ...axis.axisLabel },
    }))
    const scatter = series.some(item => item.type === 'scatter')

    // Build the final chart option.
    const chartOption = {
      tooltip: {
        trigger: scatter ? 'item' : 'axis', confine: true,
        ...(scatter || yAxisOption.length !== 1 ? {} : { valueFormatter: value => formatChartValue(value, axisCaption) }),
        ...dataObj.tooltip,
      },
      legend: {
        type: 'scroll', orient: 'horizontal', left: 4, right: 4, bottom: 0,
        itemWidth: 18, itemGap: 12, textStyle: { fontSize: 12 },
        data: subKeys, ...(dataObj.legend || {}),
      },
      grid: { left: 12, right: 32, top: 16, bottom: dataObj.visualMap ? 112 : 72, containLabel: true, ...dataObj.grid },
      xAxis: xAxisOption,
      yAxis: yAxisOption,
      series: series
    }

    if (dataObj.visualMap) {
      chartOption.visualMap = {
        orient: 'horizontal', left: 'center', bottom: 34,
        itemWidth: 110, itemHeight: 10, ...dataObj.visualMap,
      }
      chartOption.colorBy = 'series'
    }

    if (crisis.length > 0) {
      chartOption.series.forEach(s => {
        s.markLine = {
          data: crisis.map(c => ({
            xAxis: c.date,
            label: {
              formatter: c.name,
              position: 'insideEndTop',
              rotate: 90,
              color: '#172E5C'
            },
            lineStyle: {
              color: '#BC1142',
              type: 'dashed'
            }
          }))
        }
      })
    }

    result.push({ key, title: chartTitle, axisCaption, option: chartOption })
  }

  return result
})
</script>

<style scoped>
.chart {
  width: 100%;
  min-width: 0;
  height: clamp(320px, 45vw, 400px);
}
.chart-panel {
  min-width: 0;
  margin: 0;
}
.chart-container {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 480px), 1fr));
  gap: 24px;
}
.chart-title {
  font-size: 16px;
  font-weight: 600;
  line-height: 1.5;
  overflow-wrap: anywhere;
}
.chart-axis-caption {
  margin: 4px 0 8px;
  color: var(--vp-c-text-2);
  font-size: 13px;
  line-height: 1.5;
  overflow-wrap: anywhere;
}
.chart-output {
  background-color: var(--vp-code-block-bg);
  border-radius: 8px;
  padding: 16px;
  min-width: 0;
}
@media (max-width: 640px) {
  .chart-output {
    padding: 12px 8px;
  }
}
.text-output pre {
  font-family: inherit;
  white-space: pre-wrap;
}
h3 {
  font-size: 1.2em;
  margin-bottom: 1em;
}
</style>
