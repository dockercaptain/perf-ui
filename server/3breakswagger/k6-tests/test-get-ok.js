import http from 'k6/http';
import { check, sleep } from 'k6';

export let options = {
  vus: 10,
  duration: '30s',
};

export default function () {
  let res = http.get('https://localhost:8081/ok', {
    headers: {
      'X-Client-ID': 'test'
    }
});
  check(res, {
    'status is 200': (r) => r.status === 200,
  });
  sleep(1);
}