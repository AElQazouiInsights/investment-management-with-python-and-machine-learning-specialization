<template>
  <div class="output-display">
    <!-- 1) Plain Text Output -->
    <div v-if="textOutput" class="text-output">
      <pre class="whitespace-pre-wrap p-4 bg-gray-100 rounded-lg">{{ textOutput }}</pre>
    </div>

    <!-- 2) Chart Output (if there's parsed JSON) -->
    <div v-if="rawChartData" class="chart-output mt-4">
      <div class="chart-container space-y-4">
        <!-- Loop over each "chart object" built in `chartObjects` -->
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
  VisualMapComponent // Register VisualMapComponent
])

// 2) Define the "output" prop containing both text and <ECHARTS_DATA> JSON
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

  // Assign plain text before <ECHARTS_DATA>
  textOutput.value = parts[0].trim()

  // Parse JSON after <ECHARTS_DATA>
  if (parts[1]) {
    try {
      rawChartData.value = JSON.parse(parts[1])
    } catch (err) {
      console.error('Failed to parse chart data:', err)
    }
  } else {
    // Reset chart data if no JSON part exists
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
    const chartType  = dataObj.type || 'line'  // Default chart type
    const yAxisName  = dataObj.yAxisName || ''
    const subKeys    = Object.keys(dataObj.series)
    const chartTitle = dataObj.title || key

    // Build sub-series for the chart
    const series = subKeys.map(subKey => {
      // Retrieve raw data for the sub-series
      const rawData = dataObj.series[subKey] || []

      // Determine chart type based on subKey
      let finalType = chartType
      if (subKey === 'Portfolios') {
        finalType = 'scatter'
      } else if (subKey === 'Frontier') {
        finalType = 'line'
      } else if (subKey === 'GMV' || subKey === 'MSR') {
        finalType = 'scatter'
      }

      // Configure encoding based on xAxis type
      let encodeObj = {}
      if (dataObj.xAxis?.type === 'value') {
        encodeObj = { x: 0, y: 1 }
      }

      // Define styling for specific sub-series
      let itemStyle = {}
      let symbol = 'circle'
      let symbolSize = 8
      let zIndex = 1 // Default z-index

      if (subKey === 'GMV') {
        finalType = 'scatter'     // crucial
        itemStyle = { color: 'black' }
        symbol = 'diamond'
        symbolSize = 12
        zIndex = 10 // Bring to front
      } else if (subKey === 'Frontier') {
        finalType = 'line'
      } else if (subKey === 'MSR') {
        finalType = 'scatter'     // crucial
        itemStyle = { color: 'red' }
        symbol = 'rectangle'
        symbolSize = 12
        zIndex = 10 // Bring to front
      } else if (subKey === 'MinVolForTarget') {
        finalType = 'scatter'     // crucial
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

    // Configure xAxis based on dataObj specifications
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

    // Build the final chart option
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

    // Attach visualMap if specified
    if (dataObj.visualMap) {
      chartOption.visualMap = dataObj.visualMap
      chartOption.colorBy = 'series' // Ensure color mapping is based on individual data points
    }

    // Add dashed lines for crisis periods if available
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
  font-family: inherit;  /* Remove default monospaced font */
  white-space: pre-wrap; /* Ensure text wraps properly */
}

h3 {
  font-size: 1.2em;
  margin-bottom: 1em;
}
</style>
