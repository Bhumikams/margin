import { useState } from 'react'
import { api, scopeLabel } from '../api.js'
import Answer from './Answer.jsx'

/** One-page revision sheet for the scope, optionally narrowed to a topic. */
export default function ReviseView({ scope, focusN, onSources, onCite }) {
  const [topic, setTopic] = useState('')
  const [state, setState] = useState({ status: 'idle' })

  const make = async (e) => {
    e.preventDefault()
    setState({ status: 'pending' })
    try {
      const res = await api.summarize({ ...scope, topic: topic.trim() || null })
      setState({ status: 'done', ...res })
      const cited = [...res.summary.matchAll(/\[(\d+)\]/g)].map((m) => Number(m[1]))
      onSources(res.sources, cited)
    } catch (err) {
      setState({ status: 'error', error: err.message })
    }
  }

  return (
    <div className="workspace-scroll">
      <div className="column">
        <form className="tool-form" onSubmit={make}>
          <div className="field grow">
            <label htmlFor="rtopic">Focus on</label>
            <input
              id="rtopic"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder={`All of ${scopeLabel(scope)}`}
            />
          </div>
          <button className="btn btn-primary" disabled={state.status === 'pending'}>Make revision sheet</button>
        </form>

        {state.status === 'idle' && (
          <div className="tool-empty">
            <h1 className="starter-title">Revise in one page</h1>
            <p className="starter-lede">
              A short overview, the key terms with one-line meanings, and the topics most likely to be asked,
              all taken from your {scopeLabel(scope)} notes. Pick a module in the library to keep it tight.
            </p>
          </div>
        )}

        {state.status === 'pending' && (
          <div className="reading" role="status"><span className="reading-line" aria-hidden="true" />Reading your notes</div>
        )}

        {state.status === 'error' && <div className="callout callout-error" role="alert"><p>{state.error}</p></div>}

        {state.status === 'done' && (
          <article className="sheet">
            <p className="q-scope">{scopeLabel(scope)}{topic.trim() ? `, ${topic.trim()}` : ''}</p>
            <Answer text={state.summary} sourceCount={state.sources.length} activeN={focusN} onCite={onCite} />
          </article>
        )}
      </div>
    </div>
  )
}
