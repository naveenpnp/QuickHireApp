import os
import sys
import unittest

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BACKEND_DIR, '..'))
DATABASE_DIR = os.path.join(PROJECT_ROOT, 'database')

if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
if DATABASE_DIR not in sys.path:
    sys.path.insert(0, DATABASE_DIR)

from init_db import init_db
from models import UserModel, JobModel
from app import create_app

class RouteVerificationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.app = create_app()
        cls.client = cls.app.test_client()

    def test_public_routes(self):
        client = self.app.test_client()
        routes = ['/', '/login', '/register', '/jobs', '/static/css/style.css', '/static/js/script.js', '/static/images/logo.svg']
        for route in routes:
            with self.subTest(route=route):
                res = client.get(route)
                self.assertEqual(res.status_code, 200, f"Route {route} returned status {res.status_code}")

    def test_authenticated_routes(self):
        user = UserModel.get_by_email('arun@gmail.com')
        with self.client.session_transaction() as sess:
            sess['user_id'] = user['id']
            sess['user_name'] = user['name']
            sess['user_email'] = user['email']

        auth_routes = [
            '/dashboard',
            '/post-job',
            '/my-jobs',
            '/applications',
            '/wallet',
            '/profile',
            '/reviews',
            '/job/1'
        ]
        for route in auth_routes:
            with self.subTest(route=route):
                res = self.client.get(route)
                self.assertEqual(res.status_code, 200, f"Authenticated route {route} returned status {res.status_code}")

if __name__ == '__main__':
    unittest.main()
