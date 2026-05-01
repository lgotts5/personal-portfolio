const output = document.querySelector("#briefing-output");

const escapeHtml = (value) =>
  value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");

const inlineMarkdown = (value) =>
  escapeHtml(value)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\*([^*]+)\*/g, "<em>$1</em>");

const isTableDivider = (line) => /^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$/.test(line);
const isTableRow = (line) => line.trim().startsWith("|") && line.trim().endsWith("|");

const cellsFromRow = (line) =>
  line
    .trim()
    .slice(1, -1)
    .split("|")
    .map((cell) => inlineMarkdown(cell.trim()));

const renderTable = (lines, start) => {
  const headers = cellsFromRow(lines[start]);
  let index = start + 2;
  const rows = [];

  while (index < lines.length && isTableRow(lines[index])) {
    rows.push(cellsFromRow(lines[index]));
    index += 1;
  }

  const head = `<thead><tr>${headers.map((cell) => `<th>${cell}</th>`).join("")}</tr></thead>`;
  const body = rows
    .map((row) => `<tr>${row.map((cell) => `<td>${cell}</td>`).join("")}</tr>`)
    .join("");

  return {
    html: `<table>${head}<tbody>${body}</tbody></table>`,
    next: index,
  };
};

const renderMarkdown = (markdown) => {
  const lines = markdown.split(/\r?\n/);
  const html = [];
  let index = 0;
  let listType = null;

  const closeList = () => {
    if (listType) {
      html.push(`</${listType}>`);
      listType = null;
    }
  };

  while (index < lines.length) {
    const line = lines[index];
    const trimmed = line.trim();

    if (!trimmed) {
      closeList();
      index += 1;
      continue;
    }

    if (isTableRow(trimmed) && lines[index + 1] && isTableDivider(lines[index + 1])) {
      closeList();
      const table = renderTable(lines, index);
      html.push(table.html);
      index = table.next;
      continue;
    }

    if (trimmed === "---") {
      closeList();
      html.push("<hr />");
      index += 1;
      continue;
    }

    if (trimmed.startsWith("# ")) {
      closeList();
      html.push(`<h1>${inlineMarkdown(trimmed.slice(2))}</h1>`);
    } else if (trimmed.startsWith("## ")) {
      closeList();
      html.push(`<h2>${inlineMarkdown(trimmed.slice(3))}</h2>`);
    } else if (trimmed.startsWith("### ")) {
      closeList();
      html.push(`<h3>${inlineMarkdown(trimmed.slice(4))}</h3>`);
    } else if (trimmed.startsWith("> ")) {
      closeList();
      html.push(`<blockquote>${inlineMarkdown(trimmed.slice(2))}</blockquote>`);
    } else if (/^\d+\.\s+/.test(trimmed)) {
      if (listType !== "ol") {
        closeList();
        listType = "ol";
        html.push("<ol>");
      }
      html.push(`<li>${inlineMarkdown(trimmed.replace(/^\d+\.\s+/, ""))}</li>`);
    } else if (trimmed.startsWith("- ")) {
      if (listType !== "ul") {
        closeList();
        listType = "ul";
        html.push("<ul>");
      }
      html.push(`<li>${inlineMarkdown(trimmed.slice(2))}</li>`);
    } else {
      closeList();
      html.push(`<p>${inlineMarkdown(trimmed)}</p>`);
    }

    index += 1;
  }

  closeList();
  return html.join("");
};

fetch("assets/market_briefing.md")
  .then((response) => {
    if (!response.ok) {
      throw new Error("Briefing unavailable");
    }
    const lastModified = response.headers.get("last-modified");
    return response.text().then((markdown) => ({ markdown, lastModified }));
  })
  .then(({ markdown, lastModified }) => {
    if (lastModified) {
      const formattedDate = new Date(lastModified).toLocaleString([], {
        year: "numeric",
        month: "long",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
      });
      markdown = markdown.replace("**Last updated:** \n", `**Last updated:** ${formattedDate}\n`);
    }
    output.innerHTML = renderMarkdown(markdown);
  })
  .catch(() => {
    output.innerHTML = "<p>The sample briefing could not be loaded.</p>";
  });
