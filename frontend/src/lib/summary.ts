// The session summary as text to paste and as a CSV file. Built in the browser from
// the facilitator's snapshot; the server never stores it.

import { plural, points } from "./format";
import type { SummaryEntry } from "./types";

function spread(entry: SummaryEntry): string {
  return entry.votes.map((v) => `${v.label}×${v.count}`).join(", ");
}

export function summaryText(slug: string, entries: SummaryEntry[]): string {
  const lines = [`Scrum poker · ${slug} · session summary`, ""];
  for (const e of entries) {
    const result = e.status === "estimated" && e.points !== null ? points(e.points) : "skipped";
    const detail = [
      e.average !== null ? `average ${e.average.toFixed(1)}` : null,
      e.votes.length ? `votes ${spread(e)}` : null,
    ].filter(Boolean);
    lines.push(`${e.key} ${e.summary}: ${result}${detail.length ? ` (${detail.join("; ")})` : ""}`);
  }
  const estimated = entries.filter((e) => e.status === "estimated");
  const total = estimated.reduce((sum, e) => sum + (e.points ?? 0), 0);
  lines.push("", `Total: ${plural(estimated.length, "ticket")} · ${points(total)}`);
  return lines.join("\n");
}

function cell(value: string | number | null): string {
  const text = value === null ? "" : String(value);
  return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

export function summaryCsv(entries: SummaryEntry[]): string {
  const rows = [["key", "summary", "status", "points", "average", "votes"]];
  for (const e of entries) {
    rows.push([
      e.key,
      e.summary,
      e.status,
      e.points === null ? "" : String(e.points),
      e.average === null ? "" : e.average.toFixed(1),
      spread(e),
    ]);
  }
  return rows.map((r) => r.map(cell).join(",")).join("\r\n") + "\r\n";
}

export function downloadCsv(slug: string, entries: SummaryEntry[]): void {
  const blob = new Blob([summaryCsv(entries)], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `scrum-poker-${slug}-${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
