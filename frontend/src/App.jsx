import { useCallback, useEffect, useMemo, useState } from 'react'
import { api, scopeLabel } from './api.js'
import Library from './components/Library.jsx'
import AskView from './components/AskView.jsx'
import PracticeView from './components/PracticeView.jsx'
import ReviseView from './components/ReviseView.jsx'
import SourceMargin from './components/SourceMargin.jsx'
import UploadDialog from './components/UploadDialog.jsx'
import Icon from './components/Icon.jsx'

const MODES = [
  { id: 'ask', label: 'Ask' },
  { id: 'practice', label: 'Practice' },
  { id: 'revise', label: 'Revise' },
]

let nextId = 1

export default function App() {
  const [subjects, setSubjects] = useState([])
  const [documents, setDocuments] = useState([])
  const [loaded, setLoaded] = useState(false)
  const [loadError, setLoadError] = useState(null)
  const [health, setHealth] = useState(null)

  const [scope, setScope] = useState({ subject: null, module: null })
  const [mode, setMode] = useState('ask')
  const [thread, setThread] = useState([])
  const [focus, setFocus] = useState({ id: null, n: null })
  const [tool, setTool] = useState({ sources: [], cited: [], n: null }) // practice / revise margin

  const [uploadOpen, setUploadOpen] = useState(false)
  const [drawer, setDrawer] = useState(false)

  const refresh = useCallback(async () => {
    try {
      const [s, d] = await Promise.all([api.subjects(), api.documents()])
      setSubjects(s)
      setDocuments(d)
      setLoadError(null)
    } catch (e) {
      setLoadError(e.message)
    } finally {
      setLoaded(true)
    }
  }, [])

  useEffect(() => {
    refresh()
    api.health().then(setHealth).catch(() => setHealth({ error: true }))
  }, [refresh])

  // Keep scope valid if a subject disappears after deleting its last file
  useEffect(() => {
    if (scope.subject && loaded && !subjects.some((s) => s.subject === scope.subject)) {
      setScope({ subject: null, module: null })
    }
  }, [subjects, scope.subject, loaded])

  const ask = async (question, retryId) => {
    const id = retryId ?? nextId++
    const turn = { id, question, scope, status: 'pending' }
    const history = thread
      .filter((t) => t.status === 'done' && t.id !== id)
      .slice(-3)
      .flatMap((t) => [
        { role: 'user', content: t.question },
        { role: 'assistant', content: t.answer },
      ])
    setThread((cur) => (retryId ? cur.map((t) => (t.id === id ? turn : t)) : [...cur, turn]))
    setFocus({ id, n: null })
    try {
      const res = await api.ask({ question, ...scope, history })
      setThread((cur) => cur.map((t) => (t.id === id ? { ...t, ...res, status: 'done' } : t)))
    } catch (e) {
      setThread((cur) => cur.map((t) => (t.id === id ? { ...t, status: 'error', error: e.message } : t)))
    }
  }

  const deleteDoc = async (id) => {
    try {
      await api.deleteDocument(id)
    } finally {
      refresh()
    }
  }

  const changeScope = (s) => {
    setScope(s)
    setTool({ sources: [], cited: [], n: null })
    setDrawer(false)
  }

  // What the margin shows depends on the mode
  const margin = useMemo(() => {
    if (mode === 'ask') {
      const t =
        thread.find((x) => x.id === focus.id && x.status === 'done') ||
        [...thread].reverse().find((x) => x.status === 'done')
      return {
        sources: t?.sources || [],
        cited: t?.cited || [],
        n: t && t.id === focus.id ? focus.n : null,
        title: t ? 'From your notes' : 'Sources',
        onHover: (n) => t && setFocus({ id: t.id, n }),
      }
    }
    return {
      ...tool,
      title: tool.sources.length ? 'From your notes' : 'Sources',
      onHover: (n) => setTool((x) => ({ ...x, n })),
    }
  }, [mode, thread, focus, tool])

  const hasNotes = documents.length > 0

  return (
    <div className="app" data-drawer={drawer || undefined}>
      <Library
        subjects={subjects}
        documents={documents}
        scope={scope}
        onScope={changeScope}
        onAdd={() => { setUploadOpen(true); setDrawer(false) }}
        onDelete={deleteDoc}
        health={health}
      />
      <div className="scrim" onClick={() => setDrawer(false)} aria-hidden="true" />

      <main className="workspace">
        <header className="topbar">
          <button className="icon-btn menu-btn" aria-label="Open library" onClick={() => setDrawer(true)}>
            <Icon name="menu" />
          </button>
          <p className="topbar-scope" aria-live="polite">{scopeLabel(scope)}</p>
          <div className="modes" role="tablist" aria-label="Mode">
            {MODES.map((m) => (
              <button
                key={m.id}
                role="tab"
                aria-selected={mode === m.id}
                className="mode"
                onClick={() => { setMode(m.id); setTool({ sources: [], cited: [], n: null }) }}
              >
                {m.label}
              </button>
            ))}
          </div>
        </header>

        {!loaded ? (
          <div className="workspace-scroll"><div className="column"><div className="reading" role="status"><span className="reading-line" />Opening your library</div></div></div>
        ) : loadError ? (
          <Notice title="The server isn't responding" body={loadError} action="Try again" onAction={refresh} />
        ) : !hasNotes && health?.read_only ? (
          <Notice
            title="No notes here yet"
            body="This demo library is empty right now. Check back soon."
          />
        ) : !hasNotes ? (
          <Notice
            title="Start with your notes"
            body="Add lecture notes, slides or the syllabus for a subject. Every answer, question and revision sheet is built only from what you add, with the page it came from."
            action="Add notes"
            onAction={() => setUploadOpen(true)}
          />
        ) : mode === 'ask' ? (
          <AskView
            thread={thread}
            scope={scope}
            subjects={subjects}
            focus={focus}
            onFocus={(id, n) => setFocus({ id, n })}
            onAsk={ask}
            onClear={() => { setThread([]); setFocus({ id: null, n: null }) }}
          />
        ) : mode === 'practice' ? (
          <PracticeView
            key={scopeLabel(scope)}
            scope={scope}
            onSources={(sources, cited) => setTool({ sources, cited, n: null })}
            onFocusSource={(n) => setTool((x) => ({ ...x, n }))}
          />
        ) : (
          <ReviseView
            key={scopeLabel(scope)}
            scope={scope}
            focusN={tool.n}
            onSources={(sources, cited) => setTool({ sources, cited, n: null })}
            onCite={(n) => setTool((x) => ({ ...x, n }))}
          />
        )}
      </main>

      <SourceMargin sources={margin.sources} cited={margin.cited} activeN={margin.n} onHover={margin.onHover} title={margin.title} />

      <UploadDialog
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        subjects={subjects}
        defaultSubject={scope.subject}
        onUploaded={refresh}
      />
    </div>
  )
}

function Notice({ title, body, action, onAction }) {
  return (
    <div className="workspace-scroll">
      <div className="column">
        <div className="tool-empty">
          <h1 className="starter-title">{title}</h1>
          <p className="starter-lede">{body}</p>
          {action && <button className="btn btn-primary" onClick={onAction}>{action}</button>}
        </div>
      </div>
    </div>
  )
}
