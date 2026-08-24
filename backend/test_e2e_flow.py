import os
import sys
import unittest
from datetime import datetime, date, timedelta

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
from app import create_app

class QuickHireE2ETest(unittest.TestCase):
    def setUp(self):
        init_db(force=True)
        self.app = create_app()
        self.client = self.app.test_client()

    def test_full_successful_flow(self):
        # 1. Check initial balances
        arun = UserModel.get_by_email('arun@gmail.com')
        rahul = UserModel.get_by_email('rahul@gmail.com')
        self.assertEqual(arun['wallet_balance'], 5000.0)
        self.assertEqual(arun['secured_balance'], 0.0)
        self.assertEqual(rahul['wallet_balance'], 5000.0)

        # 2. Arun Posts a Job for ₹900 (1 worker)
        with self.client.session_transaction() as sess:
            sess['user_id'] = arun['id']
            sess['user_name'] = arun['name']
            sess['user_email'] = arun['email']

        post_res = self.client.post('/post-job', data={
            'title': 'Urgent Stage Coordinator',
            'category': 'Event Work',
            'description': 'Help manage event stage and guest coordination',
            'location': 'Trichy',
            'job_date': (date.today() + timedelta(days=1)).strftime("%Y-%m-%d"),
            'start_time': '10:00',
            'end_time': '16:00',
            'required_workers': '1',
            'payment': '900',
            'urgent': '1'
        }, follow_redirects=True)
        self.assertEqual(post_res.status_code, 200)

        # Verify Arun's balance is deducted and placed into escrow
        arun = UserModel.get_by_id(arun['id'])
        self.assertEqual(arun['wallet_balance'], 4100.0)
        self.assertEqual(arun['secured_balance'], 900.0)

        # Get the new job
        with db_cursor() as cur:
            cur.execute("SELECT id FROM jobs WHERE poster_id = ? AND title = 'Urgent Stage Coordinator'", (arun['id'],))
            job_id = cur.fetchone()[0]

        # 3. Rahul Applies for the Job
        with self.client.session_transaction() as sess:
            sess['user_id'] = rahul['id']
            sess['user_name'] = rahul['name']
            sess['user_email'] = rahul['email']

        apply_res = self.client.post(f'/apply/{job_id}', follow_redirects=True)
        self.assertEqual(apply_res.status_code, 200)

        app_record = ApplicationModel.get_by_job_and_worker(job_id, rahul['id'])
        self.assertIsNotNone(app_record)
        self.assertEqual(app_record['status'], 'Applied')

        # 4. Arun Selects Rahul
        with self.client.session_transaction() as sess:
            sess['user_id'] = arun['id']

        select_res = self.client.post(f'/select-worker/{app_record["id"]}', follow_redirects=True)
        self.assertEqual(select_res.status_code, 200)

        assignment = AssignmentModel.get_by_job_and_worker(job_id, rahul['id'])
        self.assertIsNotNone(assignment)
        self.assertEqual(assignment['status'], 'Assigned')

        # 5. Rahul Starts the Job (Simulating 30m Late: 10:30)
        with self.client.session_transaction() as sess:
            sess['user_id'] = rahul['id']

        today_str = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
        start_res = self.client.post(f'/start-job/{assignment["id"]}', data={
            'custom_start_time': f'{today_str} 10:30:00'
        }, follow_redirects=True)
        self.assertEqual(start_res.status_code, 200)

        assign_started = AssignmentModel.get_by_id(assignment['id'])
        self.assertEqual(assign_started['status'], 'In Progress')
        self.assertEqual(assign_started['late'], 1)

        # 6. Rahul Completes the Job (Simulating Case 2: Stayed until 16:30, full 6.0 hours worked)
        complete_res = self.client.post(f'/complete-job/{assignment["id"]}', data={
            'custom_end_time': f'{today_str} 16:30:00'
        }, follow_redirects=True)
        self.assertEqual(complete_res.status_code, 200)

        assign_done = AssignmentModel.get_by_id(assignment['id'])
        self.assertEqual(assign_done['status'], 'Awaiting Confirmation')
        self.assertEqual(assign_done['calculated_payment'], 900.0)
        self.assertEqual(assign_done['actual_hours'], 6.0)

        # 7. Arun Confirms Job Completion
        with self.client.session_transaction() as sess:
            sess['user_id'] = arun['id']

        confirm_res = self.client.post(f'/confirm-job/{assignment["id"]}', follow_redirects=True)
        self.assertEqual(confirm_res.status_code, 200)

        # Verify Balances after Escrow Payout
        arun = UserModel.get_by_id(arun['id'])
        rahul = UserModel.get_by_id(rahul['id'])
        self.assertEqual(arun['secured_balance'], 0.0)
        self.assertEqual(arun['wallet_balance'], 4100.0)
        self.assertEqual(rahul['wallet_balance'], 5900.0) # 5000 + 900

        # Verify Rahul Reliability and completed count
        self.assertEqual(rahul['completed_jobs'], 1)
        self.assertEqual(rahul['late_arrivals'], 1)
        self.assertEqual(rahul['reliability_score'], 99) # 100 + 1 - 2

        # 8. Arun reviews Rahul
        rev_res = self.client.post(f'/review/{job_id}/{rahul["id"]}', data={
            'rating': '5',
            'review': 'Great work!'
        }, follow_redirects=True)
        self.assertEqual(rev_res.status_code, 200)

        rahul = UserModel.get_by_id(rahul['id'])
        self.assertEqual(rahul['rating'], 5.0)

    def test_noshow_flow(self):
        arun = UserModel.get_by_email('arun@gmail.com')
        rahul = UserModel.get_by_email('rahul@gmail.com')

        # Arun posts another job for ₹500
        with self.client.session_transaction() as sess:
            sess['user_id'] = arun['id']

        self.client.post('/post-job', data={
            'title': 'Shop Hand',
            'category': 'Shop Assistant',
            'description': 'Unload crates',
            'location': 'Trichy',
            'job_date': (date.today() + timedelta(days=1)).strftime("%Y-%m-%d"),
            'start_time': '14:00',
            'end_time': '18:00',
            'required_workers': '1',
            'payment': '500',
            'urgent': '0'
        })

        with db_cursor() as cur:
            cur.execute("SELECT id FROM jobs WHERE poster_id = ? AND title = 'Shop Hand'", (arun['id'],))
            job_id = cur.fetchone()[0]

        # Rahul applies
        ApplicationModel.create(job_id, rahul['id'])
        app = ApplicationModel.get_by_job_and_worker(job_id, rahul['id'])

        # Arun selects Rahul
        with self.client.session_transaction() as sess:
            sess['user_id'] = arun['id']
            sess['user_name'] = arun['name']
            sess['user_email'] = arun['email']

        select_res = self.client.post(f'/select-worker/{app["id"]}', follow_redirects=True)
        self.assertEqual(select_res.status_code, 200)

        assignment = AssignmentModel.get_by_job_and_worker(job_id, rahul['id'])
        self.assertIsNotNone(assignment)

        # Arun marks No-Show
        noshow_res = self.client.post(f'/no-show/{assignment["id"]}', follow_redirects=True)
        self.assertEqual(noshow_res.status_code, 200)

        # Worker gets 0, reliability drops by 10
        rahul = UserModel.get_by_id(rahul['id'])
        self.assertEqual(rahul['no_shows'], 1)
        self.assertEqual(rahul['reliability_score'], 90)

        # Job is reopened to Available
        job = JobModel.get_by_id(job_id)
        self.assertEqual(job['status'], 'Available')

if __name__ == '__main__':
    unittest.main()
