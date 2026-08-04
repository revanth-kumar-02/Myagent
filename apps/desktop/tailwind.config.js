/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{svelte,ts,js}'],
  theme: {
    extend: {
      colors: {
        // Primary — Cocoa
        'primary':                    '#1f1514',
        'primary-container':          '#352928',
        'on-primary':                 '#ffffff',
        'on-primary-container':       '#a18f8e',
        'primary-fixed':              '#f3dedc',
        'primary-fixed-dim':          '#d6c2c0',
        'on-primary-fixed':           '#241918',
        'on-primary-fixed-variant':   '#514442',
        'inverse-primary':            '#d6c2c0',
        // Secondary — Dusty Rose
        'secondary':                  '#775751',
        'secondary-container':        '#fed3cc',
        'on-secondary':               '#ffffff',
        'on-secondary-container':     '#7a5954',
        'secondary-fixed':            '#ffdad4',
        'secondary-fixed-dim':        '#e7bdb6',
        'on-secondary-fixed':         '#2c1512',
        'on-secondary-fixed-variant': '#5d3f3b',
        // Tertiary — Warm Stone
        'tertiary':                   '#1b170f',
        'tertiary-container':         '#302b22',
        'on-tertiary':                '#ffffff',
        'on-tertiary-container':      '#999286',
        'tertiary-fixed':             '#ebe1d4',
        'tertiary-fixed-dim':         '#cec5b8',
        'on-tertiary-fixed':          '#1f1b13',
        'on-tertiary-fixed-variant':  '#4c463c',
        // Surfaces — Cream/Ivory
        'background':                 '#fff8f4',
        'surface':                    '#fff8f4',
        'surface-bright':             '#fff8f4',
        'surface-dim':                '#e0d9d4',
        'surface-tint':               '#6a5b5a',
        'surface-variant':            '#e8e1dc',
        'surface-container-lowest':   '#ffffff',
        'surface-container-low':      '#faf2ed',
        'surface-container':          '#f4ece7',
        'surface-container-high':     '#eee7e2',
        'surface-container-highest':  '#e8e1dc',
        'on-surface':                 '#1e1b18',
        'on-surface-variant':         '#4e4444',
        'on-background':              '#1e1b18',
        // Outline
        'outline':                    '#807473',
        'outline-variant':            '#d2c3c2',
        // Inverse
        'inverse-surface':            '#33302d',
        'inverse-on-surface':         '#f7efea',
        // Error
        'error':                      '#ba1a1a',
        'error-container':            '#ffdad6',
        'on-error':                   '#ffffff',
        'on-error-container':         '#93000a',
      },
      borderRadius: {
        'DEFAULT': '0.125rem',  // 2px  — tight
        'lg':      '0.25rem',   // 4px  — standard
        'xl':      '0.5rem',    // 8px  — card
        'full':    '0.75rem',   // 12px — pill
      },
      spacing: {
        'unit':           '4px',
        'xs':             '4px',
        'sm':             '8px',
        'md':             '16px',
        'lg':             '24px',
        'xl':             '48px',
        'xxl':            '80px',
        'gutter':         '24px',
        'margin-desktop': '40px',
      },
      fontFamily: {
        'ui-main':     ['Geist', 'system-ui', 'sans-serif'],
        'ui-medium':   ['Geist', 'system-ui', 'sans-serif'],
        'label-caps':  ['Geist', 'system-ui', 'sans-serif'],
        'body-reading':['Source Serif 4 Variable', 'Georgia', 'serif'],
        'headline-md': ['Source Serif 4 Variable', 'Georgia', 'serif'],
        'display-lg':  ['Source Serif 4 Variable', 'Georgia', 'serif'],
        'status-log':  ['"JetBrains Mono"', 'monospace'],
        'code-sm':     ['"JetBrains Mono"', 'monospace'],
      },
      fontSize: {
        'label-caps':   ['12px', { lineHeight: '16px', letterSpacing: '0.05em', fontWeight: '600' }],
        'status-log':   ['12px', { lineHeight: '18px', fontWeight: '400' }],
        'display-lg':   ['48px', { lineHeight: '1.2',  letterSpacing: '-0.02em', fontWeight: '600' }],
        'ui-medium':    ['15px', { lineHeight: '24px', fontWeight: '500' }],
        'code-sm':      ['13px', { lineHeight: '20px', fontWeight: '400' }],
        'ui-main':      ['15px', { lineHeight: '24px', fontWeight: '400' }],
        'body-reading': ['18px', { lineHeight: '1.6',  fontWeight: '400' }],
        'headline-md':  ['32px', { lineHeight: '1.3',  fontWeight: '500' }],
      },
    },
  },
  plugins: [],
};
