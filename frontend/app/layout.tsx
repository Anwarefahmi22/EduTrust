import '../styles/globals.css'
import Link from 'next/link'
import type { ReactNode } from 'react'

export const metadata = {
  title: 'EduTrust Algeria',
  description: 'DEV foundation shell for EduTrust MVP',
}

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="shell">
          <header className="header">
            <Link className="brand" href="/">EduTrust</Link>
            <nav className="nav" aria-label="Role navigation">
              <Link href="/parent">Parent</Link>
              <Link href="/teacher">Teacher</Link>
              <Link href="/admin">Admin</Link>
            </nav>
          </header>
          <main className="main">{children}</main>
        </div>
      </body>
    </html>
  )
}
