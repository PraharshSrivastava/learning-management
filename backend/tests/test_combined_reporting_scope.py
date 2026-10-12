"""Execute the production scope predicate on synthetic rows without a DB driver.

SQLite supports this predicate after removing PostgreSQL's ::text cast.
Full reporting integration remains covered by test_observer_reporting_postgres.
"""
import sqlite3
import unittest

from app.schemas.reporting_scope import EmployeePerformanceScope, owner_filter


class CombinedScopeTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.addCleanup(self.db.close)
        self.db.executescript("""
            CREATE TABLE employees(employee_id TEXT, directory_uuid TEXT, hub_user_id INTEGER,
                status TEXT, directory_status TEXT, department TEXT);
            CREATE TABLE courses(course_id TEXT);
            CREATE TABLE course_assignments(assignment_id TEXT, employee_id TEXT, course_id TEXT);
            CREATE TABLE lms_departments(department_id TEXT, name TEXT, active BOOLEAN, source TEXT);
            CREATE TABLE hod_department_access(hod_employee_id TEXT, identity_key TEXT,
                department_id TEXT, active BOOLEAN);
            CREATE TABLE course_observer_grants(observer_employee_id TEXT, identity_key TEXT,
                course_id TEXT, active BOOLEAN);
            CREATE TABLE course_observer_employees(observer_employee_id TEXT, course_id TEXT,
                employee_id TEXT, identity_key TEXT, phase TEXT);
            CREATE TABLE course_observer_departments(observer_employee_id TEXT, course_id TEXT,
                department_id TEXT, phase TEXT);
            INSERT INTO employees VALUES
                ('viewer','uuid-viewer',NULL,'active','active','HR'),
                ('a','uuid-a',NULL,'active','active','Finance'),
                ('b','uuid-b',NULL,'active','active','Ops'),
                ('c','uuid-c',NULL,'active','active','Finance');
            INSERT INTO courses VALUES ('one'),('two');
            INSERT INTO course_assignments VALUES
                ('one-a','a','one'),('one-b','b','one'),('one-c','c','one'),
                ('two-a','a','two'),('two-b','b','two'),('two-c','c','two');
            INSERT INTO lms_departments VALUES ('finance','Finance',TRUE,'directory');
            INSERT INTO hod_department_access VALUES ('viewer','directory:uuid-viewer','finance',TRUE);
            INSERT INTO course_observer_grants VALUES ('viewer','directory:uuid-viewer','one',TRUE);
            INSERT INTO course_observer_employees VALUES
                ('viewer','one','a','directory:uuid-a','active'),
                ('viewer','one','b','directory:uuid-b','active');
            INSERT INTO course_observer_departments VALUES ('viewer','one','finance','active');
        """)

    def rows(self, view):
        predicate, params = owner_filter(EmployeePerformanceScope('viewer', 'directory:uuid-viewer', view))
        # Dialect-only adaptation; authorization logic is imported unchanged.
        predicate = predicate.removesuffix(' AND ').replace('::text', '')
        return self.db.execute(
            'SELECT ca.assignment_id, e.employee_id FROM course_assignments ca '
            'JOIN employees e USING(employee_id) JOIN courses c USING(course_id) '
            'WHERE ' + predicate + ' ORDER BY ca.assignment_id', params).fetchall()

    def ids(self, view):
        return {row[0] for row in self.rows(view)}

    def test_union_preserves_course_bound_scope_and_counts_overlap_once(self):
        hod = self.ids('my_departments')
        observed = self.ids('observed')
        self.assertEqual(hod, {'one-a', 'one-c', 'two-a', 'two-c'})
        self.assertEqual(observed, {'one-a', 'one-b', 'one-c'})
        combined = self.rows('combined')
        self.assertEqual({row[0] for row in combined}, hod | observed)
        self.assertEqual(len(combined), 5)
        self.assertEqual(len({row[1] for row in combined}), 3)
        self.assertNotIn('two-b', self.ids('combined'))

    def test_observer_revocation_retains_hod_contribution(self):
        self.db.execute('UPDATE course_observer_grants SET active=FALSE')
        self.assertEqual(self.ids('observed'), set())
        self.assertEqual(self.ids('combined'), self.ids('my_departments'))
        self.assertEqual(len(self.rows('combined')), 4)

    def test_hod_revocation_retains_observer_contribution(self):
        self.db.execute('UPDATE hod_department_access SET active=FALSE')
        self.assertEqual(self.ids('my_departments'), set())
        self.assertEqual(self.ids('combined'), self.ids('observed'))
        self.assertEqual(len(self.rows('combined')), 3)

    def test_no_roles_means_no_combined_rows(self):
        self.db.execute('UPDATE hod_department_access SET active=FALSE')
        self.db.execute('UPDATE course_observer_grants SET active=FALSE')
        self.assertEqual(self.rows('combined'), [])

    def test_recycled_viewer_identity_invalidates_both_contributions(self):
        self.db.execute("UPDATE employees SET directory_uuid='replacement' WHERE employee_id='viewer'")
        self.assertEqual(self.rows('combined'), [])

    def test_inactive_viewer_invalidates_both_contributions(self):
        self.db.execute("UPDATE employees SET directory_status='inactive' WHERE employee_id='viewer'")
        self.assertEqual(self.rows('combined'), [])

    def test_pending_subject_is_not_visible_outside_hod_scope(self):
        self.db.execute("UPDATE course_observer_employees SET phase='pending' WHERE employee_id='b'")
        self.assertNotIn('one-b', self.ids('combined'))

    def test_recycled_subject_identity_is_not_visible_through_explicit_grant(self):
        self.db.execute("UPDATE employees SET directory_uuid='replacement' WHERE employee_id='b'")
        self.assertNotIn('one-b', self.ids('combined'))


if __name__ == '__main__':
    unittest.main()
