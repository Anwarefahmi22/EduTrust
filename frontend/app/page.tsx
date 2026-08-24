import Link from 'next/link'

export default function LoginShell() {
  return (
    <section className="card">
      <span className="badge info">DEV shell only</span>
      <h1>EduTrust Login</h1>
      <p className="muted">Authentication shell for the approved MVP. Detailed UI screens are intentionally not implemented in Sprint 1.</p>
      <div className="grid">
        <Link className="primary" href="/parent">Parent dashboard shell</Link>
        <Link className="primary" href="/teacher">Teacher dashboard shell</Link>
        <Link className="primary" href="/admin">Admin dashboard shell</Link>
      </div>
    </section>
  )
}
