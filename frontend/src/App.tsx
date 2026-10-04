import { useEffect, useRef, useState, type FormEvent } from 'react'
import { ArrowDownToLine, ArrowRight, ArrowUpRight, BookOpen, Check, ChevronRight, FileText, FolderOpen, Layers, LoaderCircle, MessageSquare, Plus, RefreshCw, Search, SlidersHorizontal, Sparkles, X } from 'lucide-react'
import { request, downloadJson, type Bid, type Evidence, type Citation, type Answer, type Extraction, type IndexReport } from './api'

type Tab = 'search' | 'ask' | 'extract'
type Source = { file: string; page: number | null; locator: string; text: string }
const tabs: { id: Tab; label: string; icon: typeof Search }[] = [
  { id: 'search', label: 'Search documents', icon: Search },
  { id: 'ask', label: 'Ask a question', icon: MessageSquare },
  { id: 'extract', label: 'Bid extraction', icon: Layers },
]
const formatLocation = (page: number | null) => page === null ? 'HTML section' : 'Page ' + page
const display = (value: unknown): string => typeof value === 'string' ? value : value == null ? 'Not found in documents' : JSON.stringify(value)

function Value({ value }: { value: unknown }) {
  if (value == null) return <span className="muted">Not found in documents</span>
  if (Array.isArray(value)) return <ul className="value-list">{value.map((item, i) => <li key={i}><Value value={item} /></li>)}</ul>
  if (typeof value === 'object') return <dl className="nested-values">{Object.entries(value).map(([key, item]) => <div key={key}><dt>{key.replaceAll('_', ' ')}</dt><dd><Value value={item} /></dd></div>)}</dl>
  return <span>{String(value)}</span>
}

