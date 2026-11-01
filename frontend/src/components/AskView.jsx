import { useEffect, useRef, useState } from 'react'
import Answer from './Answer.jsx'
import { InlineSources } from './SourceMargin.jsx'
import Icon from './Icon.jsx'
import { scopeLabel } from '../api.js'

export default function AskView({ thread, scope, subjects, focus, onFocus, onAsk, onClear }) {
  const endRef = useRef(null)
  const busy = thread.some((t) => t.status === 'pending')

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' })
  }, [thread.length])

  return (
    <>
      <div className="workspace-scroll">
        <div className="column">
          {thread.length === 0 ? (
            <Starter scope={scope} subjects={subjects} onAsk={onAsk} />
          ) : (
            <>
              {thread.map((t) => (
                <Turn key={t.id} t={t} focus={focus} onFocus={onFocus} onRetry={() => onAsk(t.question, t.id)} />
              ))}
              <div className="thread-end" ref={endRef}>
                <button className="link" onClick={onClear} disabled={busy}>Start a new session</button>
              </div>
            </>
          )}
        </div>
      </div>
      <Composer scope={scope} busy={busy} onSubmit={onAsk} />
    </>
  )
}

function Turn({ t, focus, onFocus, onRetry }) {
  const isFocused = focus.id === t.id
  return (
    <article
      className="turn"
      data-focused={isFocused || undefined}
      onMouseEnter={() => t.status === 'done' && !isFocused && onFocus(t.id, null)}
    >
      <header className="turn-q">
        <p className="q-text">{t.question}</p>
        <p className="q-scope">{scopeLabel(t.scope)}</p>
      </header>

      {t.status === 'pending' && (
        <div className="reading" role="status">
          <span className="reading-line" aria-hidden="true" />
          Reading your notes
        </div>
      )}

      {t.status === 'error' && (
        <div className="callout callout-error" role="alert">
          <p>{t.error}</p>
          <button className="link" onClick={onRetry}>Ask again</button>
        </div>
      )}

      {t.status === 'done' && (
        <>
          <Answer
            text={t.answer}
            sourceCount={t.sources.length}
            activeN={isFocused ? focus.n : null}
            onCite={(n, pin) => onFocus(t.id, n, pin)}
          />
          <InlineSources sources={t.sources} cited={t.cited} />
        </>
      )}
    </article>
  )
}

function Starter({ scope, subjects, onAsk }) {
  const pool = scope.subject ? subjects.filter((s) => s.subject === scope.subject) : subjects
  const prompts = []
  for (const { subject, modules } of pool.slice(0, 3)) {
    const m = scope.module || modules[0]
    if (m) prompts.push(`Explain the main ideas of Module ${m} in ${subject} as exam points`)
    prompts.push(`Which topics in ${subject} could come as 10-mark questions?`)
  }
  prompts.push('Define the key terms from these notes with one example each')

  return (
    <div className="starter">
      <h1 className="starter-title">What are you revising?</h1>
      <p className="starter-lede">
        Answers come only from {scope.subject ? `your ${scopeLabel(scope)} notes` : 'the notes you added'}, with
        the page each point came from.
      </p>
      <ul className="starter-prompts">
        {prompts.slice(0, 4).map((p) => (
          <li key={p}>
            <button className="prompt" onClick={() => onAsk(p)}>{p}</button>
          </li>
        ))}
      </ul>
    </div>
  )
}

function Composer({ scope, busy, onSubmit }) {
  const [text, setText] = useState('')
  const ref = useRef(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 200) + 'px'
  }, [text])

  const send = (e) => {
    e?.preventDefault()
    const q = text.trim()
    if (!q || busy) return
    onSubmit(q)
    setText('')
  }

  return (
    <form className="composer" onSubmit={send}>
      <div className="composer-box">
        <label htmlFor="question" className="sr-only">Your question</label>
        <textarea
          id="question"
          ref={ref}
          rows={1}
          value={text}
          placeholder={`Ask about ${scope.subject ? `your ${scopeLabel(scope)} notes` : 'your notes'}`}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) send(e)
          }}
        />
        <button className="btn btn-primary composer-send" disabled={busy || !text.trim()} aria-label="Ask">
          <Icon name="send" size={18} />
        </button>
      </div>
      <p className="composer-hint">Enter to ask, Shift + Enter for a new line</p>
    </form>
  )
}
