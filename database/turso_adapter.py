"""
Turso / libSQL HTTP Adapter for QuickHire
Allows seamless connection to Turso Cloud SQLite database via standard HTTP Pipeline API.
Requires no binary compilation or external C-extensions, fully compatible with Vercel serverless.
"""

import os
import json
import urllib.request
import urllib.error
from datetime import date, datetime

class TursoRow(dict):
    """
    Dictionary-like and tuple-like row object that behaves identically to sqlite3.Row.
    Supports row['col_name'], row[0], dict(row), and case-insensitive column lookups.
    """
    def __init__(self, cols, values):
        super().__init__()
        self._cols = list(cols)
        self._cols_lower = {c.lower(): idx for idx, c in enumerate(cols)}
        self._values = list(values)
        for col, val in zip(cols, values):
            self[col] = val

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        if isinstance(key, str):
            if key in self:
                return super().__getitem__(key)
            if key.lower() in self._cols_lower:
                return self._values[self._cols_lower[key.lower()]]
            raise KeyError(key)
        return super().__getitem__(key)

    def get(self, key, default=None):
        try:
            return self[key]
        except (KeyError, IndexError):
            return default

    def keys(self):
        return self._cols

    def values(self):
        return self._values


def _format_arg(val):
    if val is None:
        return {'type': 'null'}
    elif isinstance(val, bool):
        return {'type': 'integer', 'value': '1' if val else '0'}
    elif isinstance(val, int):
        return {'type': 'integer', 'value': str(val)}
    elif isinstance(val, float):
        return {'type': 'float', 'value': val}
    elif isinstance(val, (date, datetime)):
        return {'type': 'text', 'value': val.isoformat()}
    elif isinstance(val, bytes):
        import base64
        return {'type': 'blob', 'base64': base64.b64encode(val).decode('utf-8')}
    else:
        return {'type': 'text', 'value': str(val)}


def _parse_val(v):
    if v is None:
        return None
    t = v.get('type')
    val = v.get('value')
    if t == 'null' or val is None:
        return None
    elif t == 'integer':
        return int(val)
    elif t == 'float':
        return float(val)
    elif t == 'text':
        return str(val)
    elif t == 'blob':
        import base64
        b64 = v.get('base64', '')
        return base64.b64decode(b64)
    return val


class TursoCursor:
    def __init__(self, connection):
        self.connection = connection
        self.lastrowid = None
        self.rowcount = -1
        self.description = None
        self._rows = []
        self._index = 0

    def execute(self, sql, params=None):
        res = self.connection._execute_sql(sql, params)
        cols = [c['name'] for c in res.get('cols', [])]
        self.description = [(c, None, None, None, None, None, None) for c in cols]
        self.lastrowid = res.get('last_insert_rowid')
        self.rowcount = res.get('affected_row_count', -1)
        
        raw_rows = res.get('rows', [])
        self._rows = []
        for r in raw_rows:
            parsed_vals = [_parse_val(v) for v in r]
            self._rows.append(TursoRow(cols, parsed_vals))
        self._index = 0
        return self

    def executemany(self, sql, seq_of_params):
        for params in seq_of_params:
            self.execute(sql, params)
        return self

    def executescript(self, script_sql):
        statements = [s.strip() for s in script_sql.split(';') if s.strip()]
        for stmt in statements:
            self.execute(stmt)
        return self

    def fetchone(self):
        if self._index < len(self._rows):
            row = self._rows[self._index]
            self._index += 1
            return row
        return None

    def fetchall(self):
        if self._index == 0:
            self._index = len(self._rows)
            return self._rows
        rows = self._rows[self._index:]
        self._index = len(self._rows)
        return rows

    def fetchmany(self, size=None):
        if size is None:
            size = 1
        end = min(self._index + size, len(self._rows))
        rows = self._rows[self._index:end]
        self._index = end
        return rows

    def close(self):
        self._rows = []
        self._index = 0


class TursoConnection:
    def __init__(self, url, auth_token):
        if url.startswith('libsql://'):
            url = 'https://' + url[len('libsql://'):]
        elif url.startswith('http://'):
            url = 'https://' + url[len('http://'):]
        
        self.base_url = url.rstrip('/')
        self.pipeline_url = f"{self.base_url}/v2/pipeline"
        self.auth_token = auth_token
        self.row_factory = None

    def cursor(self):
        return TursoCursor(self)

    def _execute_sql(self, sql, params=None):
        formatted_args = []
        if params is not None:
            if isinstance(params, (list, tuple)):
                formatted_args = [_format_arg(p) for p in params]
            elif isinstance(params, dict):
                # Named args
                formatted_args = {k: _format_arg(v) for k, v in params.items()}
            else:
                formatted_args = [_format_arg(params)]

        stmt_obj = {'sql': sql}
        if formatted_args:
            if isinstance(formatted_args, list):
                stmt_obj['args'] = formatted_args
            elif isinstance(formatted_args, dict):
                stmt_obj['named_args'] = formatted_args

        payload = {
            'requests': [
                {
                    'type': 'execute',
                    'stmt': stmt_obj
                }
            ]
        }

        headers = {
            'Authorization': f'Bearer {self.auth_token}',
            'Content-Type': 'application/json'
        }

        req_data = json.dumps(payload).encode('utf-8')
        max_retries = 3
        last_err = None

        for attempt in range(max_retries):
            req = urllib.request.Request(
                self.pipeline_url,
                data=req_data,
                headers=headers,
                method='POST'
            )
            try:
                with urllib.request.urlopen(req, timeout=20) as resp:
                    data = json.loads(resp.read().decode('utf-8'))
                    results = data.get('results', [])
                    if not results:
                        return {'cols': [], 'rows': [], 'affected_row_count': 0, 'last_insert_rowid': None}
                    first = results[0]
                    if first.get('type') == 'error':
                        err_msg = first.get('error', {}).get('message', 'Turso query error')
                        raise RuntimeError(f"Turso error: {err_msg} (Query: {sql})")
                    return first.get('response', {}).get('result', {})
            except urllib.error.HTTPError as e:
                err_body = e.read().decode('utf-8') if e.fp else str(e)
                raise RuntimeError(f"Turso HTTP Error {e.code}: {err_body} (Query: {sql})")
            except Exception as e:
                last_err = e
                if attempt < max_retries - 1:
                    import time
                    time.sleep(0.3 * (attempt + 1))
                else:
                    raise RuntimeError(f"Turso Connection Error: {last_err} (Query: {sql})") from last_err

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass

    def execute(self, sql, params=None):
        cur = self.cursor()
        return cur.execute(sql, params)

    def executescript(self, script_sql):
        cur = self.cursor()
        return cur.executescript(script_sql)


def get_turso_connection():
    url = os.environ.get('TURSO_DATABASE_URL') or os.environ.get('TURSO_URL')
    token = os.environ.get('TURSO_AUTH_TOKEN') or os.environ.get('TURSO_TOKEN')
    if url and token:
        return TursoConnection(url, token)
    return None
