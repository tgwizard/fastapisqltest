# Test FastAPI with SQLAlchemy and session usage

> [!WARNING]
> This is a very basic test, to help myself understand how to use FastAPI with SQLModel / SQLAlchemy and session usage.

I find it so very weird that SQLAlchemy by default creates a transaction on first session use, and keeps this open until you close the session. And that SQLAlchemy recommends to keep one session for a web request

https://docs.sqlalchemy.org/en/20/orm/session_basics.html#session-faq-whentocreate

> Web applications. In this case, it’s best to make use of the SQLAlchemy integrations provided by the web framework in use. Or otherwise, the basic pattern is create a Session at the start of a web request, call the Session.commit() method at the end of web requests that do POST, PUT, or DELETE, and then close the session at the end of web request. It’s also usually a good idea to set Session.expire_on_commit to False so that subsequent access to objects that came from a Session within the view layer do not need to emit new SQL queries to refresh the objects, if the transaction has been committed already.

Transactions are expensive to keep open.

If a we in a request do a DB read to fetch, say, a user, and then a slow API call to OpenAI, we don't want concurrent requests to be blocked from accessing the DB

1. because the transaction is still open.
2. there's no connection available.

My current conclusion is that we should use locally scoped sessions, closing them as early as possible, and opening multiple sessions per request, as needed. (We should also use async sessions and async routes).

There are probably drawbacks here too, that I'll find out later.

I'm considering whether we should try to disable the SQLAlchemy default transactions for read-only queries.


## Setup

Start the database

```bash
podman run --name postgres_container -e POSTGRES_PASSWORD=mysecretpassword -d -p 5432:5432 -v postgres_data:/var/lib/postgresql/data postgres
```

Optionally psql in to see activity:

```bash
PGPASSWORD=mysecretpassword /opt/homebrew/opt/libpq/bin/psql -h localhost -U postgres
```

Run

```sql
SELECT                                                                                 backend_start,                                                                                xact_start,                                                                                   query_start,                                                                                  state_change,                                                                                 state,                                                                                        substring(query for 50) AS query                                                          FROM pg_stat_activity                                                                         WHERE backend_type = 'client backend';
```

We can here see whether transactions are open or not.

Run the app

```
uv sync
uv run uvicorn a:app --port 8080 --workers 1
```

(I didn't specify connection pool size, relies on the default of 5)


## Results

Run vegeta to test the endpoints

#### Sync session sleep outside session

```
$ echo -n "GET http://localhost:8080/sync_session_sleep_outside_session" | vegeta attack -duration=5s -rate=100 | tee results.bin | vegeta report
Requests      [total, rate, throughput]         500, 100.18, 19.03
Duration      [total, attack, wait]             26.276s, 4.991s, 21.285s
Latencies     [min, mean, 50, 90, 95, 99, max]  2.003s, 11.267s, 11.646s, 19.682s, 19.713s, 21.317s, 21.354s
Bytes In      [total, mean]                     13000, 26.00
Bytes Out     [total, mean]                     0, 0.00
Success       [ratio]                           100.00%
Status Codes  [code:count]                      200:500
Error Set:
```

Works, but lots of wait time. p99 and p100 latencies are high.

#### Sync session sleep inside session

```
$ echo -n "GET http://localhost:8080/sync_session_sleep_inside_session" | vegeta attack -duration=5s -rate=100 | tee results.bin | vegeta report
Requests      [total, rate, throughput]         500, 100.20, 6.80
Duration      [total, attack, wait]             34.991s, 4.99s, 30.001s
Latencies     [min, mean, 50, 90, 95, 99, max]  2.004s, 23.251s, 30s, 30.001s, 30.001s, 30.001s, 30.002s
Bytes In      [total, mean]                     6188, 12.38
Bytes Out     [total, mean]                     0, 0.00
Success       [ratio]                           47.60%
Status Codes  [code:count]                      0:262  200:238
Error Set:
Get "http://localhost:8080/sync_session_sleep_inside_session": context deadline exceeded (Client.Timeout exceeded while awaiting headers)
```

Timeouts.

#### Async session sleep outside session

```
$ echo -n "GET http://localhost:8080/async_session_sleep_outside_session" | vegeta attack -duration=5s -rate=100 | tee results.bin | vegeta report
Requests      [total, rate, throughput]         500, 100.20, 71.49
Duration      [total, attack, wait]             6.994s, 4.99s, 2.004s
Latencies     [min, mean, 50, 90, 95, 99, max]  2.002s, 2.006s, 2.004s, 2.006s, 2.008s, 2.102s, 2.121s
Bytes In      [total, mean]                     13000, 26.00
Bytes Out     [total, mean]                     0, 0.00
Success       [ratio]                           100.00%
Status Codes  [code:count]                      200:500
Error Set:
```

This is the best. p99 and p100 latencies are low.


#### Async session sleep inside session

```
$ echo -n "GET http://localhost:8080/async_session_sleep_inside_session" | vegeta attack -duration=5s -rate=100 | tee results.bin | vegeta report
Requests      [total, rate, throughput]         500, 100.21, 6.86
Duration      [total, attack, wait]             34.991s, 4.99s, 30.001s
Latencies     [min, mean, 50, 90, 95, 99, max]  2.005s, 23.268s, 30s, 30.001s, 30.001s, 30.001s, 30.004s
Bytes In      [total, mean]                     6240, 12.48
Bytes Out     [total, mean]                     0, 0.00
Success       [ratio]                           48.00%
Status Codes  [code:count]                      0:260  200:240
Error Set:
Get "http://localhost:8080/async_session_sleep_inside_session": context deadline exceeded (Client.Timeout exceeded while awaiting headers)
```

Also times out