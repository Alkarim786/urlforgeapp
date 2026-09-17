import React, { useState, useEffect } from 'react';
import {
  Activity,
  Terminal,
  CheckCircle2,
  ExternalLink,
  RefreshCw,
  Cpu,
  Layers,
  BookOpen,
  ArrowRight,
  ShieldAlert,
  Server,
  Link as LinkIcon,
  Copy,
  Check,
  AlertTriangle,
  Info
} from 'lucide-react';

interface HealthResponse {
  status: string;
  service: string;
  environment: string;
  timestamp: string;
  version: string;
  components?: {
    database: string;
    cache: string;
  };
}

interface EndpointResult {
  endpoint: string;
  method?: string;
  statusCode: number | null;
  latencyMs: number | null;
  data: any;
  error?: string;
}

interface CreatedURL {
  short_code: string;
  short_url: string;
  original_url: string;
  created_at: string;
}

export default function App() {
  const [healthData, setHealthData] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [latency, setLatency] = useState<number | null>(null);
  const [selectedEndpoint, setSelectedEndpoint] = useState<string>('create');
  const [endpointResult, setEndpointResult] = useState<EndpointResult | null>(null);
  const [activeTab, setActiveTab] = useState<'console' | 'architecture' | 'roadmap' | 'interview'>('console');
  const [openInterviewIndex, setOpenInterviewIndex] = useState<number | null>(0);

  // URL Shortener Interactive Form State
  const [inputUrl, setInputUrl] = useState<string>('https://fastapi.tiangolo.com/tutorial/bigger-applications/');
  const [customAlias, setCustomAlias] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [lastCreated, setLastCreated] = useState<CreatedURL | null>(null);
  const [copied, setCopied] = useState<boolean>(false);
  const [queryCode, setQueryCode] = useState<string>('');

  const fetchHealth = async () => {
    setLoading(true);
    const start = performance.now();
    try {
      const res = await fetch('/health');
      const time = Math.round(performance.now() - start);
      if (res.ok) {
        const json = await res.json();
        setHealthData(json);
        setLatency(time);
      } else {
        setHealthData(null);
      }
    } catch {
      setHealthData(null);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateURL = async (urlToCreate?: string, aliasToCreate?: string) => {
    const targetUrl = urlToCreate !== undefined ? urlToCreate : inputUrl;
    const targetAlias = aliasToCreate !== undefined ? aliasToCreate : customAlias;

    setIsSubmitting(true);
    setSelectedEndpoint('create');
    const start = performance.now();

    try {
      const payload: { url: string; custom_alias?: string } = { url: targetUrl };
      if (targetAlias && targetAlias.trim()) {
        payload.custom_alias = targetAlias.trim();
      }

      const res = await fetch('/api/v1/urls', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const time = Math.round(performance.now() - start);
      const json = await res.json();

      setEndpointResult({
        endpoint: '/api/v1/urls',
        method: 'POST',
        statusCode: res.status,
        latencyMs: time,
        data: json,
      });

      if (res.status === 201) {
        setLastCreated(json);
        setQueryCode(json.short_code);
      }
    } catch (err: any) {
      setEndpointResult({
        endpoint: '/api/v1/urls',
        method: 'POST',
        statusCode: 500,
        latencyMs: null,
        data: null,
        error: err.message || 'Failed to submit',
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleGetMetadata = async (codeToQuery?: string) => {
    const code = codeToQuery || queryCode || (lastCreated ? lastCreated.short_code : 'UOEnjbR');
    setSelectedEndpoint(`get_meta_${code}`);
    const start = performance.now();

    try {
      const res = await fetch(`/api/v1/urls/${code}`);
      const time = Math.round(performance.now() - start);
      const json = await res.json();

      setEndpointResult({
        endpoint: `/api/v1/urls/${code}`,
        method: 'GET',
        statusCode: res.status,
        latencyMs: time,
        data: json,
      });
    } catch (err: any) {
      setEndpointResult({
        endpoint: `/api/v1/urls/${code}`,
        method: 'GET',
        statusCode: 500,
        latencyMs: null,
        data: null,
        error: err.message || 'Failed to fetch metadata',
      });
    }
  };

  const testEndpoint = async (path: string) => {
    setSelectedEndpoint(path);
    const start = performance.now();
    try {
      const res = await fetch(path);
      const time = Math.round(performance.now() - start);
      const json = await res.json();
      setEndpointResult({
        endpoint: path,
        method: 'GET',
        statusCode: res.status,
        latencyMs: time,
        data: json,
      });
    } catch (err: any) {
      setEndpointResult({
        endpoint: path,
        method: 'GET',
        statusCode: 500,
        latencyMs: null,
        data: null,
        error: err.message || 'Failed to fetch',
      });
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  useEffect(() => {
    fetchHealth();
    // Test initial URL creation on boot to demonstrate live functionality
    handleCreateURL('https://fastapi.tiangolo.com', 'fastapi-link');
  }, []);

  const phases = [
    { num: 1, name: "FastAPI Core Skeleton & Health", status: "completed", desc: "Minimal ASGI app, GET /, GET /health, Pydantic settings, Pytest." },
    { num: 2, name: "URL Creation (POST /api/v1/urls)", status: "completed", desc: "Base62 token generator, Pydantic URL validation, collision retry loop, metadata endpoint." },
    { num: 3, name: "PostgreSQL & SQLAlchemy 2.x", status: "completed", desc: "Async engine (asyncpg), connection pool, Alembic migrations, database UNIQUE constraints & indexes." },
    { num: 4, name: "HTTP Redirect (GET /{short_code})", status: "current", desc: "HTTP 307 vs 301/302 semantics, path routing, lookup performance." },
    { num: 5, name: "Short Code Generation & Base62", status: "completed", desc: "Bi-directional integer conversion, collision probability analysis, secure random tokens." },
    { num: 6, name: "Redis Caching (Cache-Aside)", status: "completed", desc: "Cache get/set/delete, 24h TTL, hit/miss metrics, graceful fallback on outage." },
    { num: 7, name: "Analytics & Click Tracking", status: "upcoming", desc: "Click counts, timestamps, user-agent parsing, referrer, privacy-first." },
    { num: 8, name: "Redis-Backed Rate Limiting", status: "upcoming", desc: "Token bucket/sliding window, concurrency control, 429 Too Many Requests." },
    { num: 9, name: "Idempotency (Idempotency-Key)", status: "upcoming", desc: "Prevent duplicate creation on network retries, key replay & caching." },
    { num: 10, name: "Comprehensive Test Suite", status: "completed", desc: "Unit, integration, and concurrency race-condition tests with Pytest (17 passing)." },
    { num: 11, name: "Docker & Compose", status: "upcoming", desc: "Multi-stage Dockerfile, docker-compose.yml (FastAPI, Postgres, Redis)." },
    { num: 12, name: "Observability & Metrics", status: "upcoming", desc: "Structured JSON logging, correlation IDs, Prometheus metrics exporter." },
    { num: 13, name: "Performance Benchmarks", status: "upcoming", desc: "Locust load testing, P50/P95/P99 latency, cache hit ratio comparisons." },
    { num: 14, name: "Chaos & Failure Testing", status: "upcoming", desc: "Simulated Redis outage, DB connection drop, graceful degradation." },
    { num: 15, name: "System Design & Capacity Planning", status: "upcoming", desc: "100M URLs/month math, sharding, replication, interview guide." },
  ];

  const interviewQuestions = [
    {
      q: "Why use asyncpg and SQLAlchemy 2.0 AsyncEngine instead of synchronous psycopg2?",
      short: "asyncpg is fully non-blocking and utilizes binary protocol encoding, handling tens of thousands of concurrent I/O requests per worker without blocking Python's event loop.",
      deep: "Synchronous drivers like psycopg2 block the entire OS thread during socket I/O with PostgreSQL. In high-concurrency URL redirect engines handling 5,000+ requests per second, thread context switching causes catastrophic latency spikes and thread pool starvation. asyncpg integrates natively with asyncio, streaming binary protocol packets directly. Paired with SQLAlchemy 2.0 AsyncSession and connection pooling, worker nodes sustain high concurrency on modest CPU footprints.",
      forge: "In `app/database.py`, URLForge uses `create_async_engine('postgresql+asyncpg://...')` with `pool_pre_ping=True`, configured connection pool size, and automated transaction rollback on exceptions."
    },
    {
      q: "How does the Cache-Aside pattern work in URLForge and how does it protect the database?",
      short: "Reads query Redis first; on cache hit, the response returns in <1ms without touching PostgreSQL. On cache miss, it reads PostgreSQL, writes to Redis, and returns.",
      deep: "In URL shorteners, traffic is heavily read-dominant (often 100:1 read-to-write ratio) with a Pareto distribution where the top 20% of active links generate 80% of click traffic. Without caching, PostgreSQL would be overwhelmed by repetitive index lookups. By setting a 24-hour TTL on cached short codes in Redis, 99% of hot redirects bypass the database entirely. If Redis experiences a transient failure, URLForge's resilient try/except fallback seamlessly queries PostgreSQL without dropping user traffic.",
      forge: "In `app/services/url_service.py`, `get_destination_url` queries `cache.get(f'url:{short_code}')`. If missed, it queries `URLModel` from PostgreSQL and populates Redis via `cache.set(...)`."
    },
    {
      q: "Why use Base62 instead of Base64 or MD5 hashing for URL short codes?",
      short: "Base62 uses [0-9a-zA-Z] which is 100% URL-safe without escaping characters like '+' and '/' in Base64, and provides much higher density than hex-encoded MD5.",
      deep: "Base64 includes '+' and '/' which are reserved URL delimiter characters and cause routing collisions unless percent-encoded (e.g. %2B). Base62 consists strictly of 10 digits, 26 lowercase, and 26 uppercase alphanumeric characters. A 7-character Base62 string yields 62^7 = 3.52 Trillion unique codes. MD5 outputs hexadecimal (16 characters per byte), meaning a 7-character hex hash yields only 16^7 = 268 Million codes—far too low for global scale.",
      forge: "In URLForge `app/utils/short_code.py`, `generate_random_short_code(7)` draws from the 62-symbol alphabet using cryptographically secure `secrets.choice` to prevent link-harvesting attacks."
    },
    {
      q: "Why must we use HTTP 201 Created and the Location header on POST /api/v1/urls?",
      short: "REST specifications (RFC 9110) mandate HTTP 201 when a new resource is allocated, and the Location header specifies the canonical URI where that resource can be accessed.",
      deep: "Returning HTTP 200 OK for a creation request is a REST anti-pattern because HTTP 200 indicates generic success, whereas HTTP 201 informs HTTP clients, proxies, and API gateways that an identifiable resource was minted. The `Location` header enables automated clients and test runners to follow or cache the created resource URI without parsing JSON bodies.",
      forge: "In `app/routes/urls.py`, `response.headers['Location'] = result.short_url` is set, and the endpoint explicitly defines `status_code=status.HTTP_201_CREATED`."
    },
    {
      q: "What is the Birthday Paradox, and how does it affect random short code collision probability?",
      short: "Even with trillions of possible codes, collisions begin occurring far sooner than when the keyspace is full, scaling with the square root of the keyspace size (O(sqrt(N))).",
      deep: "With N = 62^7 = 3.52 Trillion, the 50% collision threshold occurs around sqrt(3.52 * 10^12) ~ 1.87 Million generated URLs. This is why a production shortener cannot rely purely on random generation without either: 1) Counter-based Base62 conversion (guaranteed unique via DB sequences), or 2) An automated collision detection and retry loop backed by a DB unique constraint.",
      forge: "In `app/services/url_service.py`, URLForge implements a retry loop bounded by `MAX_COLLISION_RETRIES`. In Phase 3, this is coupled with PostgreSQL's `UNIQUE` index constraint."
    },
    {
      q: "Why is Pydantic validation crucial for preventing SSRF and XSS in URL shorteners?",
      short: "Allowing protocols like 'javascript:' causes Cross-Site Scripting (XSS), and internal schemes like 'file://' or unvalidated internal IPs can enable Server-Side Request Forgery (SSRF).",
      deep: "If an attacker shortens `javascript:alert(document.cookie)` and an application redirects or renders it in an anchor tag without sanitization, malicious code runs in the user's browser session. By restricting `url` via Pydantic validator to strictly `http` and `https` schemes and enforcing length limits (max 2048 chars), URLForge blocks script injections and buffer attacks at the door.",
      forge: "In `app/schemas.py`, `URLCreateRequest.validate_url_scheme` strictly enforces scheme matching `http` or `https` and rejects arbitrary payloads with HTTP 422."
    }
  ];

  return (
    <div id="urlforge-root" className="min-h-screen bg-slate-950 text-slate-100 font-sans flex flex-col">
      {/* Top Navigation Bar */}
      <header id="main-header" className="border-b border-slate-800 bg-slate-900/80 backdrop-blur sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-lg bg-indigo-600 flex items-center justify-center font-bold text-white shadow-md shadow-indigo-500/20">
              <Server className="w-5 h-5 text-white" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-bold text-lg tracking-tight text-white">URLForge</span>
                <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-950 text-emerald-300 font-medium border border-emerald-800">
                  Phase 3 & 6 Active
                </span>
              </div>
              <p className="text-xs text-slate-400">PostgreSQL 15 & Redis 7 Subsystems Online</p>
            </div>
          </div>

          <div className="flex items-center space-x-2 sm:space-x-3">
            {/* PostgreSQL Indicator */}
            <div className="hidden sm:flex items-center space-x-1.5 px-2.5 py-1 rounded-full bg-slate-800/80 border border-slate-700/60 text-xs">
              <span className={`w-2 h-2 rounded-full ${healthData?.components?.database === 'connected' ? 'bg-emerald-400' : 'bg-rose-500'}`} />
              <span className="text-slate-300 font-mono text-[11px]">PostgreSQL 15</span>
            </div>

            {/* Redis Indicator */}
            <div className="hidden sm:flex items-center space-x-1.5 px-2.5 py-1 rounded-full bg-slate-800/80 border border-slate-700/60 text-xs">
              <span className={`w-2 h-2 rounded-full ${healthData?.components?.cache === 'connected' ? 'bg-red-400' : 'bg-rose-500'}`} />
              <span className="text-slate-300 font-mono text-[11px]">Redis 7</span>
            </div>

            <div className="flex items-center space-x-2 px-3 py-1.5 rounded-full bg-slate-800/80 border border-slate-700/60 text-xs">
              <span className={`w-2 h-2 rounded-full ${healthData ? 'bg-emerald-400 animate-pulse' : 'bg-rose-500'}`} />
              <span className="font-medium text-slate-300">
                {loading ? 'Probing...' : healthData ? 'Backend Online' : 'Connecting...'}
              </span>
              {latency !== null && (
                <span className="text-slate-500 font-mono">({latency}ms)</span>
              )}
            </div>

            <button
              id="refresh-health-btn"
              onClick={fetchHealth}
              disabled={loading}
              className="p-1.5 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg transition"
              title="Refresh Health Probe"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>
      </header>

      {/* Navigation Sub-Tabs */}
      <nav id="subnav-tabs" className="bg-slate-900 border-b border-slate-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 flex space-x-1 sm:space-x-4">
          <button
            id="tab-console-btn"
            onClick={() => setActiveTab('console')}
            className={`py-3 px-3 sm:px-4 text-sm font-medium border-b-2 flex items-center space-x-2 transition ${
              activeTab === 'console'
                ? 'border-indigo-500 text-indigo-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Terminal className="w-4 h-4" />
            <span>Live Console & URL Creator</span>
          </button>

          <button
            id="tab-arch-btn"
            onClick={() => setActiveTab('architecture')}
            className={`py-3 px-3 sm:px-4 text-sm font-medium border-b-2 flex items-center space-x-2 transition ${
              activeTab === 'architecture'
                ? 'border-indigo-500 text-indigo-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Layers className="w-4 h-4" />
            <span>Architecture & Design</span>
          </button>

          <button
            id="tab-roadmap-btn"
            onClick={() => setActiveTab('roadmap')}
            className={`py-3 px-3 sm:px-4 text-sm font-medium border-b-2 flex items-center space-x-2 transition ${
              activeTab === 'roadmap'
                ? 'border-indigo-500 text-indigo-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Activity className="w-4 h-4" />
            <span>Development Roadmap (15 Phases)</span>
          </button>

          <button
            id="tab-interview-btn"
            onClick={() => setActiveTab('interview')}
            className={`py-3 px-3 sm:px-4 text-sm font-medium border-b-2 flex items-center space-x-2 transition ${
              activeTab === 'interview'
                ? 'border-indigo-500 text-indigo-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <BookOpen className="w-4 h-4" />
            <span>CS Interview Deep-Dives</span>
          </button>
        </div>
      </nav>

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 py-8">
        {/* Tab 1: Live Console & API Probes */}
        {activeTab === 'console' && (
          <div className="space-y-6">
            {/* Interactive URL Shortener Workbench */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 relative overflow-hidden">
              <div className="absolute top-0 right-0 w-64 h-64 bg-indigo-500/5 rounded-full blur-3xl -mr-20 -mt-20 pointer-events-none" />
              
              <div className="max-w-3xl">
                <div className="flex items-center space-x-2">
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                    Phase 2 Live API
                  </span>
                  <span className="text-xs text-slate-400">POST /api/v1/urls & Base62 Generation</span>
                </div>
                <h1 className="text-2xl font-bold text-white mt-1">URL Shortener Engine</h1>
                <p className="text-sm text-slate-300 mt-1">
                  Test URL creation with Pydantic validation. The service generates a 7-character Base62 code,
                  checks collision avoidance, and returns an HTTP 201 Created with Location header.
                </p>

                {/* URL Shortening Input Form */}
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    handleCreateURL();
                  }}
                  className="mt-6 space-y-4"
                >
                  <div>
                    <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                      Destination URL (HTTP or HTTPS)
                    </label>
                    <div className="relative">
                      <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-500">
                        <LinkIcon className="w-4 h-4" />
                      </div>
                      <input
                        type="text"
                        value={inputUrl}
                        onChange={(e) => setInputUrl(e.target.value)}
                        placeholder="https://example.com/very/long/path/to/resource"
                        className="w-full pl-10 pr-4 py-2.5 bg-slate-950 border border-slate-700 rounded-lg text-sm text-white font-mono placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <div className="sm:col-span-2">
                      <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                        Custom Alias <span className="text-slate-500 font-normal">(Optional, 4-16 chars)</span>
                      </label>
                      <input
                        type="text"
                        value={customAlias}
                        onChange={(e) => setCustomAlias(e.target.value)}
                        placeholder="e.g. docs-link"
                        className="w-full px-3.5 py-2.5 bg-slate-950 border border-slate-700 rounded-lg text-sm text-white font-mono placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition"
                      />
                    </div>

                    <div className="flex items-end">
                      <button
                        type="submit"
                        disabled={isSubmitting || !inputUrl.trim()}
                        className="w-full py-2.5 px-4 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-medium text-sm rounded-lg transition shadow-sm flex items-center justify-center space-x-2"
                      >
                        {isSubmitting ? (
                          <RefreshCw className="w-4 h-4 animate-spin" />
                        ) : (
                          <>
                            <span>Shorten URL</span>
                            <ArrowRight className="w-4 h-4" />
                          </>
                        )}
                      </button>
                    </div>
                  </div>
                </form>

                {/* Pre-canned Quick Test Buttons */}
                <div className="mt-4 pt-4 border-t border-slate-800/80 flex flex-wrap items-center gap-2">
                  <span className="text-xs text-slate-500">Test Scenarios:</span>
                  <button
                    onClick={() => {
                      setInputUrl('https://python.org');
                      setCustomAlias('');
                      handleCreateURL('https://python.org', '');
                    }}
                    className="text-xs px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
                  >
                    Valid URL (Auto Base62)
                  </button>
                  <button
                    onClick={() => {
                      setInputUrl('https://developer.mozilla.org');
                      setCustomAlias('mdn-web');
                      handleCreateURL('https://developer.mozilla.org', 'mdn-web');
                    }}
                    className="text-xs px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
                  >
                    Custom Alias
                  </button>
                  <button
                    onClick={() => {
                      setInputUrl('https://example.com/duplicate');
                      setCustomAlias('mdn-web');
                      handleCreateURL('https://example.com/duplicate', 'mdn-web');
                    }}
                    className="text-xs px-2.5 py-1 rounded bg-amber-950/60 hover:bg-amber-900/60 text-amber-300 border border-amber-800/50 transition"
                  >
                    Duplicate Alias (409 Conflict)
                  </button>
                  <button
                    onClick={() => {
                      setInputUrl('javascript:alert(1)');
                      setCustomAlias('');
                      handleCreateURL('javascript:alert(1)', '');
                    }}
                    className="text-xs px-2.5 py-1 rounded bg-rose-950/60 hover:bg-rose-900/60 text-rose-300 border border-rose-800/50 transition flex items-center space-x-1"
                  >
                    <ShieldAlert className="w-3 h-3" />
                    <span>Malicious Scheme (422 Reject)</span>
                  </button>
                </div>
              </div>
            </div>

            {/* Response & Metadata Explorer Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Left Column: API Actions & Active Links */}
              <div className="lg:col-span-1 space-y-4">
                {/* Last Generated URL Card */}
                {lastCreated && (
                  <div className="bg-slate-900 border border-emerald-800/50 rounded-xl p-5 bg-gradient-to-b from-emerald-950/20 to-slate-900">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-semibold text-emerald-400 uppercase tracking-wider">
                        Active Short Link
                      </span>
                      <span className="text-xs font-mono text-slate-400">HTTP 201</span>
                    </div>

                    <div className="font-mono text-sm font-bold text-white break-all bg-slate-950/80 p-2.5 rounded border border-slate-800 flex items-center justify-between">
                      <span>{lastCreated.short_url}</span>
                      <button
                        onClick={() => copyToClipboard(lastCreated.short_url)}
                        className="ml-2 p-1 text-slate-400 hover:text-white transition"
                        title="Copy to clipboard"
                      >
                        {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                      </button>
                    </div>

                    <div className="mt-3 flex items-center justify-between text-xs">
                      <span className="text-slate-400">Short Code:</span>
                      <span className="font-mono text-indigo-300 font-bold">{lastCreated.short_code}</span>
                    </div>
                  </div>
                )}

                {/* Metadata Query Card */}
                <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
                  <h2 className="text-sm font-semibold text-white mb-2 flex items-center space-x-2">
                    <Terminal className="w-4 h-4 text-indigo-400" />
                    <span>Query URL Metadata</span>
                  </h2>
                  <p className="text-xs text-slate-400 mb-3">
                    Fetch creation timestamp, click statistics, and target destination for a given short code.
                  </p>

                  <div className="flex space-x-2">
                    <input
                      type="text"
                      value={queryCode}
                      onChange={(e) => setQueryCode(e.target.value)}
                      placeholder="Short Code (e.g. UOEnjbR)"
                      className="flex-1 px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-xs font-mono text-white focus:outline-none focus:border-indigo-500"
                    />
                    <button
                      onClick={() => handleGetMetadata(queryCode)}
                      className="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium rounded-lg transition"
                    >
                      Query
                    </button>
                  </div>
                </div>

                {/* Endpoint Switchers */}
                <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
                  <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                    Raw HTTP Endpoints
                  </h3>
                  <div className="space-y-1.5">
                    <button
                      onClick={() => testEndpoint('/health')}
                      className="w-full text-left px-3 py-2 rounded-lg bg-slate-950/60 hover:bg-slate-800 text-xs font-mono text-slate-300 flex items-center justify-between border border-slate-800"
                    >
                      <span>GET /health</span>
                      <span className="text-[10px] text-emerald-400">200 OK</span>
                    </button>
                    <button
                      onClick={() => testEndpoint('/')}
                      className="w-full text-left px-3 py-2 rounded-lg bg-slate-950/60 hover:bg-slate-800 text-xs font-mono text-slate-300 flex items-center justify-between border border-slate-800"
                    >
                      <span>GET /</span>
                      <span className="text-[10px] text-emerald-400">200 OK</span>
                    </button>
                  </div>
                </div>
              </div>

              {/* Right Column: Terminal-style Response Viewer */}
              <div className="lg:col-span-2">
                <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden flex flex-col h-full">
                  <div className="bg-slate-950/80 border-b border-slate-800 px-4 py-3 flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <div className="flex space-x-1.5">
                        <span className="w-3 h-3 rounded-full bg-rose-500/80 inline-block" />
                        <span className="w-3 h-3 rounded-full bg-amber-500/80 inline-block" />
                        <span className="w-3 h-3 rounded-full bg-emerald-500/80 inline-block" />
                      </div>
                      <span className="text-xs font-mono text-slate-400 ml-2">
                        {endpointResult?.method || 'GET'} {endpointResult?.endpoint || '/api/v1/urls'}
                      </span>
                    </div>

                    {endpointResult && (
                      <div className="flex items-center space-x-2 text-xs font-mono">
                        <span
                          className={`px-2 py-0.5 rounded border ${
                            endpointResult.statusCode === 201 || endpointResult.statusCode === 200
                              ? 'bg-emerald-950 text-emerald-400 border-emerald-800'
                              : endpointResult.statusCode === 422 || endpointResult.statusCode === 409
                              ? 'bg-amber-950 text-amber-400 border-amber-800'
                              : 'bg-rose-950 text-rose-400 border-rose-800'
                          }`}
                        >
                          HTTP {endpointResult.statusCode}
                        </span>
                        {endpointResult.latencyMs !== null && (
                          <span className="text-slate-400">{endpointResult.latencyMs}ms</span>
                        )}
                      </div>
                    )}
                  </div>

                  <div className="p-4 flex-1 font-mono text-xs overflow-x-auto bg-slate-950/40 text-emerald-400">
                    {endpointResult?.data ? (
                      <pre className="whitespace-pre-wrap">
                        {JSON.stringify(endpointResult.data, null, 2)}
                      </pre>
                    ) : endpointResult?.error ? (
                      <div className="text-rose-400">{endpointResult.error}</div>
                    ) : (
                      <div className="text-slate-500 italic py-8 text-center">
                        Submit a URL or click a probe to inspect live HTTP responses.
                      </div>
                    )}
                  </div>

                  <div className="bg-slate-950/60 border-t border-slate-800 px-4 py-2.5 flex items-center justify-between text-xs text-slate-400">
                    <span>Base62 Keyspace: 62^7 = 3.52 Trillion Tokens</span>
                    <span className="text-slate-500 font-mono">Pydantic Schemas Enforced</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: Architecture & Design */}
        {activeTab === 'architecture' && (
          <div className="space-y-6">
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
              <h2 className="text-lg font-bold text-white mb-2">URLForge System Architecture</h2>
              <p className="text-sm text-slate-300 mb-6">
                URLForge is engineered according to Clean Architecture principles. API routes remain thin,
                business logic is isolated into services, and data persistence layers are strictly decoupled.
              </p>

              {/* Architectural Block Diagram */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4 p-4 rounded-xl bg-slate-950 border border-slate-800/80 mb-6">
                <div className="p-4 rounded-lg bg-slate-900 border border-slate-800 text-center">
                  <div className="text-xs font-mono text-indigo-400 mb-1">CLIENT TIER</div>
                  <div className="font-semibold text-white text-sm">Browser / HTTP Client</div>
                  <div className="text-xs text-slate-400 mt-1">REST API / Redirect Requests</div>
                </div>

                <div className="p-4 rounded-lg bg-indigo-950/40 border border-indigo-800/60 text-center">
                  <div className="text-xs font-mono text-indigo-300 mb-1">ROUTING & MIDDLEWARE</div>
                  <div className="font-semibold text-white text-sm">FastAPI + Starlette</div>
                  <div className="text-xs text-slate-300 mt-1">Validation, CORS, Correlation IDs</div>
                </div>

                <div className="p-4 rounded-lg bg-slate-900 border border-slate-800 text-center">
                  <div className="text-xs font-mono text-amber-400 mb-1">CACHE TIER (Phase 6)</div>
                  <div className="font-semibold text-white text-sm">Redis Cluster</div>
                  <div className="text-xs text-slate-400 mt-1">Sub-millisecond redirect lookups</div>
                </div>

                <div className="p-4 rounded-lg bg-slate-900 border border-slate-800 text-center">
                  <div className="text-xs font-mono text-emerald-400 mb-1">DATA TIER (Phase 3)</div>
                  <div className="font-semibold text-white text-sm">PostgreSQL + Alembic</div>
                  <div className="text-xs text-slate-400 mt-1">ACID durability & unique constraints</div>
                </div>
              </div>

              {/* Core Design Decisions */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="p-4 rounded-lg bg-slate-950/60 border border-slate-800">
                  <h3 className="text-sm font-semibold text-white mb-2 flex items-center space-x-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    <span>Thin Route Handlers</span>
                  </h3>
                  <p className="text-xs text-slate-300 leading-relaxed">
                    Routes in `app/routes/` only handle HTTP semantics: parsing request bodies, validating headers,
                    calling the corresponding service, and mapping output models to HTTP status codes. No SQL queries or cache commands live in route files.
                  </p>
                </div>

                <div className="p-4 rounded-lg bg-slate-950/60 border border-slate-800">
                  <h3 className="text-sm font-semibold text-white mb-2 flex items-center space-x-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    <span>Fail-Fast 12-Factor Settings</span>
                  </h3>
                  <p className="text-xs text-slate-300 leading-relaxed">
                    Configuration in `app/config.py` uses Pydantic's `BaseSettings`. Missing critical variables or invalid data types halt execution at boot time rather than blowing up during user traffic.
                  </p>
                </div>

                <div className="p-4 rounded-lg bg-slate-950/60 border border-slate-800">
                  <h3 className="text-sm font-semibold text-white mb-2 flex items-center space-x-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    <span>Dependency Injection</span>
                  </h3>
                  <p className="text-xs text-slate-300 leading-relaxed">
                    Database sessions, cache clients, and rate limiters are injected via FastAPI's `Depends()`.
                    This eliminates global state and enables instantaneous unit test mocking.
                  </p>
                </div>

                <div className="p-4 rounded-lg bg-slate-950/60 border border-slate-800">
                  <h3 className="text-sm font-semibold text-white mb-2 flex items-center space-x-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    <span>Database-Enforced Integrity</span>
                  </h3>
                  <p className="text-xs text-slate-300 leading-relaxed">
                    Never trust in-memory `SELECT` checks to prevent duplicate short codes under concurrent load.
                    Unique constraints at the database level are the only authoritative defense against race conditions.
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Tab 3: Development Roadmap */}
        {activeTab === 'roadmap' && (
          <div className="space-y-6">
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="text-lg font-bold text-white">System Development Roadmap</h2>
                  <p className="text-sm text-slate-300">
                    15 progressive engineering milestones building a production-grade backend service.
                  </p>
                </div>
                <div className="text-right">
                  <span className="text-xs font-mono text-emerald-400">Phase 2 / 15 Complete</span>
                  <div className="w-32 h-2 bg-slate-800 rounded-full mt-1 overflow-hidden">
                    <div className="w-2/15 h-full bg-emerald-500 rounded-full" style={{ width: '13%' }} />
                  </div>
                </div>
              </div>

              <div className="space-y-3">
                {phases.map((p) => (
                  <div
                    key={p.num}
                    className={`p-4 rounded-lg border transition flex items-start justify-between ${
                      p.status === 'completed'
                        ? 'bg-emerald-950/20 border-emerald-800/40 text-slate-200'
                        : p.status === 'current'
                        ? 'bg-indigo-950/30 border-indigo-700/50 text-slate-200 shadow-sm'
                        : 'bg-slate-950/40 border-slate-800/60 text-slate-400'
                    }`}
                  >
                    <div className="flex items-start space-x-3">
                      <div className="mt-0.5">
                        {p.status === 'completed' && (
                          <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                        )}
                        {p.status === 'current' && (
                          <div className="w-5 h-5 rounded-full border-2 border-indigo-400 border-t-transparent animate-spin" />
                        )}
                        {p.status === 'upcoming' && (
                          <div className="w-5 h-5 rounded-full border border-slate-700 flex items-center justify-center text-xs font-mono text-slate-500">
                            {p.num}
                          </div>
                        )}
                      </div>
                      <div>
                        <div className="flex items-center space-x-2">
                          <span className="font-semibold text-sm text-white">
                            Phase {p.num}: {p.name}
                          </span>
                          {p.status === 'completed' && (
                            <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded bg-emerald-900/60 text-emerald-300">
                              Verified
                            </span>
                          )}
                          {p.status === 'current' && (
                            <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded bg-indigo-900/60 text-indigo-300">
                              Current Milestone
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-slate-400 mt-1">{p.desc}</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Tab 4: CS Interview Deep-Dives */}
        {activeTab === 'interview' && (
          <div className="space-y-6">
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
              <h2 className="text-lg font-bold text-white mb-2">CS & Backend Engineering Interview Prep</h2>
              <p className="text-sm text-slate-300 mb-6">
                Mastering backend concepts requires understanding trade-offs, internal runtimes, and real production failure modes.
              </p>

              <div className="space-y-4">
                {interviewQuestions.map((item, idx) => (
                  <div
                    key={idx}
                    className="border border-slate-800 rounded-lg overflow-hidden bg-slate-950/60 transition"
                  >
                    <button
                      onClick={() => setOpenInterviewIndex(openInterviewIndex === idx ? null : idx)}
                      className="w-full text-left p-4 flex items-center justify-between hover:bg-slate-900/60 transition"
                    >
                      <div className="flex items-center space-x-3">
                        <span className="w-6 h-6 rounded-full bg-indigo-950 text-indigo-400 border border-indigo-800/60 flex items-center justify-center text-xs font-mono">
                          Q{idx + 1}
                        </span>
                        <span className="font-semibold text-sm text-white">{item.q}</span>
                      </div>
                      <ArrowRight className={`w-4 h-4 text-slate-400 transition-transform ${openInterviewIndex === idx ? 'rotate-90' : ''}`} />
                    </button>

                    {openInterviewIndex === idx && (
                      <div className="p-4 pt-0 space-y-3 border-t border-slate-800/60 bg-slate-900/30">
                        <div>
                          <div className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">
                            Short Answer (Elevator Pitch)
                          </div>
                          <p className="text-xs text-slate-200 bg-slate-950/50 p-2.5 rounded border border-slate-800">
                            {item.short}
                          </p>
                        </div>

                        <div>
                          <div className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">
                            Deep Technical Explanation
                          </div>
                          <p className="text-xs text-slate-300 leading-relaxed">
                            {item.deep}
                          </p>
                        </div>

                        <div>
                          <div className="text-xs font-bold text-indigo-400 uppercase tracking-wider mb-1">
                            URLForge Architecture Context
                          </div>
                          <p className="text-xs text-indigo-200/90 bg-indigo-950/30 p-2.5 rounded border border-indigo-900/50 leading-relaxed">
                            {item.forge}
                          </p>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800 bg-slate-900/60 py-4 mt-auto">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 flex flex-col sm:flex-row items-center justify-between text-xs text-slate-400">
          <div>URLForge &copy; 2026 &bull; Production-Grade Computer Science Architecture</div>
          <div className="flex items-center space-x-4 mt-2 sm:mt-0 font-mono">
            <span>FastAPI 0.141</span>
            <span>&bull;</span>
            <span>Uvicorn 0.53</span>
            <span>&bull;</span>
            <span>Python 3.11</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
