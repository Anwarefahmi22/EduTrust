'use client'
import { useState } from 'react'
import { apiGet, apiPatch, apiPost } from '../../lib/api'

export default function TeacherDashboardShell() {
  const [email, setEmail] = useState(`teacher-${Date.now()}@example.com`)
  const [password] = useState('StrongPassword123!')
  const [token, setToken] = useState('')
  const [subjectId, setSubjectId] = useState('')
  const [levelId, setLevelId] = useState('')
  const [sessionId, setSessionId] = useState('')
  const [log, setLog] = useState<string[]>([])
  const [myReviews, setMyReviews] = useState<any[]>([])
  const [myDisputes, setMyDisputes] = useState<any[]>([])
  const [myPayouts, setMyPayouts] = useState<any[]>([])
  const [payoutDetail, setPayoutDetail] = useState<any | null>(null)
  const addLog = (m: string) => setLog((l) => [m, ...l].slice(0, 12))
  async function registerLogin() { await apiPost('/api/v1/auth/register', { role:'TEACHER', full_name:'Teacher User', email, password }); const res:any=await apiPost('/api/v1/auth/login',{identifier:email,password}); setToken(res.data.access_token); addLog('Teacher logged in') }
  async function updateProfile() { const res:any=await apiPatch('/api/v1/teachers/me',{ bio:'Mathematics tutor', teaching_modes:['ONLINE']}, token); addLog(`Profile ${res.data.public_name}`) }
  async function addSubject() { const res:any=await apiPost('/api/v1/teachers/subjects',{subject_id:subjectId, academic_level_id:levelId, price:{amount:'2000.00'}, session_duration_minutes:60},token); addLog(`Subject added ${res.data.id}`) }
  async function createSlot() { const starts=new Date(Date.now()+7*86400000).toISOString(); const ends=new Date(Date.now()+7*86400000+3600000).toISOString(); const res:any=await apiPost('/api/v1/teachers/availability/slots',{starts_at:starts, ends_at:ends, mode:'ONLINE'},token); addLog(`Slot ${res.data.id}`) }
  async function bookings() { const res:any=await apiGet('/api/v1/bookings?scope=teacher',token); addLog(`Teacher bookings ${res.data.length}`) }
  async function sessions() { const res:any=await apiGet('/api/v1/sessions',token); addLog(`Sessions ${res.data.length}`); if(res.data[0]) setSessionId(res.data[0].id) }
  async function startSession() { const res:any=await apiPost(`/api/v1/sessions/${sessionId}/start`,{},token); addLog(`Session ${res.data.status}`) }
  async function completeSession() { const res:any=await apiPost(`/api/v1/sessions/${sessionId}/complete`,{},token); addLog(`Session ${res.data.status}`) }
  async function studentNoShow() { const res:any=await apiPost(`/api/v1/sessions/${sessionId}/no-show`,{no_show_type:'STUDENT'},token); addLog(`No-show ${res.data.status}`) }
  async function submitReport() { const res:any=await apiPost(`/api/v1/sessions/${sessionId}/report`,{topics_covered:['Linear equations'],skills_practiced:['Solving equations'],participation:'HIGH',teacher_observations:'Good work',homework:'Exercises 1-3',recommended_revision:'Review basics',next_objectives:['Functions']},token); addLog(`Report ${res.data.id}; progress ${res.data.progress_events_created}`) }

  async function loadMyReviews() {
    const res: any = await apiGet('/api/v1/reviews', token)
    setMyReviews(res.data || [])
    addLog(`Reviews on my sessions: ${res.data.length}`)
  }
  async function loadMyDisputes() {
    const res: any = await apiGet('/api/v1/disputes', token)
    setMyDisputes(res.data || [])
    addLog(`Disputes involving me: ${res.data.length}`)
  }

  async function loadMyPayouts() {
    const res: any = await apiGet('/api/v1/teacher/payouts', token)
    setMyPayouts(res.data || [])
    addLog(`My payouts: ${res.data.length}`)
  }
  async function viewPayout(id: string) {
    const res: any = await apiGet(`/api/v1/teacher/payouts/${id}`, token)
    setPayoutDetail(res.data)
    addLog(`Payout ${res.data.status} — ${res.data.amount} ${res.data.currency}`)
  }

  return <>
    <section className="card"><span className="badge warning">Teacher vertical slice</span><h1>Teacher Dashboard</h1><p className="muted">DEV only. Configure subject IDs from seeded taxonomy.</p></section>
    <section className="grid">
      <div className="card"><h2>1. Login</h2><input value={email} onChange={e=>setEmail(e.target.value)} style={{width:'100%',padding:8}}/><br/><br/><button className="primary" onClick={registerLogin}>Register/Login</button></div>
      <div className="card"><h2>2. Profile</h2><button className="primary" onClick={updateProfile} disabled={!token}>Update profile</button></div>
      <div className="card"><h2>3. Subject/Pricing</h2><input placeholder="subject_id" value={subjectId} onChange={e=>setSubjectId(e.target.value)} style={{width:'100%',padding:8}}/><br/><input placeholder="academic_level_id" value={levelId} onChange={e=>setLevelId(e.target.value)} style={{width:'100%',padding:8,marginTop:8}}/><br/><br/><button className="primary" onClick={addSubject} disabled={!token||!subjectId||!levelId}>Add subject</button></div>
      <div className="card"><h2>4. Availability</h2><button className="primary" onClick={createSlot} disabled={!token}>Create slot</button> <button onClick={bookings} disabled={!token}>Bookings</button> <button onClick={sessions} disabled={!token}>Sessions</button><br/><br/><input placeholder="session_id" value={sessionId} onChange={e=>setSessionId(e.target.value)} style={{width:'100%',padding:8}}/><br/><br/><button onClick={startSession} disabled={!sessionId}>Start</button> <button onClick={completeSession} disabled={!sessionId}>Complete</button> <button onClick={studentNoShow} disabled={!sessionId}>Student no-show</button> <button onClick={submitReport} disabled={!sessionId}>Submit report</button></div>
    </section>
    <section className="card"><span className="badge success">VS4 — Reviews + Dispute visibility</span><h2>VS4 · My Reviews &amp; Disputes</h2>
      <button className="primary" onClick={loadMyReviews} disabled={!token}>Load my reviews</button>
      <button onClick={loadMyDisputes} disabled={!token}>Load disputes involving me</button>
      <ul>{myReviews.map(r=><li key={r.id}>{r.rating}★ — {r.student_display_name || 'student'}: {r.comment || 'no comment'} (verified={r.is_verified}, {r.status})</li>)}</ul>
      <ul>{myDisputes.map(d=><li key={d.id}>{d.category} · {d.status} · priority {d.priority} — {d.description || ''}</li>)}</ul>
    </section>
    <section className="card"><span className="badge success">VS5 — Payouts</span><h2>My Payouts</h2>
      <button className="primary" onClick={loadMyPayouts} disabled={!token}>Load my payouts</button>
      <ul>{myPayouts.map(p=><li key={p.id}>{p.status} · {p.amount} {p.currency} · items {p.item_count} — <a href="#" onClick={(e)=>{e.preventDefault();viewPayout(p.id)}}>details</a></li>)}</ul>
      {payoutDetail && <div><h3>Payout {payoutDetail.id} — {payoutDetail.status}</h3>
        <p className="muted">amount {payoutDetail.amount} {payoutDetail.currency} · eligible {payoutDetail.eligible_at} · paid {payoutDetail.paid_at || '—'}</p>
        <ul>{(payoutDetail.items||[]).map((it:any)=><li key={it.id}>session {it.session_id} — {it.amount} {it.currency}</li>)}</ul>
      </div>}
    </section>
    <section className="card"><h2>Activity</h2>{log.map((l,i)=><p key={i}>{l}</p>)}</section>
  </>
}
