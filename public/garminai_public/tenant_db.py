"""Tenant-scoped SQLite reference implementation for isolated tests ONLY.

Not connected to public MCP tools, Garmin accounts or production storage.
SQLite on Render Free is ephemeral and MUST NOT hold real user data.
"""
import json
import sqlite3
from .identity import VerifiedPrincipal

class TenantActivityDB:
    def __init__(self, database=':memory:'):
        self.connection=sqlite3.connect(database)
        self.connection.execute('PRAGMA foreign_keys=ON')
        self.connection.execute("""CREATE TABLE IF NOT EXISTS activities (
            owner_subject TEXT NOT NULL, activity_id TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            PRIMARY KEY(owner_subject,activity_id))""")
    @staticmethod
    def _subject(principal):
        if not isinstance(principal,VerifiedPrincipal):
            raise PermissionError('Verified principal required')
        return principal.subject
    @staticmethod
    def _id(activity_id):
        if not isinstance(activity_id,str) or not activity_id or len(activity_id)>128:
            raise ValueError('Invalid activity id')
        return activity_id
    def upsert(self, principal, activity_id, payload):
        owner=self._subject(principal); self._id(activity_id)
        if not isinstance(payload,dict):raise ValueError('Record must be an object')
        data=json.dumps(payload,ensure_ascii=False,allow_nan=False)
        if len(data)>200000:raise ValueError('Record too large')
        with self.connection:
            self.connection.execute("""INSERT INTO activities(owner_subject,activity_id,payload_json)
                VALUES (?,?,?) ON CONFLICT(owner_subject,activity_id) DO UPDATE SET
                payload_json=excluded.payload_json""",(owner,activity_id,data))
    def get(self, principal, activity_id):
        owner=self._subject(principal); self._id(activity_id)
        row=self.connection.execute("""SELECT payload_json FROM activities
           WHERE owner_subject=? AND activity_id=?""",(owner,activity_id)).fetchone()
        return json.loads(row[0]) if row else None
    def list(self, principal, limit=100):
        owner=self._subject(principal)
        if type(limit) is not int or not 1<=limit<=100:raise ValueError('Invalid limit')
        rows=self.connection.execute("""SELECT activity_id,payload_json FROM activities
           WHERE owner_subject=? ORDER BY activity_id LIMIT ?""",(owner,limit)).fetchall()
        return [{'activity_id':id,'data':json.loads(data)} for id,data in rows]
    def delete(self, principal, activity_id):
        owner=self._subject(principal); self._id(activity_id)
        with self.connection:
            cur=self.connection.execute("""DELETE FROM activities
                WHERE owner_subject=? AND activity_id=?""",(owner,activity_id))
        return cur.rowcount > 0
    def delete_all_for_principal(self, principal):
        owner=self._subject(principal)
        with self.connection:
            cur=self.connection.execute('DELETE FROM activities WHERE owner_subject=?',(owner,))
        return cur.rowcount
    def close(self):self.connection.close()
