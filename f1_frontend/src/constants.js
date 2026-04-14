// constants.js

export const CIRCUITS = [
  'Bahrain','Saudi Arabia','Australia','Japan','China',
  'Miami','Emilia Romagna','Monaco','Canada','Spain',
  'Austria','Great Britain','Hungary','Belgium','Netherlands',
  'Italy','Azerbaijan','Singapore','United States','Mexico',
  'Brazil','Las Vegas','Qatar','Abu Dhabi',
]

export const YEARS = Array.from(
  { length: new Date().getFullYear() - 2017 },
  (_, i) => new Date().getFullYear() - i
)

export const PLOTLY_LAYOUT = {
  paper_bgcolor: '#0a0a0f',
  plot_bgcolor:  '#0a0a0f',
  font:          { family: 'Barlow Condensed, sans-serif', color: '#888' },
  xaxis:         { gridcolor: '#1e1e2e', zeroline: false },
  yaxis:         { gridcolor: '#1e1e2e', zeroline: false },
  legend:        { orientation: 'h', y: 1.05, x: 1, xanchor: 'right',
                   bgcolor: 'rgba(0,0,0,0)', font: { color: '#ccc', size: 12 } },
  margin:        { l: 55, r: 30, t: 40, b: 40 },
  hovermode:     'x unified',
}

export const PLOTLY_CONFIG = { displayModeBar: false, responsive: true }
