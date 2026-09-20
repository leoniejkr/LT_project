import { describe, expect, it } from "vitest";
import { renderMarkdown } from "./markdown";

describe("renderMarkdown", () => {
	it("renders paragraphs and escapes HTML", () => {
		const html = renderMarkdown("Hello **world** <script>alert(1)</script>");
		expect(html).toContain("<p>");
		expect(html).toContain("<strong>world</strong>");
		expect(html).not.toContain("<script>");
		expect(html).toContain("&lt;script&gt;");
	});

	it("renders unordered and ordered lists", () => {
		const html = renderMarkdown("- one\n- two\n\n1. first\n2. second");
		expect(html).toContain("<ul><li>one</li><li>two</li></ul>");
		expect(html).toContain("<ol><li>first</li><li>second</li></ol>");
	});

	it("renders bold labels at the start of a line", () => {
		const html = renderMarkdown("**Symptoms:**\n- fever\n- cough");
		expect(html).toContain("<strong>Symptoms:</strong>");
		expect(html).toContain("<ul><li>fever</li><li>cough</li></ul>");
	});

	it("renders headings", () => {
		expect(renderMarkdown("### Treatment")).toContain("<h5>Treatment</h5>");
	});

	it("renders code spans", () => {
		expect(renderMarkdown("Use `O2` monito.")).toContain("<code>O2</code>");
	});

	it("keeps single newlines as soft breaks within a paragraph", () => {
		expect(renderMarkdown("line one\nline two")).toContain(
			"<p>line one<br>line two</p>",
		);
	});
});