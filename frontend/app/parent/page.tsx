'use client'
import { useState } from 'react'
import { apiGet, apiPost } from '../../lib/api'

export default function ParentDashboardShell() {
  const [email, setEmail] = useState(`parent-${Date.now()}@example.com`)
  const [password] = useState('StrongPassword123!')
  const [token, setToken] = useState('')
  const [studentId, setStudentId] = useState('')
  const [teacherSubjectId, setTeacherSubjectId] = useState('')
  const [slotId, setSlotId] = useState('')
  const [bookingId, setBookingId] = useState('')
  const [paymentId, setPaymentId] = useState('')
  const [sessionId, setSessionId] = useState('')
  const [log, setLog] = useState<string[]>([])
  const [sessions, setSessions] = useState<any[]>([])
  const [reviewSessionId, setReviewSessionId] = useState('')
  const [rating, setRating] = useState('5')
  const [reviewComment, setReviewComment] = useState('')
  const [reviewState, setReviewState] = useState('')
  const [myReviews, setMyReviews] = useState<any[]>([])
  const [disputeCategory, setDisputeCategory] = useState('SESSION_QUALITY')
  const [disputeDesc, setDisputeDesc] = useState('')
  const [myDisputes, setMyDisputes] = useState<any[]>([])
  const [refundState, setRefundState] = useState('')
  const addLog = (m: string) => setLog((l) => [m, ...l].slice(0, 12))
  // UX v1.1 Patch 1 parent-facing labels; "completed" (refunded) only when SUCCEEDED.
  const REFUND_PARENT_LABEL: Record<string, string> = {
    REQUESTED: 'Refund requested', APPROVED: 'Refund approved', PROVIDER_PENDING: 'Refund processing',
    SUCCEEDED: 'Refund completed', FAILED: 'Refund failed', REJECTED: 'Refund rejected', CANCELLED: 'Refund cancelled',
  }
  async function registerLogin() {
    await apiPost('/api/v1/auth/register', { role: 'PARENT', full_name: 'Parent User', email, password })
    const res: any = await apiPost('/api/v1/auth/login', { identifier: email, password })
    setToken(res.data.access_token); addLog('Parent logged in')
  }
  async function createStudent() {
    const res: any = await apiPost('/api/v1/students', { display_name: 'Ahmed' }, token)
    setStudentId(res.data.id); addLog(`Student created ${res.data.id}`)
  }
  async function searchTeachers() {
    const res: any = await apiGet('/api/v1/teachers/search?mode=ONLINE', token)
    const first = res.data?.[0]
    if (first) { setTeacherSubjectId(first.teacher_subject_id); setSlotId(first.slot_id); addLog(`Found teacher ${first.public_name}`) }
    else addLog('No teacher with available ONLINE slot found')
  }
  async function holdBooking() {
    const res: any = await apiPost('/api/v1/bookings/hold', { student_id: studentId, teacher_subject_id: teacherSubjectId, availability_slot_id: slotId }, token, `hold-${crypto.randomUUID()}`)
    setBookingId(res.data.booking.id); addLog(`Booking held ${res.data.booking.id}`)
  }
  async function initiatePayment() {
    const res: any = await apiPost('/api/v1/payments/initiate', { booking_id: bookingId, provider: 'OTHER' }, token, `pay-${crypto.randomUUID()}`)
    setPaymentId(res.data.payment.id); addLog(`Payment pending ${res.data.payment.id}`)
  }
  async function mockPaymentSuccess() {
    const res: any = await apiPost(`/api/v1/payments/${paymentId}/mock/succeed`, { provider_event_id: `evt-${crypto.randomUUID()}` }, token)
    setSessionId(res.data.session_id || ''); addLog(`Payment ${res.data.payment_status}; booking ${res.data.booking_status}; session ${res.data.session_id || 'none'}`)
  }
  async function mockPaymentFailure() {
    const res: any = await apiPost(`/api/v1/payments/${paymentId}/mock/fail`, { provider_event_id: `evt-${crypto.randomUUID()}` }, token)
    addLog(`Payment ${res.data.payment_status}; booking ${res.data.booking_status}`)
  }
  async function viewRefundStatus() {
    try {
      const res: any = await apiGet(`/api/v1/payments/${paymentId}`, token)
      const refunds = res.data?.refunds || []
      if (refunds.length === 0) { setRefundState('No refund activity on this payment'); addLog('Refund status: none') }
      else {
        const labels = refunds.map((r: any) => `${REFUND_PARENT_LABEL[r.status] || r.status}${r.approved_amount ? ` (${r.approved_amount} ${r.currency})` : ''}`).join(', ')
        setRefundState(`Payment ${res.data.status} — ${labels}`)
        addLog(`Refund status: ${labels}`)
      }
    } catch (e: any) { setRefundState(`Refund status rejected: ${e.message}`); addLog(`Refund status rejected: ${e.message}`) }
  }
  async function listBookings() {
    const res: any = await apiGet('/api/v1/bookings', token)
    addLog(`Bookings: ${res.data.length}`)
  }
  async function viewSession() {
    const res: any = await apiGet(`/api/v1/sessions/${sessionId}`, token)
    addLog(`Session ${res.data.status}; attendance ${res.data.attendance_status}`)
  }
  async function viewReport() {
    const res: any = await apiGet(`/api/v1/sessions/${sessionId}/report`, token)
    addLog(`Report topics: ${(res.data.topics_covered || []).join(', ')}; progress ${res.data.progress_events.length}`)
  }

  async function loadSessions() {
    const res: any = await apiGet('/api/v1/sessions', token)
    setSessions(res.data || [])
    addLog(`Sessions loaded: ${res.data.length}`)
  }
  async function submitReview() {
    try {
      const res: any = await apiPost(`/api/v1/sessions/${reviewSessionId}/review`, { rating: Number(rating), comment: reviewComment }, token, `rev-${crypto.randomUUID()}`)
      setReviewState(`Review submitted (verified, id ${res.data.review.id})`)
      addLog(`Verified review created ${res.data.review.id}`)
      await loadMyReviews()
    } catch (e: any) { setReviewState(`Review rejected: ${e.message}`); addLog(`Review rejected: ${e.message}`) }
  }
  async function loadMyReviews() {
    const res: any = await apiGet('/api/v1/reviews', token)
    setMyReviews(res.data || [])
    addLog(`My reviews: ${res.data.length}`)
  }
  async function openDispute() {
    try {
      const res: any = await apiPost('/api/v1/disputes', { session_id: reviewSessionId, category: disputeCategory, description: disputeDesc }, token, `disp-${crypto.randomUUID()}`)
      addLog(`Dispute opened ${res.data.dispute.id} (${res.data.dispute.status}, priority ${res.data.dispute.priority})`)
      await loadMyDisputes()
    } catch (e: any) { addLog(`Dispute rejected: ${e.message}`) }
  }
  async function loadMyDisputes() {
    const res: any = await apiGet('/api/v1/disputes', token)
    setMyDisputes(res.data || [])
    addLog(`My disputes: ${res.data.length}`)
  }

  return <>
    <section className="card"><span className="badge info">Parent vertical slice</span><h1>Parent Dashboard</h1><p className="muted">DEV marketplace flow only. No real payment.</p></section>
    <section className="grid">
      <div className="card"><h2>1. Login</h2><input value={email} onChange={e=>setEmail(e.target.value)} style={{width:'100%',padding:8}}/><br/><br/><button className="primary" onClick={registerLogin}>Register/Login</button></div>
      <div className="card"><h2>2. Student</h2><button className="primary" onClick={createStudent} disabled={!token}>Create student</button><p className="muted">{studentId || 'No student yet'}</p></div>
      <div className="card"><h2>3. Search</h2><button className="primary" onClick={searchTeachers} disabled={!token}>Search teachers</button><p className="muted">slot {slotId || '-'}</p></div>
      <div className="card"><h2>4. Booking</h2><button className="primary" onClick={holdBooking} disabled={!studentId || !slotId}>Hold slot</button> <button onClick={initiatePayment} disabled={!bookingId}>Initiate payment</button> <button onClick={mockPaymentSuccess} disabled={!paymentId}>Mock success</button> <button onClick={mockPaymentFailure} disabled={!paymentId}>Mock fail</button> <button onClick={listBookings} disabled={!token}>History</button> <button onClick={viewSession} disabled={!sessionId}>Session</button> <button onClick={viewReport} disabled={!sessionId}>Report</button> <button onClick={viewRefundStatus} disabled={!paymentId}>Refund status</button><p className="muted">{refundState || 'No refund activity yet'}</p></div>
    </section>
    <section className="card"><span className="badge success">VS4 — Verified Review + Dispute</span><h2>VS4 · Review &amp; Dispute</h2>
      <p className="muted">Completed sessions are review-eligible (server checks booking/payment state). Verification is derived by the server.</p>
      <button className="primary" onClick={loadSessions} disabled={!token}>Load sessions</button>
      <select value={reviewSessionId} onChange={e=>setReviewSessionId(e.target.value)} style={{padding:8}}>
        <option value="">select session…</option>
        {sessions.map(s=><option key={s.id} value={s.id}>{s.status} — {s.scheduled_start}</option>)}
      </select>
      <select value={rating} onChange={e=>setRating(e.target.value)} style={{padding:8}}>{[5,4,3,2,1].map(n=><option key={n} value={n}>{n}</option>)}</select>
      <input placeholder="review comment" value={reviewComment} onChange={e=>setReviewComment(e.target.value)} style={{width:'100%',padding:8,marginTop:8}}/>
      <br/><br/>
      <button className="primary" onClick={submitReview} disabled={!token || !reviewSessionId}>Submit verified review</button>
      {reviewState && <p className="muted">{reviewState}</p>}
      <br/><br/>
      <span className="muted">Dispute (open issue) on selected session:</span>
      <select value={disputeCategory} onChange={e=>setDisputeCategory(e.target.value)} style={{padding:8}}>
        {['SESSION_QUALITY','TEACHER_NO_SHOW','STUDENT_NO_SHOW','PAYMENT_REFUND','SAFETY','REPORT_ISSUE','OTHER'].map(c=><option key={c} value={c}>{c}</option>)}
      </select>
      <input placeholder="dispute description" value={disputeDesc} onChange={e=>setDisputeDesc(e.target.value)} style={{width:'100%',padding:8,marginTop:8}}/>
      <br/><br/>
      <button onClick={openDispute} disabled={!token || !reviewSessionId}>Open dispute</button>
      <button onClick={loadMyReviews} disabled={!token}>My reviews</button>
      <button onClick={loadMyDisputes} disabled={!token}>My disputes</button>
      <ul>{myReviews.map(r=><li key={r.id}>{r.rating}★ {r.teacher_public_name || ''} — verified={r.is_verified} ({r.comment || 'no comment'})</li>)}</ul>
      <ul>{myDisputes.map(d=><li key={d.id}>{d.category} · {d.status} · priority {d.priority} — {d.description || ''}</li>)}</ul>
    </section>
    <section className="card"><h2>Activity</h2>{log.map((l,i)=><p key={i}>{l}</p>)}</section>
  </>
}
