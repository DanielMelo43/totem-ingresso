import React, { Component, type ErrorInfo, type ReactNode } from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './styles.css'

class SafeErrorBoundary extends Component<{children:ReactNode},{failed:boolean}> {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  componentDidCatch(error:Error, info:ErrorInfo) {
    if (import.meta.env.DEV) console.error('Erro de interface:', error, info)
  }
  render() {
    if (this.state.failed) return <main className="fatal-error"><div className="alert-icon">!</div><h1>Não foi possível continuar</h1><p>Ocorreu um problema inesperado. Nenhum detalhe técnico será exibido nesta tela.</p><button className="primary" onClick={()=>window.location.replace('/')}>Voltar ao início</button></main>
    return this.props.children
  }
}

ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><SafeErrorBoundary><App /></SafeErrorBoundary></React.StrictMode>)
