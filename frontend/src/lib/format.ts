/** Presentation helpers. All numbers come from the API; nothing here invents data. */

const MINUS = "\u2212";

const numberFormat = (digits: number) =>
  new Intl.NumberFormat("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });

export function formatNumber(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "n/a";
  const text = numberFormat(digits).format(Math.abs(value));
  return value < 0 && Number(text.replace(/,/g, "")) !== 0 ? `${MINUS}${text}` : text;
}

export function formatSigned(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "n/a";
  const text = numberFormat(digits).format(Math.abs(value));
  if (Number(text.replace(/,/g, "")) === 0) return text;
  return value < 0 ? `${MINUS}${text}` : `+${text}`;
}

export function formatTonnes(value: number | null | undefined, digits = 0): string {
  return value === null || value === undefined ? "n/a" : `${formatNumber(value, digits)} t`;
}

export function formatSignedTonnes(value: number | null | undefined, digits = 0): string {
  return value === null || value === undefined ? "n/a" : `${formatSigned(value, digits)} t`;
}

export function formatPercent(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "n/a";
  return `${numberFormat(digits).format(value)}%`;
}

export function formatSignedPercent(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "n/a";
  const text = numberFormat(digits).format(Math.abs(value));
  if (Number(text.replace(/,/g, "")) === 0) return `${text}%`;
  return `${value < 0 ? MINUS : "+"}${text}%`;
}

export function formatHours(value: number | null | undefined, digits = 1): string {
  return value === null || value === undefined ? "n/a" : `${numberFormat(digits).format(value)} h`;
}

// Fixed month names: Intl abbreviations vary by ICU version ("Sep" vs "Sept"), and
// dates should read the same in every browser and in tests.
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"] as const;

function dayMonthYear(date: Date): string {
  const day = String(date.getUTCDate()).padStart(2, "0");
  return `${day} ${MONTHS[date.getUTCMonth()]} ${date.getUTCFullYear()}`;
}

/** Format an ISO calendar date (YYYY-MM-DD) without timezone shifts: "30 Sep 2026". */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "n/a";
  const date = new Date(`${iso.slice(0, 10)}T00:00:00Z`);
  return Number.isNaN(date.getTime()) ? iso : dayMonthYear(date);
}

/** Format a YYYY-MM month key: "Sep 2026". */
export function formatMonth(yyyyMm: string): string {
  const [year, month] = yyyyMm.split("-");
  const index = Number(month) - 1;
  if (!year || !MONTHS[index]) return yyyyMm;
  return `${MONTHS[index]} ${year}`;
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "n/a";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return `${dayMonthYear(date)}, ${date.toISOString().slice(11, 16)} UTC`;
}

/** Shift an ISO date by whole days (UTC). */
export function addDays(iso: string, days: number): string {
  const date = new Date(`${iso.slice(0, 10)}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

export function pluralise(count: number, singular: string, plural = `${singular}s`): string {
  return `${formatNumber(count)} ${count === 1 ? singular : plural}`;
}
