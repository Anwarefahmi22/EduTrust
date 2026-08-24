'use client'
import { useState } from 'react'
import { apiGet, apiPost } from '../../lib/api'

export default function AdminDashboardShell() {
  const [email, setEmail] = useState(`admin-${Date.now()}@example.com`)
  const [password] = useState('StrongPassword123!')
  const [token, setToken] = useState('')
  const [log, setLog] = useState<string[]>([])
  const [reviews, setReviews] = useState<any[]>([])
  const [disputes, setDisputes] = useState<any[]>([])
  const [payouts, setPayouts] = useState<any[]>([])
  const [payoutTeacherId, setPayoutTeacherId] = useState('')
  const [payoutSessionIds, setPayoutSessionIds] = useState('')
  const [forceFail, setForceFail] = useState(false)
  const [payoutResult, setPayoutResult] = useState('')
  const addLog = (m: string) => setLog((l) => [m, ...l].slice(0, 12))
  async function loginOnly() { const res:any=await apiPost('/api/v1/auth/login',{identifier:email,password}); setToken(res.data.access_token); addLog('Admin logged in') }
  async function securityEvents() { const res:any=await apiGet('/api/v1/admin/security-events',token); addLog(`Security events ${res.data.count}`) }
  async function payments() { const res:any=await apiGet('/api/v1/admin/payments',token); addLog(`Payments ${res.data.length}`) }
  async function events() { const res:any=await apiGet('/api/v1/admin/events',token); addLog(`Event ledger ${res.data.length}`) }
  async function sessions() { const res:any=await apiGet('/api/v1/sessions',token); addLog(`Operational sessions ${res.data.length}`) }
  async function operationalReviews() {
    const res: any = await apiGet('/api/v1/reviews', token)
    setReviews(res.data || [])
    addLog(`Operational reviews ${res.data.length}`)
  }
  async function operationalDisputes() {
    const res: any = await apiGet('/api/v1/disputes', token)
    setDisputes(res.data || [])
    addLog(`Operational disputes ${res.data.length}`)
  }

  async function loadPayouts() {
    const res: any = await apiGet('/api/v1/admin/payouts', token)
    setPayouts(res.data || [])
    addLog(`Payouts (operational): ${res.data.length} — access audited`)
  }
  async function processPayout() {
    const ids = payoutSessionIds.split(',').map(s=>s.trim()).filter(Boolean)
    if (!payoutTeacherId || ids.length === 0) { addLog('Enter teacher_id and session_ids (comma-separated)'); return }
    try {
      const res: any = await apiPost('/api/v1/admin/payouts/process', { teacher_id: payoutTeacherId, session_ids: ids, force_mock_failure: forceFail }, token, `payout-${crypto.randomUUID()}`)
      setPayoutResult(`Payout ${res.data.payout.id} → ${res.data.result} (status ${res.data.payout.status}, ledger ${res.data.ledger.status})`)
      addLog(`Payout processed (mock): ${res.data.result}, total ${res.data.payout.amount} ${res.data.payout.currency}`)
      loadPayouts()
    } catch (e: any) { setPayoutResult(`Payout rejected: ${e.message}`); addLog(`Payout rejected: ${e.message}`) }
  }

  return <>
    <section className="card"><span className="badge warning">Admin / OPS shell</span><h1>Admin Dashboard</h1><p className="muted">Admin users are seeded/created outside public registration. Sensitive access is logged.</p></section>
    <section className="grid"><div className="card"><h2>Login</h2><input value={email} onChange={e=>setEmail(e.target.value)} style={{width:'100%',padding:8}}/><br/><br/><button className="primary" onClick={loginOnly}>Login existing admin</button></div><div className="card"><h2>Audit</h2><button className="primary" onClick={securityEvents} disabled={!token}>Read security events</button> <button onClick={payments} disabled={!token}>Payments</button> <button onClick={events} disabled={!token}>Event ledger</button> <button onClick={sessions} disabled={!token}>Sessions</button><p className="muted">This access will be logged.</p></div></section>
    <section className="card"><span className="badge warning">VS4 — Operational review &amp; dispute</span><h2>VS4 · Operational Views</h2>
      <button className="primary" onClick={operationalReviews} disabled={!token}>Review list</button>
      <button onClick={operationalDisputes} disabled={!token}>Dispute list</button>
      <ul>{reviews.map(r=><li key={r.id}>★{r.rating} {r.teacher_public_name || ''} / {r.student_display_name || ''} — {r.status} verified={r.is_verified}</li>)}</ul>
      <ul>{disputes.map(d=><li key={d.id}>{d.category} · {d.status} · p{d.priority} — {d.student_display_name || ''}</li>)}</ul>
      <p className="muted">These reads are audited (ADMIN_ACTION + security events).</p>
    </section>
    <section className="card"><span className="badge warning">VS5 — Payouts (DEV mock)</span><h2>Payouts (operational)</h2>
      <button className="primary" onClick={loadPayouts} disabled={!token}>Load payouts</button>
      <ul>{payouts.map(p=><li key={p.id}>{p.teacher_public_name} · {p.status} · {p.amount} {p.currency} · items {p.item_count} · ref {p.provider_reference || '—'}</li>)}</ul>
      <h3>Process payout (mock/manual-ops)</h3>
      <input placeholder="teacher_id" value={payoutTeacherId} onChange={e=>setPayoutTeacherId(e.target.value)} style={{width:'100%',padding:8}}/>
      <input placeholder="session_ids (comma-separated)" value={payoutSessionIds} onChange={e=>setPayoutSessionIds(e.target.value)} style={{width:'100%',padding:8,marginTop:8}}/>
      <label style={{marginTop:8}}><input type="checkbox" checked={forceFail} onChange={e=>setForceFail(e.target.checked)}/> force mock failure</label>
      <br/><br/>
      <button onClick={processPayout} disabled={!token}>Process payout (mock)</button>
      {payoutResult && <p className="muted">{payoutResult}</p>}
      <p className="muted">No real payout provider, no real money. Idempotency-Key sent automatically; reads are audited.</p>
    </section>
    <section className="card"><h2>Activity</h2>{log.map((l,i)=><p key={i}>{l}</p>)}</section>
  </>
}
