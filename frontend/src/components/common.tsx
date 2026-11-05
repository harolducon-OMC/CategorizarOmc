import { ArrowRight, FolderOpen } from 'lucide-react'

export function NavButton({ active, onClick, icon, label }: { active: boolean; onClick: () => void; icon: React.ReactNode; label: string }) {
  return <button className={`nav-button ${active ? 'active' : ''}`} onClick={onClick}>{icon}<span>{label}</span>{active && <span className="nav-active-mark" />}</button>
}

export function PageHeading({ eyebrow, title, text, action }: { eyebrow: string; title: string; text: string; action?: React.ReactNode }) {
  return <div className="page-heading"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{text}</p></div>{action && <div className="heading-action">{action}</div>}</div>
}

export function MetricCard({ icon, label, value, sub, color }: { icon: React.ReactNode; label: string; value: string | number; sub: string; color: string }) {
  return <div className="metric-card"><div className={`metric-icon ${color}`}>{icon}</div><div><span>{label}</span><strong>{value}</strong><small>{sub}</small></div></div>
}

export function DataTable({ columns, rows }: { columns: string[]; rows: Record<string, any>[] }) {
  if (!rows.length) return <div className="empty-inline">Sin filas para mostrar.</div>
  return <div className="table-scroll"><table><thead><tr>{columns.slice(0, 8).map((c) => <th key={c}>{c}</th>)}</tr></thead><tbody>{rows.slice(0, 8).map((row, i) => <tr key={i}>{columns.slice(0, 8).map((c) => <td key={c}>{String(row[c] ?? '—').slice(0, 90)}</td>)}</tr>)}</tbody></table></div>
}

export function EmptyState({ title, text, action }: { title: string; text: string; action: string }) {
  return <div className="empty-state"><div className="empty-state-mark"><FolderOpen size={25} /></div><h2>{title}</h2><p>{text}</p><a href="/" className="button-secondary">{action} <ArrowRight size={15} /></a></div>
}
