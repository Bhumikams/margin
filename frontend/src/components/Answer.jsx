import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

/** Turn the model's "[2]" markers into links the renderer can swap for citation marks. */
function linkCitations(text, max) {
  return text.replace(/\[(\d+)\](?!\()/g, (m, n) =>
    Number(n) >= 1 && Number(n) <= max ? `[${n}](#cite-${n})` : m
  )
}

/**
 * Markdown answer where each [n] becomes a highlighter mark. Hovering or focusing a mark
 * lights up the matching note in the margin; clicking pins it.
 */
export default function Answer({ text, sourceCount, activeN, onCite }) {
  return (
    <div className="prose">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a({ href = '', children, ...rest }) {
            const m = href.match(/^#cite-(\d+)$/)
            if (!m) return <a href={href} target="_blank" rel="noreferrer" {...rest}>{children}</a>
            const n = Number(m[1])
            return (
              <button
                type="button"
                className="cite"
                data-active={activeN === n || undefined}
                aria-label={`Source ${n}`}
                onMouseEnter={() => onCite(n, false)}
                onFocus={() => onCite(n, false)}
                onClick={() => onCite(n, true)}
              >
                {n}
              </button>
            )
          },
        }}
      >
        {linkCitations(text, sourceCount)}
      </ReactMarkdown>
    </div>
  )
}
