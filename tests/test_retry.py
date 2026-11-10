"""retry() waits between attempts and returns as soon as the last one fails."""

import os
import sys
import unittest
from unittest.mock import patch

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import pyrogram
import module.pyrogram_extension as ext
from module.pyrogram_extension import retry


class RetryTests(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        ext.logger.disable("module.pyrogram_extension")

    def tearDown(self):
        ext.logger.enable("module.pyrogram_extension")

    async def _sleeps_for(self, func, max_attempts=3, wait_second=15):
        sleeps = []

        async def fake_sleep(delay):
            sleeps.append(delay)

        with patch.object(ext.asyncio, "sleep", fake_sleep):
            result = await retry(
                func, args=("x",), max_attempts=max_attempts, wait_second=wait_second
            )
        return result, sleeps

    async def test_no_sleep_after_the_final_exception(self):
        async def boom(*args):
            raise RuntimeError("fail")

        result, sleeps = await self._sleeps_for(boom)
        self.assertIsNone(result)
        self.assertEqual(sleeps, [15, 15])

    async def test_no_sleep_after_the_final_flood_wait(self):
        async def flooded(*args):
            raise pyrogram.errors.exceptions.flood_420.FloodWait(30)

        result, sleeps = await self._sleeps_for(flooded, max_attempts=3, wait_second=15)
        self.assertIsNone(result)
        self.assertEqual(sleeps, [30, 30])

    async def test_success_on_a_later_attempt_stops_retrying(self):
        calls = {"n": 0}

        async def flaky(*args):
            calls["n"] += 1
            if calls["n"] < 2:
                raise RuntimeError("not yet")
            return "ok"

        result, sleeps = await self._sleeps_for(flaky, max_attempts=3, wait_second=7)
        self.assertEqual(result, "ok")
        self.assertEqual(calls["n"], 2)
        self.assertEqual(sleeps, [7])


if __name__ == "__main__":
    unittest.main()
