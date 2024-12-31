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

// Dynamically import VChart to prevent SSR processing
import { defineAsyncComponent } from 'vue'
const VChart = defineAsyncComponent(() => import('vue-echarts'))

// import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, BarChart } from 'echarts/charts'
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

  // 3a) Everything before <ECHARTS_DATA> is plain text
  textOutput.value = parts[0].trim()

  // 3b) Everything after is JSON for ECharts
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
 *    - If we find "dates" or "x", we treat it as the x-axis data.
 *    - If we find "crisis", we add vertical dashed lines (markLine).
 *    - Each chart key should contain:
 *        - "series": { sub-series data }
 *        - "type": chart type (e.g., "line", "bar")
 *        - "yAxisName": label for the y-axis
 */
const chartObjects = computed(() => {
  if (!rawChartData.value) return []

  // Potential x-axis data
  const xData = rawChartData.value.dates
           || rawChartData.value.x
           || []

  // Potential crisis lines
  const crisis = rawChartData.value.crisis || []

  // Omit known special keys from the chart loops
  const { x, dates, crisis: _, ...chartSets } = rawChartData.value

  const result = []

  for (const key of Object.keys(chartSets)) {
    // For each key, e.g., "stockPrices", "returns", etc.
    const dataObj = chartSets[key]

    // Ensure the chart key contains 'series'
    if (typeof dataObj !== 'object' || dataObj === null || !dataObj.series) continue

    // Extract 'type' and 'yAxisName', defaulting to 'line' and empty string
    const chartType = dataObj.type || 'line'
    const yAxisName = dataObj.yAxisName || ''

    // Extract 'series' object
    const seriesData = dataObj.series

    // Each sub-key in seriesData is a separate line/bar
    const subKeys = Object.keys(seriesData)

    // Build multiple series
    const series = subKeys.map(subKey => ({
      name: subKey,     // e.g., "Stock A"
      type: chartType,  // e.g., "line" or "bar"
      data: seriesData[subKey],
      // Optionally, add more styling here (e.g., color)
    }))

    // Build an ECharts option for this particular "key"
    const chartOption = {
      title: {
        text: key.replace(/([A-Z])/g, ' $1').trim()  // e.g., "stockPrices" -> "stock Prices"
      },
      tooltip: { trigger: 'axis' },
      legend: {
        data: subKeys
      },
      xAxis: {
        type: 'category',
        data: xData
      },
      yAxis: {
        type: 'value',
        name: yAxisName
      },
      series
    }

    // If there's a crisis array, add dashed lines
    if (crisis.length > 0) {
      // Add markLine to each series
      for (const s of chartOption.series) {
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
      }
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
  /* Ensure the text wraps appropriately */
  white-space: pre-wrap;
}

h3 {
  font-size: 1.2em;
  margin-bottom: 1em;
}
</style>
