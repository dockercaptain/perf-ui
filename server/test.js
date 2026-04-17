import http from 'k6/http';
import { Trend } from 'k6/metrics';
import { uuidv4 } from 'https://jslib.k6.io/k6-utils/1.4.0/index.js';

export const options = {
  vus: 1,
  duration: '30s',
};

const BASE_URL = __ENV.BASE_URL;

const rootDuration = new Trend('GET_root_duration');
const notfoundDuration = new Trend('GET_notfound_duration');
const randomStatusDuration = new Trend('GET_random_status_duration');
const okDuration = new Trend('GET_ok_duration');
const badDuration = new Trend('GET_bad_duration');

function getTracingHeaders() {
  const traceID = Math.floor(Math.random() * 1e18).toString();
  const parentID = Math.floor(Math.random() * 1e18).toString();

  const headers = {
    'x-datadog-trace-id': traceID,
    'x-datadog-parent-id': parentID,
    'x-datadog-sampling-priority': '1',
    'x-trace-id': traceID,
  };

  const tags = {
    'trace_id': traceID,
    'parent_id': parentID,
    'sampling_priority': '1',
  };

  return { headers, tags };
}

function get_root() {
  const { headers: tracingHeaders, tags: tracingTags } = getTracingHeaders();
  const res = http.get(`${BASE_URL}/`, {
    headers: {
      ...tracingHeaders,
    },
    redirects: 0,
    tags: {
      name: 'GET /',
      ...tracingTags,
    },
  });
  rootDuration.add(res.timings.duration);
}

function get_notfound() {
  const { headers: tracingHeaders, tags: tracingTags } = getTracingHeaders();
  const res = http.get(`${BASE_URL}/notfound`, {
    headers: {
      'X-Client-ID': 'k6-test-client',
      'Authorization': 'Bearer dummy_token',
      ...tracingHeaders,
    },
    redirects: 0,
    tags: {
      name: 'GET /notfound',
      ...tracingTags,
    },
  });
  notfoundDuration.add(res.timings.duration);
}

function get_random_status() {
  const { headers: tracingHeaders, tags: tracingTags } = getTracingHeaders();
  const res = http.get(`${BASE_URL}/random/status`, {
    headers: {
      'X-Client-ID': 'k6-test-client',
      ...tracingHeaders,
    },
    redirects: 0,
    tags: {
      name: 'GET /random/status',
      ...tracingTags,
    },
  });
  randomStatusDuration.add(res.timings.duration);
}

function get_ok() {
  const { headers: tracingHeaders, tags: tracingTags } = getTracingHeaders();
  const res = http.get(`${BASE_URL}/ok`, {
    headers: {
      'X-Client-ID': 'k6-test-client',
      'Authorization': 'Bearer dummy_token',
      ...tracingHeaders,
    },
    redirects: 0,
    tags: {
      name: 'GET /ok',
      ...tracingTags,
    },
  });
  okDuration.add(res.timings.duration);
}

function get_bad() {
  const { headers: tracingHeaders, tags: tracingTags } = getTracingHeaders();
  const res = http.get(`${BASE_URL}/bad`, {
    headers: {
      'X-Client-ID': 'k6-test-client',
      'Authorization': 'Bearer dummy_token',
      ...tracingHeaders,
    },
    redirects: 0,
    tags: {
      name: 'GET /bad',
      ...tracingTags,
    },
  });
  badDuration.add(res.timings.duration);
}

export default function () {
  get_root();
  get_notfound();
  get_random_status();
  get_ok();
  get_bad();
}