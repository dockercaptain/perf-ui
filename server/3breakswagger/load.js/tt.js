import http from 'k6/http';
import { check } from 'k6';

export let options = {
  vus: 1, // number of virtual users
  duration: '3s', // test duration
};

export default function () {
  let res = http.get('http://localhost:8081/');

  check(res, {
    'status is 404': (r) => r.status === 404,
  });
}

