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
  const [modReviews, setModReviews] = useState<any[]>([])
  const [modAction, setModAction] = useState('')
  const [modReason, setModReason] = useState('')
  const [modResult, setModResult] = useState('')
  const [pendingTeachers, setPendingTeachers] = useState<any[]>([])
  const [verifDetail, setVerifDetail] = useState<any | null>(null)
  const [verifNote, setVerifNote] = useState('')
  const [verifResult, setVerifResult] = useState('')
  const [refunds, setRefunds] = useState<any[]>([])
  const [refundDetail, setRefundDetail] = useState<any | null>(null)
  const [rApprove, setRApprove] = useState('')
  const [rTeacherAdj, setRTeacherAdj] = useState('')
  const [rPlatformAdj, setRPlatformAdj] = useState('')
  const [rReason, setRReason] = useState('')
  const [rReconcileResult, setRReconcileResult] = useState('SUCCEEDED')
  const [rReconcileRef, setRReconcileRef] = useState('')
  const [refundResult, setRefundResult] = useState('')
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

  async function loadModReviews() {
    const res: any = await apiGet('/api/v1/admin/reviews', token)
    setModReviews(res.data || [])
    addLog(`Reviews (operational): ${res.data.length} — access audited`)
  }
  async function moderate(reviewId: string, action: string) {
    if (!modReason.trim()) { setModResult('Enter a reason before moderating'); return }
    try {
      const res: any = await apiPost(`/api/v1/admin/reviews/${reviewId}/moderate`, { action, reason: modReason.trim() }, token, `mod-${crypto.randomUUID()}`)
      setModResult(`Moderation ${action} applied → status ${res.data.review.status} (audited)`)
      addLog(`Moderated review ${reviewId}: ${action} → ${res.data.review.status}`)
      loadModReviews()
    } catch (e: any) { setModResult(`Moderation rejected: ${e.message}`); addLog(`Moderation rejected: ${e.message}`) }
  }

  async function loadPending() {
    const res: any = await apiGet('/api/v1/admin/teachers/pending-verification', token)
    setPendingTeachers(res.data.teachers || [])
    addLog(`Pending verifications: ${(res.data.teachers || []).length} teachers — access audited`)
  }
  async function loadVerifDetail(teacherId: string) {
    const res: any = await apiGet(`/api/v1/admin/teachers/${teacherId}/verifications`, token)
    setVerifDetail(res.data)
    addLog(`Verification detail loaded for ${res.data.teacher.public_name} — access audited`)
  }
  async function reviewVerif(action: string) {
    if (!verifDetail) return
    const v = (verifDetail.verifications || []).find((x: any) => x.status === 'SUBMITTED')
    if (!v) { setVerifResult('No SUBMITTED verification in this detail view'); return }
    const body: any = action === 'verify' ? { verification_id: v.id, reviewer_note: verifNote } : { verification_id: v.id, rejection_reason: verifNote }
    try {
      const res: any = await apiPost(`/api/v1/admin/teachers/${verifDetail.teacher.id}/${action}`, body, token)
      setVerifResult(`${action === 'verify' ? 'Approved' : 'Rejected'} → profile ${res.data.profile_verification_status}`)
      addLog(`Verification ${action}: ${v.id} (${v.verification_type}) — audited`)
      loadVerifDetail(verifDetail.teacher.id)
    } catch (e: any) { setVerifResult(`Review failed: ${e.message}`); addLog(`Review failed: ${e.message}`) }
  }

  async function loadRefunds() {
    const res: any = await apiGet('/api/v1/admin/refunds', token)
    setRefunds(res.data || [])
    addLog(`Refunds (operational): ${res.data.length}`)
  }
  async function loadRefundDetail(refundId: string) {
    const res: any = await apiGet(`/api/v1/admin/refunds/${refundId}`, token)
    setRefundDetail(res.data)
    addLog(`Refund detail loaded ${refundId} — access audited`)
  }
  async function refundAction(action: string) {
    if (!refundDetail) return
    const id = refundDetail.refund_id
    const body: any = {}
    try {
      if (action === 'approve') {
        const approved = rApprove || refundDetail.requested_amount
        if (!rTeacherAdj || !rPlatformAdj) { setRefundResult('Enter teacher + platform allocation (must sum to approved amount)'); return }
        body.approved_amount = approved
        body.teacher_adjustment_amount = rTeacherAdj
        body.platform_adjustment_amount = rPlatformAdj
        if (rReason.trim()) body.reason_code = rReason.trim()
      } else if (action === 'reject' || action === 'cancel') {
        if (!rReason.trim()) { setRefundResult('Enter a reason before rejecting/cancelling'); return }
        body.reason = rReason.trim()
      } else if (action === 'reconcile') {
        if (!rReconcileRef.trim()) { setRefundResult('Enter a reconciliation reference'); return }
        body.result = rReconcileResult
        body.reconciliation_source = 'MANUAL_RECONCILIATION'
        body.reconciliation_reference = rReconcileRef.trim()
        body.reconciled_at = new Date().toISOString()
        body.reason = rReason.trim() || 'Manual reconciliation recorded.'
      } else if (action === 'mock_succeed' || action === 'mock_fail') {
        body.provider_event_id = `rfevt-${crypto.randomUUID()}`
      }
      const res: any = await apiPost(`/api/v1/admin/refunds/${id}/${action === 'mock_succeed' ? 'mock/succeed' : action === 'mock_fail' ? 'mock/fail' : action}`, body, token, `ref-${crypto.randomUUID()}`)
      setRefundResult(`${action} → refund ${res.data.refund?.status || res.data.refund_status}, payment ${res.data.payment_status || res.data.refund?.payment_status}`)
      addLog(`Refund ${action}: ${id} → ${res.data.refund?.status || res.data.refund_status}`)
      loadRefundDetail(id)
      loadRefunds()
    } catch (e: any) { setRefundResult(`${action} rejected: ${e.message}`); addLog(`Refund ${action} rejected: ${e.message}`) }
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
    <section className="card"><span className="badge warning">VS6 — Review Moderation</span><h2>Review Moderation (operational)</h2>
      <button className="primary" onClick={loadModReviews} disabled={!token}>Load reviews</button>
      <ul>{modReviews.map(r => {
        const actions = r.status === 'VISIBLE' ? ['FLAG', 'REMOVE'] : r.status === 'FLAGGED' ? ['HIDE', 'RESTORE', 'REMOVE'] : r.status === 'HIDDEN' ? ['RESTORE', 'REMOVE'] : []
        return <li key={r.id}>
          ★{r.rating} {r.teacher_public_name || ''} / {r.student_display_name || ''} — <b>{r.status}</b> (verified={r.is_verified})<br/>
          <span className="muted">"{r.comment || ''}"</span>
          {actions.length > 0 && <>
            <select value={modAction && modAction.startsWith(r.id) ? modAction.split('|')[1] : ''} onChange={(e)=>setModAction(`${r.id}|${e.target.value}`)} style={{padding:4}}>
              <option value="">action…</option>
              {actions.map(a=><option key={a} value={a}>{a}</option>)}
            </select>
            <button onClick={()=>moderate(r.id, modAction.split('|')[1])} disabled={!modAction || !modAction.startsWith(r.id + '|') || modAction.split('|')[1]===''}>Moderate</button>
          </>}
        </li>
      })}</ul>
      <input placeholder="moderation reason (required)" value={modReason} onChange={e=>setModReason(e.target.value)} style={{width:'100%',padding:8}}/>
      {modResult && <p className="muted">{modResult}</p>}
      <p className="muted">REMOVE is ADMIN-only. Moderation is audited (ADMIN_ACTION + security events). Reviews are never physically deleted; public visibility follows the VISIBLE+verified filter.</p>
    </section>
    <section className="card"><span className="badge warning">VS7 — Verification Queue</span><h2>Teacher Verification (operational)</h2>
      <button className="primary" onClick={loadPending} disabled={!token}>Load pending</button>
      <ul>{pendingTeachers.map(t => <li key={t.id}>{t.public_name} · profile {t.verification_status} — {t.pending.map((p: any) => p.verification_type).join(', ')} — <a href="#" onClick={(e) => { e.preventDefault(); loadVerifDetail(t.id) }}>review</a></li>)}</ul>
      {verifDetail && <div>
        <h3>{verifDetail.teacher.public_name} — {verifDetail.teacher.verification_status}</h3>
        <ul>{(verifDetail.verifications || []).map((v: any) => <li key={v.id}>{v.verification_type} · <b>{v.status}</b> · submitted {String(v.submitted_at).slice(0,10)}
          {(v.documents || []).map((d: any) => <span key={d.id}> [doc: {d.document_type} ({d.status})]</span>)}
          {v.metadata && Object.keys(v.metadata).length > 0 ? ` · ${JSON.stringify(v.metadata)}` : ''}
          {v.reviewer_note ? ` · note: ${v.reviewer_note}` : ''}
          {v.rejection_reason ? ` · rejected: ${v.rejection_reason}` : ''}</li>)}</ul>
        <input placeholder="reviewer note (verify) / rejection reason (reject)" value={verifNote} onChange={e=>setVerifNote(e.target.value)} style={{width:'100%',padding:8}}/>
        <br/><br/>
        <button onClick={()=>reviewVerif('verify')}>Approve</button> <button onClick={()=>reviewVerif('reject')}>Reject</button>
        {verifResult && <p className="muted">{verifResult}</p>}
      </div>}
      <p className="muted">Documents are metadata-only in DEV (no real storage). All actions are logged (ADMIN_ACTION + security events).</p>
    </section>
    <section className="card"><span className="badge warning">VS8 — Refund Operations (DEV mock)</span><h2>Refunds (operational)</h2>
      <button className="primary" onClick={loadRefunds} disabled={!token}>Load refunds</button>
      <ul>{refunds.map(r => (
        <li key={r.refund_id}>{r.status} · {r.refund_type} · {r.requested_amount}{r.approved_amount ? ` → ${r.approved_amount}` : ''} {r.currency} — <a href="#" onClick={(e) => { e.preventDefault(); loadRefundDetail(r.refund_id) }}>detail</a></li>
      ))}</ul>
      {refundDetail && <div>
        <h3>Refund {refundDetail.status} (payment {refundDetail.payment_status})</h3>
        <p className="muted">requested {refundDetail.requested_amount} {refundDetail.currency} · type {refundDetail.refund_type} · reason: {refundDetail.reason}{refundDetail.reason_code ? ` (${refundDetail.reason_code})` : ''}</p>
        {refundDetail.approved_amount && <p>
          Allocation: approved <b>{refundDetail.approved_amount}</b> = teacher <b>{refundDetail.teacher_adjustment_amount}</b> + platform <b>{refundDetail.platform_adjustment_amount}</b>
          {' '}(total equals approved amount)
        </p>}
        {refundDetail.timeline && <p className="muted">timeline: created {String(refundDetail.timeline.created_at).slice(0,16)}{refundDetail.timeline.approved_at ? ` · approved ${String(refundDetail.timeline.approved_at).slice(11,16)}` : ''}{refundDetail.timeline.provider_submitted_at ? ` · submitted ${String(refundDetail.timeline.provider_submitted_at).slice(11,16)}` : ''}{refundDetail.timeline.completed_at ? ` · completed ${String(refundDetail.timeline.completed_at).slice(11,16)}` : ''}{refundDetail.timeline.failed_at ? ` · failed ${String(refundDetail.timeline.failed_at).slice(11,16)}` : ''}</p>}
        {refundDetail.reconciliation && <p>Reconciliation: {refundDetail.reconciliation.source} / {refundDetail.reconciliation.reference} @ {String(refundDetail.reconciliation.reconciled_at).slice(0,16)}</p>}
        <p className="muted">provider events: {(refundDetail.provider_event_summary || []).map((e: any) => `${e.event_type}(${e.status})`).join(', ') || 'none'}</p>
        {refundDetail.status === 'REQUESTED' && <div>
          <input placeholder="approved_amount (default requested)" value={rApprove} onChange={e=>setRApprove(e.target.value)} style={{width:180,padding:8}}/>
          <input placeholder="teacher adjustment" value={rTeacherAdj} onChange={e=>setRTeacherAdj(e.target.value)} style={{width:140,padding:8}}/>
          <input placeholder="platform adjustment" value={rPlatformAdj} onChange={e=>setRPlatformAdj(e.target.value)} style={{width:140,padding:8}}/>
          <input placeholder="reason_code (optional)" value={rReason} onChange={e=>setRReason(e.target.value)} style={{width:180,padding:8}}/>
          <br/><br/>
          <button onClick={()=>refundAction('approve')}>Approve (allocation required)</button>
          <button onClick={()=>refundAction('reject')}>Reject</button>
          <button onClick={()=>refundAction('cancel')}>Cancel</button>
        </div>}
        {refundDetail.status === 'PROVIDER_PENDING' && <div>
          <label><input type="checkbox" defaultChecked={false}/> DEV mock provider result: </label>
          <button onClick={()=>refundAction('mock_succeed')}>Mock success</button>
          <button onClick={()=>refundAction('mock_fail')}>Mock failure</button>
          <span className="muted"> or reconcile manually: </span>
          <select value={rReconcileResult} onChange={e=>setRReconcileResult(e.target.value)} style={{padding:4}}>
            <option value="SUCCEEDED">SUCCEEDED</option>
            <option value="FAILED">FAILED</option>
          </select>
          <input placeholder="reconciliation reference (e.g. BANK-REF-123)" value={rReconcileRef} onChange={e=>setRReconcileRef(e.target.value)} style={{width:240,padding:8}}/>
          <input placeholder="reason" value={rReason} onChange={e=>setRReason(e.target.value)} style={{width:180,padding:8}}/>
          <button onClick={()=>refundAction('reconcile')}>Reconcile</button>
          <br/><br/>
          <button onClick={()=>refundAction('cancel')}>Cancel (pre-success)</button>
        </div>}
        {(refundDetail.status === 'SUCCEEDED' || refundDetail.status === 'FAILED' || refundDetail.status === 'REJECTED' || refundDetail.status === 'CANCELLED') && <p className="muted">Terminal state — no further transitions.</p>}
        {refundResult && <p className="muted">{refundResult}</p>}
      </div>}
      <p className="muted">DEV mock only: no real refund provider, no real money. Allocation is actor-supplied (no automatic formula). All actions are audited (ADMIN_ACTION + security events); REFUND_ISSUED is never emitted.</p>
    </section>
    <section className="card"><h2>Activity</h2>{log.map((l,i)=><p key={i}>{l}</p>)}</section>
  </>
}
