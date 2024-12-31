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

/**
 * 4) Build a "chartOption" object for each key in the JSON (besides "dates", "x", or "crisis").
 *    - If we find "dates" or "x", we treat it as the x-axis data (category-based).
 *    - If dataObj.xAxis?.type === 'value', we skip using that category data.
 *    - If dataObj.visualMap exists, we attach it without breaking other graphs.
 *    - color is optional and won't break older charts if not specified.
 */
 const chartObjects = computed(() => {
  if (!rawChartData.value) return []

  // Fallback xData or crisis if older charts need it
  const xData = rawChartData.value.dates || rawChartData.value.x || []
  const crisis = rawChartData.value.crisis || []

  const { x, dates, crisis: _, ...chartSets } = rawChartData.value
  const result = []

  for (const key of Object.keys(chartSets)) {
    const dataObj = chartSets[key]
    if (!dataObj || typeof dataObj !== 'object' || !dataObj.series) continue

    const chartType = dataObj.type || 'line'
    const yAxisName = dataObj.yAxisName || ''
    const subKeys = Object.keys(dataObj.series)

    // Build sub-series
    const series = subKeys.map(subKey => {
      // For each sub-series, we specify encode if it's a numeric x-axis
      const oneSeries = {
        name: subKey,
        type: chartType,
        data: dataObj.series[subKey] || []
      }

      // If xAxis is numeric, explicitly encode x=0, y=1
      if (dataObj.xAxis?.type === 'value') {
        oneSeries.encode = { x: 0, y: 1 }
      }
      return oneSeries
    })

    // Merge or default xAxis config
    let xAxisOption
    if (dataObj.xAxis?.type === 'value') {
      xAxisOption = {
        type: 'value',
        // e.g. "Volatility (%)"
        ...dataObj.xAxis
      }
      // Remove 'data' property if it exists to avoid category mode
      delete xAxisOption.data
    } else {
      // Category fallback (older charts)
      xAxisOption = {
        type: 'category',
        data: xData,
        ...dataObj.xAxis
      }
    }

    // Build final chartOption
    const chartOption = {
      title: {
        text: dataObj.title || key
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
  /* Remove the default monospaced font */
  font-family: inherit;
  white-space: pre-wrap; /* ensure the text wraps properly */
}

h3 {
  font-size: 1.2em;
  margin-bottom: 1em;
}
</style>
