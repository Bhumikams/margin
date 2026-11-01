import { useEffect, useRef } from 'react'
import { pageLabel } from '../api.js'

/**
 * The margin: excerpts behind the current answer, set like annotations.
 * Cited excerpts first; the rest of what was retrieved below, quieter.
 */
export default function SourceMargin({ sources = [], cited = [], activeN, onHover, title }) {
  const refs = useRef({})

  useEffect(() => {
    const el = refs.current[activeN]
    if (el) el.scrollIntoView({ block: 'nearest', behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' })
  }, [activeN])

  const citedSet = new Set(cited.length ? cited : sources.map((s) => s.n))
  const primary = sources.filter((s) => citedSet.has(s.n))
  const rest = sources.filter((s) => !citedSet.has(s.n))

  return (
    <aside className="margin" aria-label="Sources">
      <h2 className="margin-title">{title}</h2>
      {sources.length === 0 ? (
        <p className="margin-empty">
          The pages behind each answer show up here, so you can check them against your notes.
        </p>
      ) : (
        <>
          <ol className="notes">
            {primary.map((s) => (
              <Note key={s.n} s={s} active={activeN === s.n} onHover={onHover} refFn={(el) => (refs.current[s.n] = el)} />
            ))}
          </ol>
          {rest.length > 0 && (
            <>
              <h3 className="margin-sub">Also retrieved, not cited</h3>
              <ol className="notes notes-quiet">
                {rest.map((s) => (
                  <Note key={s.n} s={s} active={activeN === s.n} onHover={onHover} refFn={(el) => (refs.current[s.n] = el)} />
                ))}
              </ol>
            </>
          )}
        </>
      )}
    </aside>
  )
}

function Note({ s, active, onHover, refFn }) {
  return (
    <li
      ref={refFn}
      className="note"
      data-active={active || undefined}
      onMouseEnter={() => onHover?.(s.n)}
    >
      <span className="note-n" aria-hidden="true">{s.n}</span>
      <div className="note-body">
        <p className="note-where">
          <strong>{s.file_name}</strong>, {pageLabel(s)}
        </p>
        <p className="note-scope">
          {s.subject}
          {s.module ? `, Module ${s.module}` : ''}
        </p>
        <p className="note-text">{s.snippet}</p>
      </div>
    </li>
  )
}

/** Compact version shown under answers on narrow screens, where there is no margin. */
export function InlineSources({ sources = [], cited = [] }) {
  if (!sources.length) return null
  const citedSet = new Set(cited)
  const list = cited.length ? sources.filter((s) => citedSet.has(s.n)) : sources
  return (
    <details className="inline-sources">
      <summary>
        {list.length} {list.length === 1 ? 'page' : 'pages'} from your notes
      </summary>
      <ol>
        {list.map((s) => (
          <li key={s.n}>
            <span className="note-n">{s.n}</span>
            <span>
              <strong>{s.file_name}</strong>, {pageLabel(s)}
              <span className="inline-snippet">{s.snippet}</span>
            </span>
          </li>
        ))}
      </ol>
    </details>
  )
}
