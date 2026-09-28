import React from 'react';

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

/**
 * Format inline markdown:
 * - **bold** or __bold__
 * - *italic* or _italic_
 * - `code`
 * - [label](url)
 */
function renderInline(text: string): React.ReactNode[] {
  // Regex splitting by bold, code, italic, link
  // Tokens:
  // 1. `code`
  // 2. **bold** or __bold__
  // 3. *italic* or _italic_
  // 4. [text](url)
  const tokenRegex = /(`[^`]+`|\*\*[^*]+\*\*|__[^_]+__|\*[^*]+\*|_[^_]+_|\[[^\]]+\]\([^)]+\))/g;
  const parts = text.split(tokenRegex);

  return parts.map((part, i) => {
    if (!part) return null;

    // Inline code
    if (part.startsWith('`') && part.endsWith('`') && part.length >= 2) {
      return (
        <code key={i} className="md-inline-code">
          {part.slice(1, -1)}
        </code>
      );
    }

    // Bold (**text** or __text__)
    if (
      (part.startsWith('**') && part.endsWith('**') && part.length >= 4) ||
      (part.startsWith('__') && part.endsWith('__') && part.length >= 4)
    ) {
      return (
        <strong key={i} className="md-bold">
          {part.slice(2, -2)}
        </strong>
      );
    }

    // Italic (*text* or _text_)
    if (
      (part.startsWith('*') && part.endsWith('*') && part.length >= 2) ||
      (part.startsWith('_') && part.endsWith('_') && part.length >= 2)
    ) {
      return (
        <em key={i} className="md-italic">
          {part.slice(1, -1)}
        </em>
      );
    }

    // Link [text](url)
    const linkMatch = part.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
    if (linkMatch) {
      return (
        <a
          key={i}
          href={linkMatch[2]}
          target="_blank"
          rel="noopener noreferrer"
          className="md-link"
        >
          {linkMatch[1]}
        </a>
      );
    }

    return <React.Fragment key={i}>{part}</React.Fragment>;
  });
}

/**
 * Pre-processes text: if an answer has inline numbered lists like "1. Roads: ... 2. Buildings: ...",
 * formats them onto separate lines for better readability.
 */
function preprocessText(raw: string): string {
  if (!raw) return '';

  // Expand inline numbered lists like: "Key features: 1. Buildings: ... 2. Roads: ..."
  // Replace pattern " 1. " or ". 1. " with "\n\n1. "
  let processed = raw.replace(/([.?!])\s+(\d+\.\s+)/g, '$1\n\n$2');

  // Also replace colon followed by list: "features: 1. " -> "features:\n\n1. "
  processed = processed.replace(/:\s+(\d+\.\s+)/g, ':\n\n$1');

  return processed;
}

export const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ content, className = '' }) => {
  if (!content) return null;

  const normalized = preprocessText(content.replace(/\r\n/g, '\n'));
  const lines = normalized.split('\n');

  const elements: React.ReactNode[] = [];
  let currentList: { type: 'ol' | 'ul'; items: string[] } | null = null;
  let currentParagraph: string[] = [];

  const flushParagraph = () => {
    if (currentParagraph.length > 0) {
      const text = currentParagraph.join(' ').trim();
      if (text) {
        elements.push(
          <p key={`p-${elements.length}`} className="md-paragraph">
            {renderInline(text)}
          </p>
        );
      }
      currentParagraph = [];
    }
  };

  const flushList = () => {
    if (currentList) {
      const { type, items } = currentList;
      if (type === 'ol') {
        elements.push(
          <ol key={`ol-${elements.length}`} className="md-ol">
            {items.map((item, idx) => (
              <li key={idx} className="md-li">
                {renderInline(item)}
              </li>
            ))}
          </ol>
        );
      } else {
        elements.push(
          <ul key={`ul-${elements.length}`} className="md-ul">
            {items.map((item, idx) => (
              <li key={idx} className="md-li">
                {renderInline(item)}
              </li>
            ))}
          </ul>
        );
      }
      currentList = null;
    }
  };

  for (let i = 0; i < lines.length; i++) {
    const rawLine = lines[i];
    const line = rawLine.trim();

    // Empty line
    if (!line) {
      flushParagraph();
      flushList();
      continue;
    }

    // Code block marker ```
    if (line.startsWith('```')) {
      flushParagraph();
      flushList();
      // collect until next ```
      const codeLines: string[] = [];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith('```')) {
        codeLines.push(lines[i]);
        i++;
      }
      elements.push(
        <pre key={`code-${elements.length}`} className="md-code-block">
          <code>{codeLines.join('\n')}</code>
        </pre>
      );
      continue;
    }

    // Headings
    if (line.startsWith('#')) {
      flushParagraph();
      flushList();

      const h1Match = line.match(/^#\s+(.+)$/);
      if (h1Match) {
        elements.push(
          <h3 key={`h1-${elements.length}`} className="md-heading md-h1">
            {renderInline(h1Match[1])}
          </h3>
        );
        continue;
      }
      const h2Match = line.match(/^##\s+(.+)$/);
      if (h2Match) {
        elements.push(
          <h4 key={`h2-${elements.length}`} className="md-heading md-h2">
            {renderInline(h2Match[1])}
          </h4>
        );
        continue;
      }
      const h3Match = line.match(/^###\s+(.+)$/);
      if (h3Match) {
        elements.push(
          <h5 key={`h3-${elements.length}`} className="md-heading md-h3">
            {renderInline(h3Match[1])}
          </h5>
        );
        continue;
      }
      const h4Match = line.match(/^####+\s+(.+)$/);
      if (h4Match) {
        elements.push(
          <h6 key={`h4-${elements.length}`} className="md-heading md-h4">
            {renderInline(h4Match[1])}
          </h6>
        );
        continue;
      }
    }

    // Blockquote
    if (line.startsWith('>')) {
      flushParagraph();
      flushList();
      const quoteText = line.replace(/^>\s*/, '');
      elements.push(
        <blockquote key={`quote-${elements.length}`} className="md-blockquote">
          {renderInline(quoteText)}
        </blockquote>
      );
      continue;
    }

    // Numbered list: e.g. "1. Item" or "1) Item"
    const olMatch = line.match(/^(\d+)[\.\)]\s+(.+)$/);
    if (olMatch) {
      flushParagraph();
      if (!currentList || currentList.type !== 'ol') {
        flushList();
        currentList = { type: 'ol', items: [] };
      }
      currentList.items.push(olMatch[2]);
      continue;
    }

    // Bullet list: e.g. "- Item", "* Item", "• Item", "+ Item"
    const ulMatch = line.match(/^[\-\*•\+]\s+(.+)$/);
    if (ulMatch) {
      flushParagraph();
      if (!currentList || currentList.type !== 'ul') {
        flushList();
        currentList = { type: 'ul', items: [] };
      }
      currentList.items.push(ulMatch[1]);
      continue;
    }

    // Normal text line
    if (currentList) {
      // Check if continuation of previous list item
      if (rawLine.startsWith('   ') || rawLine.startsWith('\t')) {
        const lastIdx = currentList.items.length - 1;
        if (lastIdx >= 0) {
          currentList.items[lastIdx] += ' ' + line;
          continue;
        }
      }
      flushList();
    }

    currentParagraph.push(line);
  }

  flushParagraph();
  flushList();

  return <div className={`markdown-body-container ${className}`}>{elements}</div>;
};
