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
  const addLog = (m: string) => setLog((l) => [m, ...l].slice(0, 12))
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

  return <>
    <section className="card"><span className="badge info">Parent vertical slice</span><h1>Parent Dashboard</h1><p className="muted">DEV marketplace flow only. No real payment.</p></section>
    <section className="grid">
      <div className="card"><h2>1. Login</h2><input value={email} onChange={e=>setEmail(e.target.value)} style={{width:'100%',padding:8}}/><br/><br/><button className="primary" onClick={registerLogin}>Register/Login</button></div>
      <div className="card"><h2>2. Student</h2><button className="primary" onClick={createStudent} disabled={!token}>Create student</button><p className="muted">{studentId || 'No student yet'}</p></div>
      <div className="card"><h2>3. Search</h2><button className="primary" onClick={searchTeachers} disabled={!token}>Search teachers</button><p className="muted">slot {slotId || '-'}</p></div>
      <div className="card"><h2>4. Booking</h2><button className="primary" onClick={holdBooking} disabled={!studentId || !slotId}>Hold slot</button> <button onClick={initiatePayment} disabled={!bookingId}>Initiate payment</button> <button onClick={mockPaymentSuccess} disabled={!paymentId}>Mock success</button> <button onClick={mockPaymentFailure} disabled={!paymentId}>Mock fail</button> <button onClick={listBookings} disabled={!token}>History</button> <button onClick={viewSession} disabled={!sessionId}>Session</button> <button onClick={viewReport} disabled={!sessionId}>Report</button></div>
    </section>
    <section className="card"><h2>Activity</h2>{log.map((l,i)=><p key={i}>{l}</p>)}</section>
  </>
}
