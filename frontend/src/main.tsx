import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource/chivo/latin-ext-400.css'
import '@fontsource/chivo/latin-ext-600.css'
import '@fontsource/chivo/latin-ext-700.css'
import '@fontsource/chivo/latin-ext-900.css'
import '@fontsource/chivo/400.css'
import '@fontsource/chivo/600.css'
import '@fontsource/chivo/700.css'
import '@fontsource/chivo/900.css'
import '@fontsource/jetbrains-mono/latin-ext-400.css'
import '@fontsource/jetbrains-mono/latin-ext-500.css'
import '@fontsource/jetbrains-mono/latin-ext-700.css'
import '@fontsource/jetbrains-mono/400.css'
import '@fontsource/jetbrains-mono/500.css'
import '@fontsource/jetbrains-mono/700.css'
import './index.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
