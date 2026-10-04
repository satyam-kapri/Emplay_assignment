export type Bid = { id: string; folder: string; files: string[]; indexed_files: number; warnings: string[]; has_extraction: boolean }
export type Citation = { chunk_id: string; file: string; page: number | null; locator: string; quote: string }
export type Evidence = { id: string; bid_id: string; file: string; page: number | null; locator: string; doc_type: string; text: string; score: number; addendum_number: number | null }
export type Answer = { answer: string; sources: Citation[]; notes: string; errors: string[]; warnings: string[]; run_id: string }
export type FieldValue = { value: unknown; sources: Citation[]; confidence: number; notes: string }
export type Extraction = { bid_id: string; fields: Record<string, FieldValue>; status: string; validation: { passed: number; failed: number; not_found: number }; warnings: string[]; errors: unknown[]; addendum_changes: { field: string; old_value: unknown; new_value: unknown; reason: string }[] }
export type IndexReport = { status: string; indexed: string[]; skipped: string[]; errors: unknown[]; warnings: string[] }

export async function request<T>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  let response: Response
  try {
    response = await fetch('/api' + path, { signal, method: body === undefined ? 'GET' : 'POST', headers: body === undefined ? undefined : { 'Content-Type': 'application/json' }, body: body === undefined ? undefined : JSON.stringify(body) })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new Error('Cannot reach the API. Start the Python server on port 8000 and try again.')
  }
  const data = await response.json().catch(() => null)
  if (!response.ok) throw new Error(typeof data?.detail === 'string' ? data.detail : 'Request failed (' + response.status + '). Please try again.')
  if (data === null) throw new Error('The API returned an unreadable response.')
  return data as T
}

export function downloadJson(data: unknown, filename: string) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }))
  const link = document.createElement('a'); link.href = url; link.download = filename; link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
