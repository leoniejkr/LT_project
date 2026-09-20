/** Minimal, dependency-free Markdown renderer for chat replies.
 *
 * The LLM answers with the small Markdown subset used by clinical replies:
 * `**bold**`, `*italic*`, `` `code` ``, `-` / `1.` lists and `#`–`###` headings.
 * Everything is HTML-escaped first, so model output can never inject markup.
 */

function escapeHtml(s: string): string {
	return s
		.replace(/&/g, "&amp;")
		.replace(/</g, "&lt;")
		.replace(/>/g, "&gt;")
		.replace(/"/g, "&quot;")
		.replace(/'/g, "&#39;");
}

function inline(text: string): string {
	let t = escapeHtml(text);
	t = t.replace(/`([^`]+)`/g, "<code>$1</code>");
	t = t.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
	t = t.replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<em>$2</em>");
	return t;
}

const BULLET_RE = /^[-*]\s+/;
const ORDERED_RE = /^\d+[.)]\s+/;
const HEADING_RE = /^(#{1,3})\s+(.+)$/;

export function renderMarkdown(text: string): string {
	const lines = text.replace(/\r/g, "").split("\n");
	const out: string[] = [];

	let paragraph: string[] = [];
	let listTag: "ul" | "ol" | null = null;
	let items: string[] = [];

	function flushParagraph() {
		if (paragraph.length > 0) {
			out.push(`<p>${paragraph.map(inline).join("<br>")}</p>`);
			paragraph = [];
		}
	}

	function flushList() {
		if (listTag) {
			out.push(`<${listTag}>${items.join("")}</${listTag}>`);
			listTag = null;
			items = [];
		}
	}

	for (const raw of lines) {
		const line = raw.trim();
		if (line === "") {
			flushParagraph();
			flushList();
			continue;
		}

		const heading = HEADING_RE.exec(line);
		if (heading) {
			flushParagraph();
			flushList();
			const level = heading[1].length + 2;
			out.push(`<h${level}>${inline(heading[2])}</h${level}>`);
			continue;
		}

		const isBullet = BULLET_RE.test(line);
		const isOrdered = ORDERED_RE.test(line);
		if (isBullet || isOrdered) {
			const tag = isOrdered ? "ol" : "ul";
			flushParagraph();
			if (listTag !== tag) flushList();
			listTag = tag;
			const content = line.replace(/^[-*]\s+|^\d+[.)]\s+/, "");
			items.push(`<li>${inline(content)}</li>`);
			continue;
		}

		flushList();
		paragraph.push(line);
	}

	flushParagraph();
	flushList();
	return out.join("");
}