import { Fragment } from 'react'

// Renders plain message text as light, safe markup. Everything goes through
// React text nodes (never innerHTML):
//   - a blank line starts a new paragraph;
//   - consecutive lines starting with "- " or "• " become a <ul>;
//   - any other newline is kept as a <br>.

type Block = { kind: 'paragraph'; lines: string[] } | { kind: 'list'; items: string[] }

const BULLET = /^\s*[-•]\s+(.*)$/

function toBlocks(text: string): Block[] {
  const blocks: Block[] = []
  const paragraphs = text.replace(/\r\n?/g, '\n').split(/\n[ \t]*\n/)

  for (const paragraph of paragraphs) {
    let lines: string[] | null = null
    let items: string[] | null = null

    for (const rawLine of paragraph.split('\n')) {
      const line = rawLine.trimEnd()
      const bullet = BULLET.exec(line)
      if (bullet && bullet[1].trim()) {
        if (!items) {
          items = []
          blocks.push({ kind: 'list', items })
          lines = null
        }
        items.push(bullet[1].trim())
      } else if (line.trim()) {
        if (!lines) {
          lines = []
          blocks.push({ kind: 'paragraph', lines })
          items = null
        }
        lines.push(line)
      }
    }
  }

  return blocks
}

interface MessageTextProps {
  text: string
}

export default function MessageText({ text }: MessageTextProps) {
  const blocks = toBlocks(text)

  return (
    <div className="rich-text">
      {blocks.map((block, index) =>
        block.kind === 'list' ? (
          <ul key={index}>
            {block.items.map((item, itemIndex) => (
              <li key={itemIndex}>{item}</li>
            ))}
          </ul>
        ) : (
          <p key={index}>
            {block.lines.map((line, lineIndex) => (
              <Fragment key={lineIndex}>
                {lineIndex > 0 && <br />}
                {line}
              </Fragment>
            ))}
          </p>
        ),
      )}
    </div>
  )
}