export default function App() {
  const [bids, setBids] = useState<Bid[]>([])
  const [scope, setScope] = useState('all')
  const [tab, setTab] = useState<Tab>('search')
  const [online, setOnline] = useState<boolean | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState('')
  const [query, setQuery] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [answerQuery, setAnswerQuery] = useState('')
  const [results, setResults] = useState<Evidence[] | null>(null)
  const [answer, setAnswer] = useState<Answer | null>(null)
  const [extraction, setExtraction] = useState<Extraction | null>(null)
  const [source, setSource] = useState<Source | null>(null)
  const [selectedId, setSelectedId] = useState('')
  const [docType, setDocType] = useState('')
  const [addendum, setAddendum] = useState('')
  const [mode, setMode] = useState('hybrid')
  const [folderOpen, setFolderOpen] = useState(false)
  const [folder, setFolder] = useState('')
  const [notice, setNotice] = useState('')
  const controller = useRef<AbortController | null>(null)
  const modal = useRef<HTMLElement | null>(null)
  const bid = bids.find(item => item.id === scope)
  const totalFiles = bids.reduce((sum, item) => sum + item.files.length, 0)
  const indexed = bids.reduce((sum, item) => sum + item.indexed_files, 0)

  async function refresh(signal?: AbortSignal) {
    try {
      const catalog = await request<Bid[]>('/bids', undefined, signal)
      if (signal?.aborted) return
      setBids(catalog); setOnline(true)
    } catch (err) {
      if (signal?.aborted) return
      setOnline(false); setError(err instanceof Error ? err.message : 'Unable to load bids.')
    }
  }
  useEffect(() => { const abort = new AbortController(); void refresh(abort.signal); return () => abort.abort() }, [])
  useEffect(() => {
    controller.current?.abort(); controller.current = null
    setBusy(''); setResults(null); setAnswer(null); setExtraction(null); setSource(null); setSelectedId(''); setSearchQuery(''); setAnswerQuery(''); setError(''); setNotice('')
    const abort = new AbortController()
    if (bid?.has_extraction) {
      void request<Extraction>('/bids/' + encodeURIComponent(bid.id) + '/extraction', undefined, abort.signal)
        .then(data => { if (!abort.signal.aborted) setExtraction(data) })
        .catch(err => { if (!abort.signal.aborted) setError(err.message) })
    }
    return () => abort.abort()
  }, [scope, bid?.has_extraction])
  useEffect(() => () => controller.current?.abort(), [])
  useEffect(() => {
    if (!folderOpen) return
    const previous = document.activeElement as HTMLElement | null
    function key(event: KeyboardEvent) {
      if (event.key === 'Escape') setFolderOpen(false)
      if (event.key !== 'Tab') return
      const elements = modal.current?.querySelectorAll<HTMLElement>('button:not(:disabled),input:not(:disabled)')
      if (!elements?.length) return
      const first = elements[0], last = elements[elements.length - 1]
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus() }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
    }
    document.addEventListener('keydown', key)
    return () => { document.removeEventListener('keydown', key); previous?.focus() }
  }, [folderOpen])

  async function operate(label: string, task: (signal: AbortSignal) => Promise<void>) {
    controller.current?.abort()
    const abort = new AbortController(); controller.current = abort
    setBusy(label); setError(''); setNotice('')
    try { await task(abort.signal) }
    catch (err) { if (!abort.signal.aborted) setError(err instanceof Error ? err.message : 'Something went wrong.') }
    finally { if (controller.current === abort) { controller.current = null; setBusy('') } }
  }
  function changeTab(next: Tab) {
    controller.current?.abort(); controller.current = null; setBusy(''); setError(''); setSource(null); setSelectedId(''); setTab(next)
  }
  function viewCitation(citation: Citation) {
    setSource({ file: citation.file, page: citation.page, locator: citation.locator, text: citation.quote })
    setSelectedId(citation.chunk_id)
  }
  function citations(items: Citation[]) {
    return <div className="citations">{items.map((item, i) => <button type="button" key={item.chunk_id + i} onClick={() => viewCitation(item)}><FileText size={13} /> Source {String(i + 1).padStart(2, '0')} <span>· {formatLocation(item.page)}</span><ArrowUpRight size={12} /></button>)}</div>
  }
  async function submit(event?: FormEvent, suggestion?: string) {
    event?.preventDefault()
    const text = (suggestion ?? query).trim()
    if (!text) return
    setQuery(text); setSource(null); setSelectedId('')
    await operate(tab === 'ask' ? 'Reading evidence and preparing an answer' : 'Searching your documents', async signal => {
      if (tab === 'ask') {
        const data = await request<Answer>('/ask', { question: text, bid_ids: scope === 'all' ? [] : [scope] }, signal)
        if (!signal.aborted) { setAnswer(data); setAnswerQuery(text) }
      } else {
        const params = new URLSearchParams({ q: text, mode, top_k: '8' })
        if (scope !== 'all') params.set('bid_id', scope)
        if (docType) params.set('doc_type', docType)
        if (docType === 'addendum' && addendum) params.set('addendum_number', addendum)
        const data = await request<Evidence[]>('/search?' + params, undefined, signal)
        if (!signal.aborted) { setResults(data); setSearchQuery(text) }
      }
    })
  }
  async function indexFolder(path: string) {
    await operate('Indexing the bid documents', async signal => {
      const report = await request<IndexReport>('/index', { folder: path }, signal)
      if (signal.aborted) return
      setFolderOpen(false)
      await refresh(signal)
      if (!signal.aborted) {
        setNotice(report.indexed.length + ' files indexed · ' + report.skipped.length + ' unchanged' + (report.warnings.length ? ' · ' + report.warnings.length + ' warnings' : ''))
        if (report.errors.length) setError('Some files could not be indexed. ' + report.errors.map(display).join(' '))
      }
    })
  }
  async function extract() {
    if (!bid) return
    await operate('Extracting and validating the bid fields', async signal => {
      const data = await request<Extraction>('/extract', { folder: bid.folder }, signal)
      if (!signal.aborted) { setExtraction(data); await refresh(signal) }
    })
  }

  return <div className="app-shell">
    <aside className="sidebar">
      <a href="#" className="brand" aria-label="RFP Intelligence home" onClick={event => { event.preventDefault(); setScope('all'); changeTab('search') }}>
        <span className="brand-mark"><Layers size={22} strokeWidth={1.6} /></span><span>RFP<span className="brand-secondary">Intelligence</span></span>
      </a>
      <div className="workspace-label">WORKSPACE <span>LOCAL</span></div>
      <button className={'nav-item ' + (scope === 'all' ? 'active' : '')} onClick={() => setScope('all')}><BookOpen size={17} />All bids<span className="nav-count">{bids.length}</span></button>
      <div className="sidebar-section"><span>BID LIBRARY</span><button aria-label="Refresh bid library" onClick={() => void refresh()}><RefreshCw size={14} /></button></div>
      <div className="bid-library">{bids.map(item => <button className={'bid-item ' + (scope === item.id ? 'selected' : '')} key={item.id} onClick={() => setScope(item.id)}>
        <span className="bid-icon"><FolderOpen size={19} strokeWidth={1.5} /></span>
        <span className="bid-meta"><strong>{item.id}</strong><small>{item.files.length} documents</small></span>
        <span title={item.indexed_files ? 'Indexed' : 'Not indexed'} className={'status-dot ' + (item.indexed_files ? 'ready' : '')} />
      </button>)}</div>
      {!bids.length && <p className="sidebar-empty">{online === false ? 'Connect the API to see your bids.' : online === null ? 'Loading your library…' : 'No bid folders found.'}</p>}
      <button className="add-folder" onClick={() => setFolderOpen(true)}><Plus size={16} /> Index a folder</button>
      <div className="sidebar-bottom"><span className="tiny-symbol"><FileText size={16} /></span><div><strong>Evidence comes first.</strong><p>Every answer starts with a source.</p></div></div>
      <div className="connection"><span className={'status-dot ' + (online ? 'ready' : '')} />{online === null ? 'Connecting to API' : online ? 'API connected' : 'API unavailable'}<button onClick={() => void refresh()} aria-label="Reconnect to API"><RefreshCw size={13} /></button></div>
    </aside>

    <main className="main">
      <header className="topbar"><div className="breadcrumb">Workspace <ChevronRight size={12} /><strong>{scope === 'all' ? 'All bids' : scope}</strong></div><span className="top-note"><span className="status-dot ready" />Local workspace</span></header>
      <div className="workspace">
        <div className="workspace-heading"><div><div className="eyebrow">BID INTELLIGENCE</div><h1>{scope === 'all' ? 'Bid workspace' : scope + ' workspace'}</h1><p>Search requirements, review changes, and extract cited bid records.</p></div><div className="collection-summary"><strong>{scope === 'all' ? totalFiles : bid?.files.length ?? 0}</strong><span>documents<br />in this collection</span></div></div>
        <div className="tabbar" role="tablist" aria-label="Workspace mode">{tabs.map(item => <button role="tab" aria-selected={tab === item.id} id={'tab-' + item.id} aria-controls="workspace-panel" tabIndex={tab === item.id ? 0 : -1} onKeyDown={event => { const index = tabs.findIndex(entry => entry.id === item.id); const next = event.key === 'ArrowRight' ? (index + 1) % tabs.length : event.key === 'ArrowLeft' ? (index + tabs.length - 1) % tabs.length : event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : -1; if (next >= 0) { event.preventDefault(); changeTab(tabs[next].id); document.getElementById('tab-' + tabs[next].id)?.focus() } }} key={item.id} className={tab === item.id ? 'current' : ''} onClick={() => changeTab(item.id)}><item.icon size={16} />{item.label}</button>)}<span className="tab-end">{bid ? bid.indexed_files + '/' + bid.files.length + ' indexed' : indexed + ' indexed'}</span></div>

        {error && <div className="alert error" role="alert"><span>{error}</span><button aria-label="Dismiss error" onClick={() => setError('')}><X size={16} /></button></div>}
        {notice && <div className="alert success" role="status"><Check size={16} /><span>{notice}</span></div>}
        {busy && <div className="operation" role="status"><LoaderCircle className="spin" size={17} /><span>{busy}…</span><button onClick={() => { controller.current?.abort(); controller.current = null; setBusy(''); setNotice('Stopped waiting. The server may still finish the operation.') }}>Stop waiting</button></div>}

        <section id="workspace-panel" role="tabpanel" aria-labelledby={'tab-' + tab} className="workspace-panel">
          {tab !== 'extract' ? <>
            <form className="query-form" onSubmit={event => void submit(event)}>
              <label className="sr-only" htmlFor="query">{tab === 'ask' ? 'Question about bids' : 'Search bid documents'}</label>
              <div className="query-input">{tab === 'ask' ? <Sparkles size={22} strokeWidth={1.4} /> : <Search size={23} strokeWidth={1.4} />}<input id="query" value={query} onChange={event => setQuery(event.target.value)} placeholder={tab === 'ask' ? 'Ask a question about your bids…' : 'Search requirements, deadlines, or part numbers…'} /><button disabled={!!busy || !query.trim()} className="primary query-submit" type="submit">{tab === 'ask' ? 'Ask' : 'Search'}<ArrowRight size={17} /></button></div>
              <div className="filterbar"><SlidersHorizontal size={14} /><label>Scope<select aria-label="Bid scope" value={scope} onChange={event => setScope(event.target.value)}><option value="all">All bids</option>{bids.map(item => <option key={item.id} value={item.id}>{item.id}</option>)}</select></label>
                {tab === 'search' && <><span className="filter-divider" /><label>Document<select aria-label="Document type" value={docType} onChange={event => setDocType(event.target.value)}><option value="">All documents</option><option value="rfp">RFP</option><option value="addendum">Addendum</option><option value="specs">Specifications</option><option value="affidavit">Affidavit</option><option value="bid_page">Bid page</option></select></label>{docType === 'addendum' && <label>No.<input aria-label="Addendum number" type="number" min="1" value={addendum} onChange={event => setAddendum(event.target.value)} placeholder="Any" className="number-filter" /></label>}<label className="method">Method<select aria-label="Search method" value={mode} onChange={event => setMode(event.target.value)}><option value="hybrid">Hybrid</option><option value="dense">Semantic</option><option value="rerank">Reranked</option></select></label></>}
                {tab === 'ask' && <span className="generation-note">Answers include source citations</span>}
              </div>
            </form>
            {((tab === 'search' && results === null) || (tab === 'ask' && answer === null)) && <div className="empty-workspace">
              <div className="document-illustration" aria-hidden="true"><div className="paper back" /><div className="paper front"><span /><span /><span /><div className="paper-accent"><Search size={23} strokeWidth={1.4} /></div></div><div className="illustration-cross">+</div></div>
              <div className="eyebrow">{tab === 'ask' ? 'GROUNDED IN YOUR DOCUMENTS' : 'A CLEARER VIEW OF THE DETAILS'}</div>
              <h2>{tab === 'ask' ? 'Let the evidence answer.' : 'Start with a question.'}</h2>
              <p>{tab === 'ask' ? 'Ask about requirements, changes, or differences between bids.' : 'Search across your documents, then inspect the passages that matter.'}</p>
              <div className="suggestions">{['What is the final submission deadline?', 'Which documents must bidders provide?', 'What changed in the addendums?'].map(text => <button key={text} disabled={!!busy} onClick={() => void submit(undefined, text)}>{text}<ArrowUpRight size={14} /></button>)}</div>
              {!indexed && online && <p className="setup-hint">Select a bid and index its documents to get started.</p>}
            </div>}
            {tab === 'search' && results !== null && <div className={'results-layout ' + (source ? 'inspecting' : '')}><div className="result-list"><div className="section-meta"><span>{results.length} passages</span><span>FOR “{searchQuery}”</span></div>
              {!results.length && <div className="no-results"><Search size={28} /><h2>No passages found</h2><p>Try broader wording, remove a filter, or check that the bid is indexed.</p>{bid && <button className="secondary" onClick={() => void indexFolder(bid.folder)} disabled={!!busy}>Index {bid.id}</button>}</div>}
              {results.map((item, i) => <button className={'result-row ' + (selectedId === item.id ? 'chosen' : '')} key={item.id} onClick={() => { setSelectedId(item.id); setSource({ file: item.file, page: item.page, locator: item.locator, text: item.text }) }}><div className="result-title"><span className="result-number">{String(i + 1).padStart(2, '0')}</span><span className="source-type">{item.doc_type.replaceAll('_', ' ')}</span><span className="result-bid">{item.bid_id}</span><ArrowUpRight size={15} /></div><h3>{item.file}</h3><p>{item.text}</p><div className="result-footer"><FileText size={12} />{formatLocation(item.page)}<span>Inspect evidence <ArrowRight size={12} /></span></div></button>)}
            </div>{source && <Inspector source={source} close={() => setSource(null)} />}</div>}
            {tab === 'ask' && answer && <div className={'results-layout ' + (source ? 'inspecting' : '')}><article className="answer"><div className="section-meta"><span><Sparkles size={14} />Cited answer</span><button onClick={() => downloadJson(answer, 'bid-answer.json')}><ArrowDownToLine size={14} />Export</button></div><h2>{answerQuery}</h2><p className="answer-text">{answer.answer}</p>{answer.notes && <p className="answer-notes">{answer.notes}</p>}{citations(answer.sources)}{answer.errors.length > 0 && <div className="inline-warning">{answer.errors.join(' ')}</div>}{answer.warnings.length > 0 && <Warnings warnings={answer.warnings} />}</article>{source && <Inspector source={source} close={() => setSource(null)} />}</div>}
          </> : <div className={'results-layout ' + (source ? 'inspecting' : '')}><div className="extraction-workspace"><div className="extraction-heading"><div><h2>Structured bid record</h2><p>20 fields, supported by source evidence.</p></div><div className="action-group">{extraction && <button className="secondary" onClick={() => downloadJson(extraction, extraction.bid_id + '.json')}><ArrowDownToLine size={15} />Export JSON</button>}<button className="primary" disabled={!bid || !!busy} onClick={() => void extract()}><Sparkles size={15} />{extraction ? 'Extract again' : 'Extract bid'}</button></div></div>
            {!extraction && <div className="extraction-empty"><Layers size={36} strokeWidth={1.2} /><h2>{bid ? 'Ready to review ' + bid.id : 'Choose one bid to extract'}</h2><p>{bid ? 'Run extraction to review deadlines, products, obligations, and source citations. A configured LLM is required.' : 'Select a bid from the library. Each bid gets its own structured record.'}</p></div>}
            {extraction && <><div className="validation-strip"><span className="validation-status">{extraction.status}</span><span><strong>{extraction.validation.passed}</strong> validated</span><span><strong>{extraction.validation.not_found}</strong> not found</span><span><strong>{extraction.validation.failed}</strong> failed</span></div><div className="field-list">{Object.entries(extraction.fields).map(([name, field]) => <details key={name} className="field-row"><summary><ChevronRight size={14} /><strong>{name}</strong><span className={'field-preview ' + (field.value == null ? 'muted' : '')}>{display(field.value)}</span><span className="field-source-count">{field.sources.length ? field.sources.length + ' sources' : 'No source'}</span></summary><div className="field-detail"><Value value={field.value} /><p className="answer-notes">{field.notes}</p>{field.value !== null && <small className="muted">Evidence score: {Math.round(field.confidence * 100)}% · not a probability</small>}{citations(field.sources)}</div></details>)}</div>{extraction.addendum_changes.length > 0 && <div className="changes"><h3>Addendum changes</h3>{extraction.addendum_changes.map((change, i) => <div key={i}><strong>{change.field}</strong><p><s>{display(change.old_value)}</s> → {display(change.new_value)}</p><p className="muted">{change.reason}</p></div>)}</div>}{extraction.errors.length > 0 && <div className="inline-warning">{extraction.errors.map(display).join(' ')}</div>}<Warnings warnings={extraction.warnings} /></>}
          </div>{source && <Inspector source={source} close={() => setSource(null)} />}</div>}
        </section>
        <footer className="workspace-footer"><span><FileText size={13} />Source-backed by design</span>{bid && <button disabled={!!busy} onClick={() => void indexFolder(bid.folder)}><RefreshCw size={13} />Update {bid.id} index</button>}<span>RFP INTELLIGENCE / 01</span></footer>
        {bid && <Warnings warnings={bid.warnings} />}
      </div>
    </main>

    {folderOpen && <div className="modal-backdrop" onClick={() => setFolderOpen(false)}><section ref={modal} className="modal" role="dialog" aria-modal="true" aria-labelledby="folder-title" onClick={event => event.stopPropagation()}><button className="modal-close" aria-label="Close folder dialog" onClick={() => setFolderOpen(false)}><X size={18} /></button><FolderOpen size={28} /><h2 id="folder-title">Index a bid folder</h2><p>Use a folder inside the server’s configured data root, containing PDF or HTML documents.</p><form onSubmit={event => { event.preventDefault(); void indexFolder(folder.trim()) }}><label htmlFor="folder">Folder path</label><input id="folder" autoFocus value={folder} onChange={event => setFolder(event.target.value)} placeholder="./MyBid" /><button className="primary" disabled={!folder.trim() || !!busy}>Index documents<ArrowRight size={16} /></button></form></section></div>}
  </div>
}

function Inspector({ source, close }: { source: Source; close: () => void }) {
  return <aside className="inspector" aria-label="Source evidence"><div className="inspector-label"><span><FileText size={14} />SOURCE EVIDENCE</span><button aria-label="Close evidence inspector" onClick={close}><X size={16} /></button></div><h3>{source.file}</h3><div className="source-location">{formatLocation(source.page)}<span>Original passage</span></div><blockquote>{source.text}</blockquote><details className="locator"><summary>Source location</summary><p>{source.locator}</p></details></aside>
}

function Warnings({ warnings }: { warnings: string[] }) {
  if (!warnings.length) return null
  return <details className="warnings"><summary>{warnings.length} document warning{warnings.length === 1 ? '' : 's'} · some content may be unavailable</summary><ul>{warnings.map((warning, i) => <li key={i}>{warning}</li>)}</ul></details>
}


