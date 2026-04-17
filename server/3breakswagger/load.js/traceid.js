import http from "k6/http";
import { check, sleep } from "k6";

import { Trend } from "k6/metrics";

const customDuration = new Trend('custom_http_req_duration');

function generateDatadogTraceID() {
    return Math.floor(Math.random() * Number.MAX_SAFE_INTEGER).toString(); // Generates large numeric ID
}

function generateDatadogSpanID() {
    return Math.floor(Math.random() * Number.MAX_SAFE_INTEGER).toString();
}


  export const options = {
    vus: 2000,
    duration: '10s',
    thresholds: {
      http_req_failed: 
      [{ threshold: 'rate < 0.01', abortOnFail: true }],
    //   ['rate<0.01'],
    
    }
    
  };




// curl --location 'https://np-auth.wesco.com/realms/wesco/protocol/openid-connect/token' \
// --header 'accept: application/json' \
// --header 'Content-Type: application/x-www-form-urlencoded' \
// --data-urlencode 'client_id=cmp-sso-uat' \
// --data-urlencode 'username=user@wescodist.com' \
// --data-urlencode 'password=Login@123456' \
// --data-urlencode 'grant_type=password' \
// --data-urlencode 'scope=openid'


export default function () {
    const traceID = generateDatadogTraceID();
    const spanID = generateDatadogSpanID();
    const samplingPriority = "1"; // Ensure trace is sampled

    //const url = "https://cmp-device-service-uat.wescodevops.com/actuator/health"; // Replace with actual API

    // const url = "cmp-data-aggregation-service-dev.wescodevops.com/api/v1/so-txn";
    const url = "http://localhost:8081/ok";

    // const url = "https://example.com/";
     let res = http.get(url, JSON.stringify({ test: "datadog tracing" }), {
        headers: {
            "x-datadog-trace-id": traceID,
            "x-datadog-parent-id": spanID,
            "x-datadog-sampling-priority": samplingPriority,
        }
    });

    customDuration.add(res.timings.duration,{
        trace_id: traceID,
        span_id: spanID,
        method: res.request.method,
        name: `${url}`, // You can customize this
        proto: res.proto, // This might be undefined; see note below
        status: String(res.status),
        // expected_status: String(http.expectedStatuses),
      });
      
  
    check(res, { "status is 200": (r) => r.status === 200 });
    console.log(`Sent trace to Datadog: Trace ID=${traceID}, Span ID=${spanID}`);

    sleep(1);
}
