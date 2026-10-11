"""Account pooling: one shared pool, checked connections, no transaction replay."""
import importlib.util
import unittest
from unittest.mock import MagicMock, Mock, patch

from backend.auth import AuthStore, AuthError
from backend.cloud_storage import CloudStorageError


@unittest.skipUnless(importlib.util.find_spec('psycopg_pool'), 'PostgreSQL pool not installed')
class AccountPoolTests(unittest.TestCase):
    def setUp(self):
        self.cloud = Mock()
        self.auth = AuthStore(cloud=self.cloud, mode='postgres')
        self.pool = MagicMock()
        self.connection = MagicMock()
        self.context = self.pool.connection.return_value
        self.context.__enter__.return_value = self.connection
        self.factory = patch('psycopg_pool.ConnectionPool', return_value=self.pool)
        self.constructor = self.factory.start()

    def tearDown(self):
        self.auth.close()
        self.factory.stop()

    def test_session_reads_share_one_pool_and_shutdown_closes_it(self):
        self.connection.execute.return_value.fetchone.return_value = None
        self.assertIsNone(self.auth.lookup('first-browser-token'))
        self.assertIsNone(self.auth.lookup('second-browser-token'))
        self.constructor.assert_called_once()
        self.assertEqual(self.pool.connection.call_count, 2)
        self.auth.close()
        self.pool.close.assert_called_once()

    def test_pool_checks_borrowed_connections_and_uses_safe_iam_connector(self):
        from psycopg.rows import dict_row
        self.auth._postgres_pool()
        params = self.constructor.call_args.kwargs
        self.assertEqual((params['min_size'], params['max_size']), (1, 4))
        self.assertIs(params['check'], self.constructor.check_connection)
        params['configure'](self.connection)
        self.assertIs(self.connection.row_factory, dict_row)
        self.cloud._connect.return_value = self.connection
        self.assertIs(params['connection_class'].connect(), self.connection)
        self.assertTrue(callable(self.cloud._connect.call_args.kwargs['_connector']))
        self.cloud._connect.side_effect = CloudStorageError('Safe connection failure')
        with self.assertRaisesRegex(CloudStorageError, 'Safe connection failure'):
            params['connection_class'].connect()

    def test_failed_write_exits_transaction_once_without_replaying_it(self):
        failure = RuntimeError('private SQL and password')
        self.connection.execute.side_effect = failure
        with self.assertRaises(AuthError) as caught:
            self.auth.logout('browser-token')
        self.assertEqual(caught.exception.status, 503)
        self.assertNotIn('private', caught.exception.message)
        self.assertEqual(self.connection.execute.call_count, 1)
        self.context.__exit__.assert_called_once()
        self.assertIs(self.context.__exit__.call_args.args[1], failure)

    def test_long_outage_restarts_recovery_without_a_new_request(self):
        self.auth._postgres_pool()
        callback = self.constructor.call_args.kwargs['reconnect_failed']
        self.pool.closed = False
        callback(self.pool)
        self.pool.check.assert_called_once_with()

    def test_shutdown_does_not_restart_recovery(self):
        self.auth._postgres_pool()
        callback = self.constructor.call_args.kwargs['reconnect_failed']
        self.pool.closed = True
        callback(self.pool)
        self.pool.check.assert_not_called()

    def test_duplicate_identity_keeps_conflict_response(self):
        import psycopg
        self.connection.execute.side_effect = psycopg.errors.UniqueViolation('private email')
        with self.assertRaises(AuthError) as caught:
            self.auth.logout('browser-token')
        self.assertEqual(caught.exception.status, 409)


if __name__ == '__main__':
    unittest.main()
