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
 *    - If dataObj.visualMap exists (dimension=2), we attach it, letting "Portfolios" be scatter with color dimension.
 *    - color is optional for older charts (no break).
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

    // Read any metadata from dataObj
    const chartType = dataObj.type || 'line'      // fallback
    const yAxisName = dataObj.yAxisName || ''
    const subKeys   = Object.keys(dataObj.series)
    const chartTitle = dataObj.title || key       // fallback

    // Build sub-series
    const series = subKeys.map(subKey => {
      // data is array of [x,y,(optional colorDim)]
      let rawData = dataObj.series[subKey] || []

      // Decide type by subKey or fallback
      // e.g. "Portfolios" => scatter, "Frontier" => line
      let finalType = chartType
      if (subKey === "Portfolios") {
        finalType = "scatter"
      } else if (subKey === "Frontier") {
        finalType = "line"
      }

      // For numeric x-axis, set encode
      let encodeObj = {}
      if (dataObj.xAxis?.type === 'value') {
        encodeObj = { x: 0, y: 1 }
      }

      return {
        name: subKey,
        type: finalType,
        data: rawData,
        encode: encodeObj
      }
    })

    // Merge or default xAxis config
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

    // If visualMap is specified, attach it (for scatter color dimension=2)
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
  font-family: inherit;  /* remove default monospaced font */
  white-space: pre-wrap; /* ensure text wraps properly */
}

h3 {
  font-size: 1.2em;
  margin-bottom: 1em;
}
</style>
