"""Check the increased allowance while preserving reservation and rate guards."""
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import agent


class UsageLimitTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root=patch.object(agent,'ROOT',Path(self.directory.name))
        self.root.start()
        self.addCleanup(self.root.stop)

    def seed(self,count=1,tokens=0,status='complete',age=120):
        with agent.db() as c:
            c.executemany('INSERT INTO turns VALUES (?,?,?,?)',
                [(str(i),time.time()-age,status,tokens if i==0 else 0) for i in range(count)])

    def test_previously_blocked_usage_has_room_and_history_is_retained(self):
        self.seed(count=24,tokens=134787)
        turn=agent.reserve_turn()
        with agent.db() as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM turns').fetchone()[0],25)
            self.assertEqual(c.execute('SELECT status FROM turns WHERE id=?',(turn,)).fetchone()[0],'pending')

    def test_daily_turn_and_token_caps_still_block(self):
        for count,tokens in ((100,0),(1,930001)):
            with self.subTest(count=count,tokens=tokens):
                with agent.db() as c:c.execute('DELETE FROM turns')
                self.seed(count=count,tokens=tokens)
                with self.assertRaises(ValueError):agent.reserve_turn()

    def test_reservation_fits_exact_token_boundary(self):
        self.seed(tokens=agent.DAILY_TOKEN_LIMIT-agent.TURN_TOKEN_RESERVATION)
        self.assertTrue(agent.reserve_turn())
        with self.assertRaises(ValueError):agent.reserve_turn()

    def test_minute_and_inflight_guards_remain_active(self):
        self.seed(count=4,age=0)
        with self.assertRaises(ValueError):agent.reserve_turn()
        with agent.db() as c:c.execute('DELETE FROM turns')
        self.seed(count=14,status='pending')
        with self.assertRaises(ValueError):agent.reserve_turn()


if __name__=='__main__':unittest.main()
