'use client'
import { useState } from 'react'
import { apiGet, apiPost } from '../../lib/api'

export default function AdminDashboardShell() {
  const [email, setEmail] = useState(`admin-${Date.now()}@example.com`)
  const [password] = useState('StrongPassword123!')
  const [token, setToken] = useState('')
  const [log, setLog] = useState<string[]>([])
  const addLog = (m: string) => setLog((l) => [m, ...l].slice(0, 12))
  async function loginOnly() { const res:any=await apiPost('/api/v1/auth/login',{identifier:email,password}); setToken(res.data.access_token); addLog('Admin logged in') }
  async function securityEvents() { const res:any=await apiGet('/api/v1/admin/security-events',token); addLog(`Security events ${res.data.count}`) }
  async function payments() { const res:any=await apiGet('/api/v1/admin/payments',token); addLog(`Payments ${res.data.length}`) }
  async function events() { const res:any=await apiGet('/api/v1/admin/events',token); addLog(`Event ledger ${res.data.length}`) }
  async function sessions() { const res:any=await apiGet('/api/v1/sessions',token); addLog(`Operational sessions ${res.data.length}`) }
  return <>
    <section className="card"><span className="badge warning">Admin / OPS shell</span><h1>Admin Dashboard</h1><p className="muted">Admin users are seeded/created outside public registration. Sensitive access is logged.</p></section>
    <section className="grid"><div className="card"><h2>Login</h2><input value={email} onChange={e=>setEmail(e.target.value)} style={{width:'100%',padding:8}}/><br/><br/><button className="primary" onClick={loginOnly}>Login existing admin</button></div><div className="card"><h2>Audit</h2><button className="primary" onClick={securityEvents} disabled={!token}>Read security events</button> <button onClick={payments} disabled={!token}>Payments</button> <button onClick={events} disabled={!token}>Event ledger</button> <button onClick={sessions} disabled={!token}>Sessions</button><p className="muted">This access will be logged.</p></div></section>
    <section className="card"><h2>Activity</h2>{log.map((l,i)=><p key={i}>{l}</p>)}</section>
  </>
}
