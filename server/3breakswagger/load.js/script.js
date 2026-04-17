import http from "k6/http";
import { group, check, sleep } from "k6";
import { Trend } from "k6/metrics";

const BASE_URL = "http://localhost:8081";
const SLEEP_DURATION = 1;
const xClientID = "my-client-id";

// let traceDuration = new Trend("trace_duration");

export let options = {
  stages: [
    { duration: "20s", target: 1000 },
    { duration: "10s", target: 222 },
    { duration: "2s", target: 2 },
  ],
};

// Generate tracing headers
function getTracingHeaders() {
  let traceID = Math.floor(Math.random() * Number.MAX_SAFE_INTEGER);
  let parentID = Math.floor(Math.random() * Number.MAX_SAFE_INTEGER);

  return {
    traceID,
    headers: {
      "X-Client-ID": xClientID,
      "Accept": "application/json",
      "x-datadog-trace-id": traceID.toString(),
      "x-datadog-parent-id": parentID.toString(),
      "x-datadog-sampling-priority": "1",
    },
    tags: {
      trace_id: traceID.toString(),
    },
  };
}

export default function () {
  // --------- 1. Localhost /ok endpoint ---------
  group("/ok", () => {
    let { traceID, headers, tags } = getTracingHeaders();
    let res = http.get(`${BASE_URL}/ok`, { headers, tags });

    // traceDuration.add(res.timings.duration, { trace_id: traceID });

    check(res, {
      "status is 200": (r) => r.status === 200,
    });

    sleep(SLEEP_DURATION);
  });

  // --------- 2. Public GET endpoint ---------
  group("GET test.k6.io", () => {
    let { traceID, headers, tags } = getTracingHeaders();
    let res = http.get("https://test.k6.io/", { headers, tags });

    // traceDuration.add(res.timings.duration, { trace_id: traceID });

    check(res, {
      "status is 200": (r) => r.status === 200,
      "body has Welcome": (r) => r.body.includes("Welcome"),
    });

    sleep(SLEEP_DURATION);
  });

  // --------- 3. Endpoint with mixed statuses ---------
  group("GET random status", () => {
    let { traceID, headers, tags } = getTracingHeaders();

    // httpbin returns a 302 redirect first unless we stop it
    let res = http.get("http://localhost:8081/random/status", {
      headers,
      tags,
      redirects: 0, // 🚀 do not follow redirects, capture the real status
    });

    // traceDuration.add(res.timings.duration, { trace_id: traceID });

    check(res, {
      "status is 200/404/500": (r) => [200, 404, 500].includes(r.status),
    });

    sleep(SLEEP_DURATION);
  });
}

