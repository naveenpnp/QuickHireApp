import os
import sys
import unittest
from datetime import datetime, date

# Set paths
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BACKEND_DIR, '..'))
DATABASE_DIR = os.path.join(PROJECT_ROOT, 'database')

if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
if DATABASE_DIR not in sys.path:
    sys.path.insert(0, DATABASE_DIR)

from init_db import init_db
from models import UserModel, JobModel, ApplicationModel, AssignmentModel, ReviewModel, TransactionModel, db_cursor
from services.payment_service import calculate_payment
from services.reliability_service import update_worker_on_completion, update_worker_on_noshow, recalculate_user_rating

class QuickHireTestSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Force re-init test database
        init_db(force=True)

    def test_01_users_seeded(self):
        arun = UserModel.get_by_email('arun@gmail.com')
        rahul = UserModel.get_by_email('rahul@gmail.com')
        self.assertIsNotNone(arun)
        self.assertIsNotNone(rahul)
        self.assertEqual(arun['wallet_balance'], 5000.0)
        self.assertEqual(rahul['wallet_balance'], 5000.0)
        self.assertEqual(arun['reliability_score'], 100)

    def test_02_payment_calculation_cases(self):
        # Case 1: On-time full duration (10:00 to 16:00, 6 hours, ₹900)
        c1 = calculate_payment("10:00", "16:00", "10:00", "16:00", 900.0)
        self.assertEqual(c1['calculated_payment'], 900.0)
        self.assertEqual(c1['scheduled_hours'], 6.0)
        self.assertEqual(c1['actual_hours'], 6.0)
        self.assertFalse(c1['late'])

        # Case 2: Late arrival (10:30 start), but stayed extra (16:30 end, 6 hours worked)
        c2 = calculate_payment("10:00", "16:00", "10:30", "16:30", 900.0)
        self.assertEqual(c2['calculated_payment'], 900.0)
        self.assertEqual(c2['actual_hours'], 6.0)
        self.assertTrue(c2['late'])

        # Case 3: Late arrival (10:30 start) and left at scheduled end (16:00 end, 5.5 hours worked)
        c3 = calculate_payment("10:00", "16:00", "10:30", "16:00", 900.0)
        self.assertEqual(c3['scheduled_hours'], 6.0)
        self.assertEqual(c3['actual_hours'], 5.5)
        self.assertEqual(c3['calculated_payment'], 825.0) # 900 * 5.5 / 6.0 = 825.0
        self.assertTrue(c3['late'])

    def test_03_reliability_rules(self):
        # Create a test worker
        test_email = "testworker@gmail.com"
        with db_cursor(commit=True) as cur:
            cur.execute("DELETE FROM users WHERE email = ?", (test_email,))
        
        uid = UserModel.create("Test Worker", test_email, "dummyhash", "Trichy", "Driving")
        worker = UserModel.get_by_id(uid)
        self.assertEqual(worker['reliability_score'], 100)

        # On-time completion: 100 -> 100 (capped at 100), completed_jobs = 1
        update_worker_on_completion(uid, is_late=False)
        w1 = UserModel.get_by_id(uid)
        self.assertEqual(w1['completed_jobs'], 1)
        self.assertEqual(w1['reliability_score'], 100)

        # Late completion: completed_jobs +1 -> 2, score: 100 + 1 - 2 -> 99
        update_worker_on_completion(uid, is_late=True)
        w2 = UserModel.get_by_id(uid)
        self.assertEqual(w2['completed_jobs'], 2)
        self.assertEqual(w2['late_arrivals'], 1)
        self.assertEqual(w2['reliability_score'], 99)

        # No-show: score: 99 - 10 -> 89, no_shows = 1
        update_worker_on_noshow(uid)
        w3 = UserModel.get_by_id(uid)
        self.assertEqual(w3['no_shows'], 1)
        self.assertEqual(w3['reliability_score'], 89)

    def test_04_reviews_and_average_rating(self):
        arun = UserModel.get_by_email('arun@gmail.com')
        rahul = UserModel.get_by_email('rahul@gmail.com')
        
        # Clear any prior reviews for clean testing
        with db_cursor(commit=True) as cur:
            cur.execute("DELETE FROM reviews WHERE reviewed_user_id = ?", (arun['id'],))

        # Get a demo job
        jobs = JobModel.get_all()
        job_id = jobs[0]['id']

        # Rahul reviews Arun with 5 stars
        ReviewModel.create(job_id, rahul['id'], arun['id'], 5, "Excellent host!")
        recalculate_user_rating(arun['id'])
        arun_updated = UserModel.get_by_id(arun['id'])
        self.assertEqual(arun_updated['rating'], 5.0)

        # Add a 4 star review
        ReviewModel.create(job_id, rahul['id'], arun['id'], 4, "Very good experience")
        recalculate_user_rating(arun['id'])
        arun_updated2 = UserModel.get_by_id(arun['id'])
        self.assertEqual(arun_updated2['rating'], 4.5)

if __name__ == '__main__':
    unittest.main()
