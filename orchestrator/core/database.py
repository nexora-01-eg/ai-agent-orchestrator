"""Database Management for Task History"""

import sqlite3
import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from contextlib import contextmanager


@dataclass
class TaskRecord:
    task_id: str
    date: str
    project_path: str
    task_description: str
    selected_agent: str
    model: str
    attempts: int
    duration_seconds: float
    changed_files: List[str]
    tests_run: bool
    test_results: str
    result: str  # success, failed, partial
    errors: str
    execution_log: str


class HistoryDatabase:
    """SQLite database for task history"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database schema"""
        with self._get_connection() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    date TEXT NOT NULL,
                    project_path TEXT NOT NULL,
                    task_description TEXT NOT NULL,
                    selected_agent TEXT NOT NULL,
                    model TEXT,
                    attempts INTEGER DEFAULT 1,
                    duration_seconds REAL,
                    changed_files TEXT,  -- JSON array
                    tests_run BOOLEAN DEFAULT 0,
                    test_results TEXT,
                    result TEXT NOT NULL,
                    errors TEXT,
                    execution_log TEXT
                )
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_tasks_date ON tasks(date)
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_tasks_agent ON tasks(selected_agent)
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project_path)
            ''')
            conn.commit()

    @contextmanager
    def _get_connection(self):
        """Get database connection with proper cleanup"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def add_task(self, task: TaskRecord) -> bool:
        """Add a new task record"""
        try:
            with self._get_connection() as conn:
                conn.execute('''
                    INSERT INTO tasks (task_id, date, project_path, task_description,
                                     selected_agent, model, attempts, duration_seconds,
                                     changed_files, tests_run, test_results, result,
                                     errors, execution_log)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    task.task_id,
                    task.date,
                    task.project_path,
                    task.task_description,
                    task.selected_agent,
                    task.model,
                    task.attempts,
                    task.duration_seconds,
                    json.dumps(task.changed_files),
                    int(task.tests_run),
                    task.test_results,
                    task.result,
                    task.errors,
                    task.execution_log
                ))
                conn.commit()
                return True
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return False

    def get_task(self, task_id: str) -> Optional[TaskRecord]:
        """Get a task by ID"""
        with self._get_connection() as conn:
            row = conn.execute('SELECT * FROM tasks WHERE task_id = ?', (task_id,)).fetchone()
            if row:
                return self._row_to_task(row)
        return None

    def get_all_tasks(self, limit: int = 100, offset: int = 0) -> List[TaskRecord]:
        """Get all tasks, most recent first"""
        with self._get_connection() as conn:
            rows = conn.execute(
                'SELECT * FROM tasks ORDER BY date DESC LIMIT ? OFFSET ?',
                (limit, offset)
            ).fetchall()
            return [self._row_to_task(row) for row in rows]

    def get_tasks_by_project(self, project_path: str) -> List[TaskRecord]:
        """Get tasks for a specific project"""
        with self._get_connection() as conn:
            rows = conn.execute(
                'SELECT * FROM tasks WHERE project_path = ? ORDER BY date DESC',
                (project_path,)
            ).fetchall()
            return [self._row_to_task(row) for row in rows]

    def get_tasks_by_agent(self, agent: str) -> List[TaskRecord]:
        """Get tasks for a specific agent"""
        with self._get_connection() as conn:
            rows = conn.execute(
                'SELECT * FROM tasks WHERE selected_agent = ? ORDER BY date DESC',
                (agent,)
            ).fetchall()
            return [self._row_to_task(row) for row in rows]

    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        with self._get_connection() as conn:
            total = conn.execute('SELECT COUNT(*) FROM tasks').fetchone()[0]
            success = conn.execute("SELECT COUNT(*) FROM tasks WHERE result = 'success'").fetchone()[0]
            failed = conn.execute("SELECT COUNT(*) FROM tasks WHERE result = 'failed'").fetchone()[0]
            partial = conn.execute("SELECT COUNT(*) FROM tasks WHERE result = 'partial'").fetchone()[0]

            by_agent = {}
            rows = conn.execute('SELECT selected_agent, COUNT(*) FROM tasks GROUP BY selected_agent').fetchall()
            for row in rows:
                by_agent[row[0]] = row[1]

            return {
                'total_tasks': total,
                'success': success,
                'failed': failed,
                'partial': partial,
                'by_agent': by_agent
            }

    def cleanup_old_tasks(self, max_entries: int = 1000):
        """Remove old tasks if exceeding max_entries"""
        with self._get_connection() as conn:
            count = conn.execute('SELECT COUNT(*) FROM tasks').fetchone()[0]
            if count > max_entries:
                to_delete = count - max_entries
                conn.execute('''
                    DELETE FROM tasks
                    WHERE task_id IN (
                        SELECT task_id FROM tasks
                        ORDER BY date ASC
                        LIMIT ?
                    )
                ''', (to_delete,))
                conn.commit()

    def _row_to_task(self, row: sqlite3.Row) -> TaskRecord:
        """Convert database row to TaskRecord"""
        return TaskRecord(
            task_id=row['task_id'],
            date=row['date'],
            project_path=row['project_path'],
            task_description=row['task_description'],
            selected_agent=row['selected_agent'],
            model=row['model'] or '',
            attempts=row['attempts'],
            duration_seconds=row['duration_seconds'] or 0.0,
            changed_files=json.loads(row['changed_files']) if row['changed_files'] else [],
            tests_run=bool(row['tests_run']),
            test_results=row['test_results'] or '',
            result=row['result'],
            errors=row['errors'] or '',
            execution_log=row['execution_log'] or ''
        )


def get_database(db_path: str = None) -> HistoryDatabase:
    """Get database instance"""
    if db_path is None:
        db_path = str(Path(__file__).parent.parent.parent / "orchestrator.db")
    return HistoryDatabase(db_path)