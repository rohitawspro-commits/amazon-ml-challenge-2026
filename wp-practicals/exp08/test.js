// Calls the API as different users and prints one line per request.
const BASE = 'http://localhost:3008/api';

async function call(label, method, path, token, body) {
  const res = await fetch(BASE + path, {
    method,
    headers: { 'Content-Type': 'application/json', ...(token && { Authorization: 'Bearer ' + token }) },
    body: body && JSON.stringify(body)
  });
  const data = await res.json();
  const text = JSON.stringify(data.token ? { token: data.token.slice(0, 22) + '...' } : data);
  console.log(`${label.padEnd(30)} ${method.padEnd(6)} ${path.padEnd(14)} ${res.status}  ${text.slice(0, 60)}`);
  return data;
}

(async () => {
  const login = async u => (await call(`login ${u}`, 'POST', '/login', null, { username: u, password: u + '@123' })).token;
  await call('guest lists books', 'GET', '/books');
  await call('guest reads profile', 'GET', '/me');
  await call('wrong password', 'POST', '/login', null, { username: 'rohit', password: 'x' });
  const rohit = await login('rohit'), mehta = await login('mehta'), admin = await login('admin');
  await call('rohit reads profile', 'GET', '/me', rohit);
  await call('rohit own loans', 'GET', '/loans/1', rohit);
  await call('rohit loans of priya', 'GET', '/loans/2', rohit);
  await call('librarian loans of priya', 'GET', '/loans/2', mehta);
  await call('rohit adds book', 'POST', '/books', rohit, { title: 'DBMS' });
  await call('librarian adds book', 'POST', '/books', mehta, { title: 'Computer Networks', copies: 4 });
  await call('librarian deletes book', 'DELETE', '/books/101', mehta);
  await call('admin deletes book', 'DELETE', '/books/101', admin);
  await call('tampered token', 'GET', '/me', rohit.slice(0, -2) + 'xx');
})();
