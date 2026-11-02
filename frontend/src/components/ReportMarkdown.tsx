import type { ReactNode } from "react";
import "./ReportMarkdown.css";

// Report text is model output grounded in scraped pages, so it is rendered
// into React elements and never as HTML. Covers what the report prompt
// produces: headings, paragraphs, lists, bold/italic/code, links and [n]
// citations. Anything else (tables, quotes) falls back to plain paragraphs.

interface ReportMarkdownProps {
  content: string;
  /** Renders a citation marker for source n. */
  renderCitation: (n: number, key: string) => ReactNode;
}

type Block =
  | { kind: "heading"; level: number; text: string }
  | { kind: "paragraph"; text: string }
  | { kind: "list"; ordered: boolean; items: string[] };

const HEADING = /^(#{1,6})\s+(.*)$/;
const BULLET = /^\s*[-*+]\s+(.*)$/;
const NUMBERED = /^\s*\d+[.)]\s+(.*)$/;

export function ReportMarkdown({ content, renderCitation }: ReportMarkdownProps) {
  return (
    <div className="md">
      {parseBlocks(content).map((block, i) => {
        const inline = (text: string) => renderInline(text, `${i}`, renderCitation);
        switch (block.kind) {
          case "heading": {
            // The page title is the h1; report headings start at h2.
            const Tag = `h${Math.min(block.level + 1, 6)}` as "h2";
            return <Tag key={i}>{inline(block.text)}</Tag>;
          }
          case "list": {
            const Tag = block.ordered ? "ol" : "ul";
            return (
              <Tag key={i}>
                {block.items.map((item, j) => (
                  <li key={j}>{renderInline(item, `${i}.${j}`, renderCitation)}</li>
                ))}
              </Tag>
            );
          }
          case "paragraph":
            return <p key={i}>{inline(block.text)}</p>;
        }
      })}
    </div>
  );
}

function parseBlocks(content: string): Block[] {
  const blocks: Block[] = [];
  let paragraph: string[] = [];
  let list: { ordered: boolean; items: string[] } | null = null;

  const flush = () => {
    if (paragraph.length) blocks.push({ kind: "paragraph", text: paragraph.join(" ") });
    if (list) blocks.push({ kind: "list", ...list });
    paragraph = [];
    list = null;
  };

  for (const raw of content.split("\n")) {
    const line = raw.trimEnd();
    if (!line.trim() || /^\s*([-*_])\s*\1\s*\1[\s\-*_]*$/.test(line)) {
      flush();
      continue;
    }
    const heading = HEADING.exec(line);
    if (heading) {
      flush();
      blocks.push({ kind: "heading", level: heading[1].length, text: heading[2] });
      continue;
    }
    const bullet = BULLET.exec(line);
    const numbered = bullet ? null : NUMBERED.exec(line);
    const item = bullet ?? numbered;
    if (item) {
      const ordered = !!numbered;
      if (paragraph.length || (list && list.ordered !== ordered)) flush();
      list ??= { ordered, items: [] };
      list.items.push(item[1]);
      continue;
    }
    // A continuation line of a list item, or paragraph text.
    if (list && /^\s+/.test(raw)) {
      list.items[list.items.length - 1] += ` ${line.trim()}`;
    } else {
      if (list) flush();
      paragraph.push(line.trim());
    }
  }
  flush();
  return blocks;
}

// Order matters: code first so its contents aren't parsed further.
const INLINE = /(`[^`]+`)|(\*\*[^*]+\*\*|__[^_]+__)|(\*[^*\s][^*]*\*|_[^_\s][^_]*_)|(\[\d+\])|(\[[^\]]+\]\((https?:\/\/[^)\s]+)\))/g;

function renderInline(text: string, keyPrefix: string, renderCitation: ReportMarkdownProps["renderCitation"]): ReactNode[] {
  const out: ReactNode[] = [];
  let last = 0;
  let n = 0;
  for (const m of text.matchAll(INLINE)) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const key = `${keyPrefix}-${n++}`;
    const [token, code, bold, italic, citation, link, href] = m;
    if (code) out.push(<code key={key}>{code.slice(1, -1)}</code>);
    else if (bold) out.push(<strong key={key}>{renderInline(bold.slice(2, -2), key, renderCitation)}</strong>);
    else if (italic) out.push(<em key={key}>{renderInline(italic.slice(1, -1), key, renderCitation)}</em>);
    else if (citation) out.push(renderCitation(Number(citation.slice(1, -1)), key));
    else if (link)
      out.push(
        <a key={key} href={href} target="_blank" rel="noreferrer noopener">
          {link.slice(1, link.indexOf("]("))}
        </a>,
      );
    else out.push(token);
    last = m.index + token.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}
