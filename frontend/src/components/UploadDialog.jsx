import { useEffect, useRef, useState } from 'react'
import { api } from '../api.js'
import Icon from './Icon.jsx'

const ACCEPT = '.pdf,.txt,.md'

export default function UploadDialog({ open, onClose, subjects, defaultSubject, onUploaded }) {
  const ref = useRef(null)
  const inputRef = useRef(null)
  const [files, setFiles] = useState([]) // {file, status, result, error}
  const [subject, setSubject] = useState('')
  const [module, setModule] = useState('')
  const [dragging, setDragging] = useState(false)
  const running = files.some((f) => f.status === 'indexing')
  const finished = files.length > 0 && files.every((f) => f.status === 'done' || f.status === 'error')

  useEffect(() => {
    const d = ref.current
    if (!d) return
    if (open && !d.open) {
      setFiles([])
      setSubject(defaultSubject || '')
      setModule('')
      d.showModal()
    } else if (!open && d.open) d.close()
  }, [open, defaultSubject])

  const addFiles = (list) => {
    const picked = [...list].filter((f) => /\.(pdf|txt|md)$/i.test(f.name))
    setFiles((cur) => [
      ...cur.filter((c) => c.status !== 'queued' || !picked.some((p) => p.name === c.file.name)),
      ...picked.map((file) => ({ file, status: 'queued' })),
    ])
  }

  const update = (i, patch) => setFiles((cur) => cur.map((f, j) => (j === i ? { ...f, ...patch } : f)))

  const start = async (e) => {
    e.preventDefault()
    if (!subject.trim() || !files.length) return
    for (let i = 0; i < files.length; i++) {
      if (files[i].status !== 'queued') continue
      update(i, { status: 'indexing' })
      try {
        const result = await api.upload(files[i].file, subject.trim(), module.trim())
        update(i, { status: 'done', result })
      } catch (err) {
        update(i, { status: 'error', error: err.message })
      }
    }
    onUploaded()
  }

  return (
    <dialog ref={ref} className="dialog" onClose={onClose} onCancel={(e) => running && e.preventDefault()}>
      <form className="dialog-inner" onSubmit={start}>
        <header className="dialog-head">
          <h2>Add notes</h2>
          <button type="button" className="icon-btn" aria-label="Close" onClick={onClose} disabled={running}>
            <Icon name="close" />
          </button>
        </header>

        <div
          className="dropzone"
          data-dragging={dragging || undefined}
          onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => { e.preventDefault(); setDragging(false); addFiles(e.dataTransfer.files) }}
        >
          <Icon name="upload" size={22} />
          <p>
            Drop lecture notes, slides or a syllabus here, or{' '}
            <button type="button" className="link" onClick={() => inputRef.current?.click()}>choose files</button>
          </p>
          <p className="hint">PDF, TXT or Markdown. Scanned PDFs need OCR first.</p>
          <input ref={inputRef} type="file" accept={ACCEPT} multiple hidden onChange={(e) => addFiles(e.target.files)} />
        </div>

        {files.length > 0 && (
          <ul className="upload-list">
            {files.map((f, i) => (
              <li key={f.file.name + i} data-status={f.status}>
                <Icon name={f.status === 'done' ? 'check' : 'file'} size={16} />
                <span className="file-name">{f.file.name}</span>
                <span className="upload-status">{statusText(f)}</span>
              </li>
            ))}
          </ul>
        )}

        <div className="field-row">
          <div className="field grow">
            <label htmlFor="subject">Subject</label>
            <input
              id="subject"
              list="subject-options"
              value={subject}
              required
              onChange={(e) => setSubject(e.target.value)}
              placeholder="e.g. NoSQL"
            />
            <datalist id="subject-options">
              {subjects.map((s) => <option key={s.subject} value={s.subject} />)}
            </datalist>
          </div>
          <div className="field narrow">
            <label htmlFor="module">Module</label>
            <input id="module" value={module} inputMode="numeric" onChange={(e) => setModule(e.target.value)} placeholder="Auto" />
          </div>
        </div>
        <p className="hint">Leave module blank to pick it up from “Module 1”, “Module 2” headings in the file.</p>

        <footer className="dialog-foot">
          {finished ? (
            <button type="button" className="btn btn-primary" onClick={onClose}>Done</button>
          ) : (
            <button className="btn btn-primary" disabled={running || !files.length || !subject.trim()}>
              {running
                ? 'Adding to library…'
                : files.length
                  ? `Add ${files.length} ${files.length === 1 ? 'file' : 'files'}`
                  : 'Add files'}
            </button>
          )}
        </footer>
      </form>
    </dialog>
  )
}

function statusText(f) {
  if (f.status === 'queued') return 'Ready'
  if (f.status === 'indexing') return 'Reading pages'
  if (f.status === 'error') return f.error
  const r = f.result
  if (r.status === 'already_indexed') return 'Already in your library'
  const mods = r.modules_detected?.length ? `, modules ${r.modules_detected.join(', ')}` : ''
  return `${r.pages} pages${mods}`
}
