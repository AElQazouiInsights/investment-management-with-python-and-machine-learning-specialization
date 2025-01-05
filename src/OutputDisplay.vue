<template>
  <div class="output-display">
    <!-- 1) Plain Text Output -->
    <div v-if="textOutput" class="text-output">
      <pre class="whitespace-pre-wrap p-4 bg-gray-100 rounded-lg">{{ textOutput }}</pre>
    </div>

    <!-- 2) Chart Output (if there's parsed JSON) -->
    <div v-if="rawChartData" class="chart-output mt-4">
      <div class="chart-container space-y-4">
        <!-- Loop over each "chart object" we build in `chartObjects` -->
        <div
          v-for="(chartOption, index) in chartObjects"
          :key="index"
          class="mb-8"
        >
          <!-- Use ClientOnly to avoid SSR issues with ECharts -->
          <ClientOnly>
            <VChart class="chart" :option="chartOption" autoresize />
          </ClientOnly>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import { defineAsyncComponent } from 'vue'

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
  MarkLineComponent
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
  MarkLineComponent
])

// 2) The "output" prop contains both text and <ECHARTS_DATA> JSON
const props = defineProps({
  output: {
    type: String,
    default: ''
  }
})

// 3) Separate text output from chart JSON
const textOutput = ref('')
const rawChartData = ref(null)

watch(() => props.output, (newVal) => {
  if (!newVal) return

  // Split at <ECHARTS_DATA>
  const parts = newVal.split('<ECHARTS_DATA>')

  // Everything before <ECHARTS_DATA> is plain text
  textOutput.value = parts[0].trim()

  // Everything after is JSON for ECharts
  if (parts[1]) {
    try {
      rawChartData.value = JSON.parse(parts[1])
    } catch (err) {
      console.error('Failed to parse chart data:', err)
    }
  } else {
    // If there's no JSON part, reset chart data
    rawChartData.value = null
  }
}, { immediate: true })

const chartObjects = computed(() => {
  if (!rawChartData.value) return []

  // Fallback xData or crisis if older charts need it
  const xData = rawChartData.value.dates || rawChartData.value.x || []
  const crisis = rawChartData.value.crisis || []

  // Omit known special keys
  const { x, dates, crisis: _, ...chartSets } = rawChartData.value
  const result = []

  for (const key of Object.keys(chartSets)) {
    const dataObj = chartSets[key]
    if (!dataObj || typeof dataObj !== 'object' || !dataObj.series) continue

    // Read any metadata from dataObj
    const chartType  = dataObj.type || 'line'  // fallback if no type
    const yAxisName  = dataObj.yAxisName || ''
    const subKeys    = Object.keys(dataObj.series)
    const chartTitle = dataObj.title || key

    // Build sub-series
    const series = subKeys.map(subKey => {
      // The raw data for this sub-series
      const rawData = dataObj.series[subKey] || []

      // Decide chart type based on subKey
      let finalType = chartType
      if (subKey === 'Portfolios') {
        finalType = 'scatter'
      } else if (subKey === 'Frontier') {
        finalType = 'line'
      } else if (subKey === 'GMV' || subKey === 'MSR') {
        finalType = 'scatter'
      }

      // Default encode if xAxis is numeric
      let encodeObj = {}
      if (dataObj.xAxis?.type === 'value') {
        encodeObj = { x: 0, y: 1 }
      }

      // Style for GMV / MSR / MinVolForTarget
      let itemStyle = {}
      let symbol = 'circle'
      let symbolSize = 8
      let zIndex = 1 // default z

      if (subKey === 'GMV') {
        itemStyle = { color: 'black' }
        symbol = 'diamond'
        symbolSize = 12
        zIndex = 10 // place GMV on top
      } else if (subKey === 'MSR') {
        itemStyle = { color: 'red' }
        symbol = 'rectangle'
        symbolSize = 12
        zIndex = 10 // place MSR on top
      } else if (subKey === 'MinVolForTarget') {
        // Diamond marker for the min-vol portfolio at a given target
        itemStyle = { color: 'black' }
        symbol = 'diamond'
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
        z: zIndex
      }
    })

    // Determine xAxis config
    let xAxisOption
    if (dataObj.xAxis?.type === 'value') {
      xAxisOption = {
        type: 'value',
        ...dataObj.xAxis
      }
      delete xAxisOption.data
    } else {
      xAxisOption = {
        type: 'category',
        data: xData,
        ...dataObj.xAxis
      }
    }

    // Build final chart option
    const chartOption = {
      title: {
        text: chartTitle
      },
      tooltip: { trigger: 'item' },
      legend: { data: subKeys },
      xAxis: xAxisOption,
      yAxis: {
        type: dataObj.yAxis?.type || 'value',
        name: yAxisName,
        ...dataObj.yAxis
      },
      series
    }

    // If visualMap is specified, attach it + color by data
    if (dataObj.visualMap) {
      chartOption.visualMap = dataObj.visualMap
      chartOption.colorBy = 'series' // data for multiple colors
    }

    // If there's a crisis array, add dashed lines
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

    result.push(chartOption)
  }

  return result
})
</script>

