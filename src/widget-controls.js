// One registry drives both control filtering and generated Python calls.
export const chartHelperParameters = {
  show_historical_drawdown_echart: new Set(['start_year', 'end_year', 'maxdd', 'cash_rate']),
  show_drawdown_echart: new Set(['maxdd', 'hedge', 'n_years', 'n_scenarios', 'periods_per_year', 'sigma', 'scenario', 'seed']),
  show_floor_echart: new Set(['floor', 'm', 'n_years', 'n_scenarios', 'periods_per_year', 'sigma', 'scenario', 'seed']),
  show_glidepath_echart: new Set(['start', 'end', 'n_years', 'n_scenarios', 'periods_per_year', 'floor', 'seed']),
  show_psp_lhp_echart: new Set(['n_years', 'n_scenarios', 'periods_per_year', 'mu', 'sigma', 'rate_sigma', 'short_weight', 'psp_weight', 'floor', 'seed']),
  show_duration_matching_echart: new Set(['asset_value', 'discount_rate', 'short_maturity', 'long_maturity', 'short_frequency', 'long_frequency', 'liability_delay']),
  show_duration_echart: new Set(['principal', 'maturity', 'coupon_rate', 'coupons_per_year', 'ytm', 'shift_bps', 'quote']),
  show_coupon_bond_echart: new Set(['principal', 'maturity', 'coupon_rate', 'coupons_per_year', 'ytm', 'reinvestment_rate']),
  show_liability_hedging_echart: new Set(['n_years', 'n_scenarios', 'initial_assets', 'liability', 'a', 'b', 'sigma', 'periods_per_year', 'r0', 'seed']),
  show_cir_echart: new Set(['n_years', 'n_scenarios', 'a', 'b', 'sigma', 'periods_per_year', 'r0', 'seed']),
  show_gbm_echart: new Set(['n_years', 'n_scenarios', 'mu', 'sigma', 'periods_per_year', 'start', 'seed']),
  show_cppi_echart: new Set(['n_years', 'n_scenarios', 'mu', 'sigma', 'periods_per_year', 'start',
    'm', 'floor', 'risk_free_rate', 'ymax', 'seed']),
}

export function chartHelperName(code = '') {
  return Object.keys(chartHelperParameters).find(name => code.includes(name))
}

export function buildChartCode(source, values) {
  const name = chartHelperName(source)
  if (!name) return ''
  const entries = Object.entries(values)
    .filter(([key, value]) => chartHelperParameters[name].has(key) && value !== undefined)
    .map(([key, value]) => `${key}=${value === null ? 'None' : typeof value === 'boolean' ? (value ? 'True' : 'False') : JSON.stringify(value)}`)
  return entries.length ? `import PortfolioOptimizationKit as pok\npok.${name}(${entries.join(', ')})` : ''
}

// Presentation labels can change without changing the Python keyword argument.
export function controlParameterName(model) {
  const parameter = model.get('_echarts_parameter')
  if (typeof parameter === 'string' && parameter) return parameter
  const label = model.get('description') || model.get('_model_name')
  return label === 'Zoom Y axis' ? 'ymax' : label
}

// Dropdowns synchronize a selected index, not their Python option values.
export function controlChangeEvent(model) {
  return model.get('_model_name') === 'DropdownModel' ? 'change:index' : 'change:value'
}

export function controlValue(model) {
  if (model.get('_model_name') !== 'DropdownModel') return model.get('value')
  const index = model.get('index')
  const values = model.get('_echarts_option_values')
  return Number.isInteger(index) && Array.isArray(values) ? values[index] : undefined
}
