// Display helpers shared by the chat and the session inspector. Pure functions
// only: nothing here touches the API or the DOM.

import type { IdentityField, ModelMode } from './api'

export const MODEL_LABELS: Record<ModelMode, string> = {
  claude: 'Claude',
  openai: 'OpenAI',
  offline: 'Offline rules',
}

/** Every identity field the backend can match on, in display order. */
export const IDENTITY_FIELDS: readonly IdentityField[] = ['full_name', 'dob', 'phone', 'email', 'ssn_last4']

export const FIELD_LABELS: Record<IdentityField, string> = {
  full_name: 'Full name',
  dob: 'Date of birth',
  phone: 'Phone',
  email: 'Email',
  ssn_last4: 'SSN last 4',
}

const MONTHS = [
  'January',
  'February',
  'March',
  'April',
  'May',
  'June',
  'July',
  'August',
  'September',
  'October',
  'November',
  'December',
]

/** 1 -> "January". Falls back to the number for anything out of range. */
export function monthName(month: number): string {
  return MONTHS[month - 1] ?? String(month)
}

/** "denial_question" -> "Denial question". */
export function humanize(value: string): string {
  const spaced = value.replace(/[_-]+/g, ' ').replace(/\s+/g, ' ').trim().toLowerCase()
  return spaced.charAt(0).toUpperCase() + spaced.slice(1)
}

/** ISO timestamp -> local 24-hour "HH:MM", or "" when it can't be parsed. */
export function formatClock(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ''
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  return `${hours}:${minutes}`
}

/**
 * "2026-03-01" -> "Mar 1, 2026". Parsed by hand: `new Date("2026-03-01")` is
 * UTC midnight, which shows as the previous day west of Greenwich.
 */
export function formatBusinessDate(isoDate: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(isoDate)
  if (!match) return isoDate
  const [, year, month, day] = match
  const name = MONTHS[Number(month) - 1]
  if (!name) return isoDate
  return `${name.slice(0, 3)} ${Number(day)}, ${year}`
}
