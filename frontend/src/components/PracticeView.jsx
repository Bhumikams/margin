import { useState } from 'react'
import { api, scopeLabel, pageLabel } from '../api.js'
import Icon from './Icon.jsx'

const TYPE_LABEL = { mcq: 'Multiple choice', short: 'Short answer', long: 'Long answer' }

/** Exam practice generated from the notes in scope. */
export default function PracticeView({ scope, onSources, onFocusSource }) {
  const [topic, setTopic] = useState('')
  const [count, setCount] = useState(6)
  const [state, setState] = useState({ status: 'idle' })

  const generate = async (e) => {
    e.preventDefault()
    setState({ status: 'pending' })
    try {
      const res = await api.quiz({ ...scope, topic: topic.trim() || null, count })
      setState({ status: 'done', ...res, key: Date.now() })
      onSources(res.sources, res.questions.map((q) => q.source).filter(Boolean))
    } catch (err) {
      setState({ status: 'error', error: err.message })
    }
  }

  return (
    <div className="workspace-scroll">
      <div className="column">
        <form className="tool-form" onSubmit={generate}>
          <div className="field grow">
            <label htmlFor="topic">Topic</label>
            <input
              id="topic"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder={`Anything in ${scopeLabel(scope)}`}
            />
          </div>
          <div className="field">
            <label htmlFor="count">Questions</label>
            <select id="count" value={count} onChange={(e) => setCount(Number(e.target.value))}>
              {[4, 6, 8, 10].map((n) => <option key={n}>{n}</option>)}
            </select>
          </div>
          <button className="btn btn-primary" disabled={state.status === 'pending'}>
            {state.status === 'done' ? <><Icon name="refresh" size={16} /> New set</> : 'Make questions'}
          </button>
        </form>

        {state.status === 'idle' && (
          <div className="tool-empty">
            <h1 className="starter-title">Test yourself</h1>
            <p className="starter-lede">
              Questions are written from your {scopeLabel(scope)} notes, in the style of a university theory paper.
              Try answering before you open the model answer.
            </p>
          </div>
        )}

        {state.status === 'pending' && (
          <div className="reading" role="status"><span className="reading-line" aria-hidden="true" />Writing questions</div>
        )}

        {state.status === 'error' && (
          <div className="callout callout-error" role="alert"><p>{state.error}</p></div>
        )}

        {state.status === 'done' && state.questions.length === 0 && (
          <div className="callout"><p>No notes in {scopeLabel(scope)} yet. Add notes or widen the scope.</p></div>
        )}

        {state.status === 'done' && (
          <ol className="questions" key={state.key}>
            {state.questions.map((q, i) => (
              <Question key={i} i={i} q={q} sources={state.sources} onFocusSource={onFocusSource} />
            ))}
          </ol>
        )}
      </div>
    </div>
  )
}

function Question({ q, i, sources, onFocusSource }) {
  const [open, setOpen] = useState(false)
  const [picked, setPicked] = useState(null)
  const src = sources.find((s) => s.n === q.source)
  const isMcq = q.type === 'mcq' && Array.isArray(q.options) && q.options.length > 0
  const isCorrect = (opt) => normalise(opt) === normalise(q.answer) || normalise(q.answer).startsWith(normalise(opt))

  return (
    <li className="question">
      <div className="question-head">
        <span className="q-num">Q{i + 1}</span>
        <span className="q-type">{TYPE_LABEL[q.type] || 'Question'}</span>
      </div>
      <p className="question-text">{q.question}</p>

      {isMcq && (
        <div className="options" role="group" aria-label={`Options for question ${i + 1}`}>
          {q.options.map((opt) => {
            const state = picked == null ? '' : isCorrect(opt) ? 'right' : picked === opt ? 'wrong' : 'dim'
            return (
              <button
                key={opt}
                className="option"
                data-state={state || undefined}
                disabled={picked != null}
                onClick={() => setPicked(opt)}
              >
                {state === 'right' && <Icon name="check" size={16} />}
                {opt}
              </button>
            )
          })}
        </div>
      )}

      {!isMcq && (
        <button className="link" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
          {open ? 'Hide model answer' : 'Show model answer'}
        </button>
      )}

      {(open || (isMcq && picked != null && !q.options.some((o) => normalise(o) === normalise(q.answer)))) && (
        <div className="model-answer">
          <p>{q.answer}</p>
        </div>
      )}

      {src && (
        <button className="source-ref" onClick={() => onFocusSource(src.n)}>
          From {src.file_name}, {pageLabel(src)}
        </button>
      )}
    </li>
  )
}

const normalise = (s = '') => String(s).toLowerCase().replace(/^[a-d][).:\s]+/, '').trim()
