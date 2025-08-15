import http from 'k6/http';
import { check } from 'k6';
import exec from 'k6/execution';

/**
 * k6 load test for an OpenAI-compatible vLLM endpoint.
 * Run:
 *   BASE_URL=http://localhost:8000/v1 \
 *   API_KEY=sk-... \
 *   MODEL=meta-llama/Meta-Llama-3.1-8B-Instruct \
 *   k6 run load_test.js
 *
 * Optional envs: PROMPT, MAX_TOKENS (default 128), STREAM (0/1)
 */

export const options = {
  scenarios: {
    rps_1: {
      executor: 'constant-arrival-rate',
      rate: 1, // requests per second
      timeUnit: '1s',
      duration: '2m',
      preAllocatedVUs: 10,
      maxVUs: 50,
      startTime: '0s',
    },
    rps_50: {
      executor: 'constant-arrival-rate',
      rate: 50,
      timeUnit: '1s',
      duration: '2m',
      preAllocatedVUs: 100,
      maxVUs: 300,
      startTime: '2m15s', // start after the first stage completes
    },
    rps_100: {
      executor: 'constant-arrival-rate',
      rate: 100,
      timeUnit: '1s',
      duration: '2m',
      preAllocatedVUs: 200,
      maxVUs: 600,
      startTime: '4m45s', // start after the second stage completes
    },
  },
  thresholds: {
    // Latency SLOs per stage (tune for your hardware/model)
    'http_req_duration{scenario:rps_1}': ['p(50)<1000', 'p(95)<3000', 'p(99)<5000'],
    'http_req_duration{scenario:rps_50}': ['p(95)<8000'],
    'http_req_duration{scenario:rps_100}': ['p(95)<15000'],
    'http_req_failed': ['rate<0.05'],
  },
  summaryTrendStats: ['avg','min','med','p(90)','p(95)','p(99)','max'],
};

const BASE_URL    = __ENV.BASE_URL || 'http://localhost:8000/v1';
const API_KEY     = __ENV.API_KEY || '';
const MODEL       = __ENV.MODEL || 'meta-llama/Meta-Llama-3.1-8B-Instruct';
const PROMPT      = __ENV.PROMPT || 'You are a helpful assistant. Respond briefly to: What is 10+9?';
const MAX_TOKENS  = parseInt(__ENV.MAX_TOKENS || '128', 10);
const STREAM      = (__ENV.STREAM || '0') === '1';

export default function () {
  const url = `${BASE_URL}/v1/chat/completions`;

  const payload = JSON.stringify({
    model: MODEL,
    messages: [{ role: 'user', content: PROMPT }],
    max_tokens: MAX_TOKENS,
    temperature: 0.2,
    stream: STREAM,
  });

  const params = {
    headers: {
      'Content-Type': 'application/json',
      ...(API_KEY ? { 'Authorization': `Bearer ${API_KEY}` } : {}),
    },
    timeout: '180s',
    // 'scenario' tag is added automatically by k6; keep our own stage tag too
    tags: { stage: exec.scenario.name },
  };

  const res = http.post(url, payload, params);

  check(res, {
    'status is 200': (r) => r.status === 200,
    'has choices': (r) => r.status === 200 && r.json('choices') !== undefined,
  });
}

export function handleSummary(data) {
  // Write a JSON summary that you can parse later
  return {
    'summary.json': JSON.stringify(data, null, 2),
  };
}