<style scoped>
.chart {
  height: 400px;
}

.chart-output {
  background-color: var(--vp-code-block-bg);
  border-radius: 8px;
  padding: 16px;
}

.text-output pre {
  font-family: inherit;  /* remove default monospaced font */
  white-space: pre-wrap; /* ensure text wraps properly */
}

h3 {
  font-size: 1.2em;
  margin-bottom: 1em;
}
</style>

<!-- const chartObjects = computed(() => {
  if (!rawChartData.value) return []

  // Fallback xData or crisis if older charts need it
  const xData = rawChartData.value.dates || rawChartData.value.x || []
  const crisis = rawChartData.value.crisis || []

  // Omit known special keys
  const { x, dates, crisis: _, ...chartSets } = rawChartData.value
  const result = []

  for (const key of Object.keys(chartSets)) {
    const dataObj = chartSets[key]
    if (!dataObj || typeof dataObj !== 'object' || !dataObj.series) continue

    // Read any metadata from dataObj
    const chartType  = dataObj.type || 'line'  // fallback for older charts
    const yAxisName  = dataObj.yAxisName || ''
    const subKeys    = Object.keys(dataObj.series)
    const chartTitle = dataObj.title || key

    // Build sub-series
    const series = subKeys.map(subKey => {
      // The raw data for this sub-series
      const rawData = dataObj.series[subKey] || []

      // Decide chart type based on subKey (Portfolios => scatter, Frontier => line, etc.)
      let finalType = chartType
      if (subKey === 'Portfolios') {
        finalType = 'scatter'
      } else if (subKey === 'Frontier') {
        finalType = 'line'
      } else if (subKey === 'GMV' || subKey === 'MSR') {
        finalType = 'scatter'
      }

      // Default encode (helpful if xAxis is numeric)
      let encodeObj = {}
      if (dataObj.xAxis?.type === 'value') {
        encodeObj = { x: 0, y: 1 }
      }

      // Style for GMV (green) and MSR (red) with special markers
      let itemStyle = {}
      let symbol = 'circle'
      let symbolSize = 8

      if (subKey === 'GMV') {
        itemStyle = { color: 'black' }
        symbol = 'diamond'
        symbolSize = 12
      } else if (subKey === 'MSR') {
        itemStyle = { color: 'red' }
        symbol = 'pin'
        symbolSize = 12
      }

      return {
        name: subKey,
        type: finalType,
        data: rawData,
        encode: encodeObj,
        itemStyle,
        symbol,
        symbolSize
      }
    })

    // Determine xAxis config
    let xAxisOption
    if (dataObj.xAxis?.type === 'value') {
      xAxisOption = {
        type: 'value',
        ...dataObj.xAxis
      }
      // Remove 'data' to avoid category mode
      delete xAxisOption.data
    } else {
      xAxisOption = {
        type: 'category',
        data: xData,
        ...dataObj.xAxis
      }
    }

    // Build final chartOption
    const chartOption = {
      title: {
        text: chartTitle
      },
      tooltip: { trigger: 'item' },
      legend: { data: subKeys },
      xAxis: xAxisOption,
      yAxis: {
        type: dataObj.yAxis?.type || 'value',
        name: yAxisName,
        ...dataObj.yAxis
      },
      series
    }

    // If visualMap is specified, attach it
    if (dataObj.visualMap) {
      chartOption.visualMap = dataObj.visualMap
      // Force ECharts to color each point individually rather than per series
      chartOption.colorBy = 'data'
    }

    // If there's a crisis array, add dashed lines
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

    result.push(chartOption)
  }

  return result
}) -->