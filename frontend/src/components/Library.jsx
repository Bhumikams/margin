import { useState } from 'react'
import Icon from './Icon.jsx'

/** Left rail: subjects → modules → files. Choosing one sets the search scope. */
export default function Library({ subjects, documents, scope, onScope, onAdd, onDelete, health }) {
  const [confirming, setConfirming] = useState(null)
  const docsBySubject = groupBy(documents, (d) => d.subject)
  const isAll = !scope.subject
  const readOnly = !!health?.read_only

  return (
    <nav className="library" aria-label="Your notes">
      <div className="wordmark">
        <span className="wordmark-bar" aria-hidden="true" />
        Margin
      </div>

      <div className="library-scroll">
        <button
          className="scope-row scope-all"
          aria-current={isAll ? 'true' : undefined}
          onClick={() => onScope({ subject: null, module: null })}
        >
          All notes
          <span className="count">{documents.length}</span>
        </button>

        {subjects.length === 0 && (
          <p className="library-empty">Subjects appear here once you add notes.</p>
        )}

        {subjects.map(({ subject, modules }) => {
          const open = scope.subject === subject
          const docs = docsBySubject[subject] || []
          return (
            <section key={subject} className={`subject ${open ? 'open' : ''}`}>
              <button
                className="scope-row subject-row"
                aria-current={open && !scope.module ? 'true' : undefined}
                aria-expanded={open}
                onClick={() => onScope({ subject, module: null })}
              >
                <Icon name="chevron" size={14} className="chev" />
                {subject}
                <span className="count">{docs.length}</span>
              </button>

              {open && (
                <div className="subject-body">
                  {modules.length > 0 && (
                    <div className="modules" role="group" aria-label={`${subject} modules`}>
                      {modules.map((m) => (
                        <button
                          key={m}
                          className="module-chip"
                          aria-pressed={scope.module === m}
                          onClick={() => onScope({ subject, module: scope.module === m ? null : m })}
                        >
                          Module {m}
                        </button>
                      ))}
                    </div>
                  )}
                  <ul className="files">
                    {docs.map((d) => (
                      <li key={d.doc_id} className="file">
                        <Icon name="file" size={15} />
                        <span className="file-name" title={d.file_name}>{d.file_name}</span>
                        <span className="file-meta">{d.pages}p</span>
                        {readOnly ? null : confirming === d.doc_id ? (
                          <span className="confirm">
                            <button className="link danger" onClick={() => { onDelete(d.doc_id); setConfirming(null) }}>
                              Remove
                            </button>
                            <button className="link" onClick={() => setConfirming(null)}>Keep</button>
                          </span>
                        ) : (
                          <button
                            className="icon-btn file-del"
                            aria-label={`Remove ${d.file_name}`}
                            onClick={() => setConfirming(d.doc_id)}
                          >
                            <Icon name="trash" size={15} />
                          </button>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </section>
          )
        })}
      </div>

      <div className="library-foot">
        {readOnly ? (
          <p className="demo-note">Demo library. Ask, practise and revise from these notes.</p>
        ) : (
          <button className="btn btn-primary btn-block" onClick={onAdd}>
            <Icon name="plus" size={16} /> Add notes
          </button>
        )}
        {health && (
          <p className="engine">
            {health.error ? 'Server offline' : `Answers by ${health.llm_provider === 'claude' ? 'Claude' : 'Groq'}`}
          </p>
        )}
      </div>
    </nav>
  )
}

function groupBy(list, key) {
  return list.reduce((acc, x) => ((acc[key(x)] ||= []).push(x), acc), {})
}
