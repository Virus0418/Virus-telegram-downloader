"""Pending consumer must be running after start(), even with no leftover tasks.

direct_download persists download_state=pending and does not call
_consume_one_pending. On a cold boot bot_tasks.json is missing, so
recover_tasks() returns before it would have started the loop. These tests
drive DownloadBot.start() with a fake Telegram client — no live session.
"""

import asyncio
import contextlib
import os
import sys
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import module.bot as bot_mod
from module.bot import DownloadBot


async def _parked_pending_loop():
    """Stand-in for _pending_consumer_loop: counts a start, then waits."""
    await asyncio.Event().wait()


async def _noop_consume():
    return None


class _TaskLoop:
    """Records create_task names and runs every coro except the reply poller."""

    def __init__(self):
        self._loop = asyncio.get_running_loop()
        self.names = []
        self.tasks = []

    def create_task(self, coro, **kwargs):
        name = coro.cr_code.co_name
        self.names.append(name)
        if name == "update_reply_message":
            coro.close()
            fut = self._loop.create_future()
            fut.set_result(None)
            return fut
        task = self._loop.create_task(coro)
        self.tasks.append((name, task))
        return task


class _FakeTelegram:
    def __init__(self, *args, **kwargs):
        self.handlers = []

    async def start(self):
        return None

    async def stop(self):
        return None

    async def get_me(self):
        return SimpleNamespace(id=1001)

    async def get_chat(self, user_id):
        return SimpleNamespace(id=user_id)

    async def set_bot_commands(self, commands):
        return None

    async def send_message(self, *args, **kwargs):
        return SimpleNamespace(id=1)

    def add_handler(self, handler):
        self.handlers.append(handler)


def _app(loop):
    return SimpleNamespace(
        application_name="test",
        api_hash="hash",
        api_id=1,
        bot_token="token",
        session_file_path="/tmp",
        proxy=None,
        allowed_user_ids=[],
        chat_download_config=None,
        loop=loop,
    )


_real_sleep = asyncio.sleep


async def _fast_sleep(delay=0, result=None):
    """Collapse recover_tasks()'s 5s startup wait; still yield to the loop."""
    return await _real_sleep(0, result)


class PendingConsumerTests(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.proxy = _TaskLoop()
        self.bot = DownloadBot()
        self.bot.config_path = os.path.join("/tmp", "pending-consumer-no-such-bot.yaml")
        self.bot.app = _app(self.proxy)

    async def asyncTearDown(self):
        pending = [task for _, task in self.proxy.tasks if not task.done()]
        for task in pending:
            task.cancel()
        for task in pending:
            try:
                await task
            except asyncio.CancelledError:
                pass

    def _patches(self, running_tasks):
        return (
            patch.object(bot_mod.pyrogram, "Client", _FakeTelegram),
            patch.object(bot_mod, "_pending_consumer_loop", _parked_pending_loop),
            patch.object(bot_mod, "_consume_one_pending", _noop_consume),
            patch.object(bot_mod, "get_running_tasks", return_value=running_tasks),
            patch.object(bot_mod.asyncio, "sleep", _fast_sleep),
        )

    async def _start(self, running_tasks):
        with contextlib.ExitStack() as stack:
            for item in self._patches(running_tasks):
                stack.enter_context(item)
            await self.bot.start(
                self.bot.app,
                _FakeTelegram(),
                add_download_task=lambda *args, **kwargs: None,
                download_chat_task=lambda *args, **kwargs: None,
            )
            recover = await self._wait_done("recover_tasks")
        if recover.exception() is not None:
            raise recover.exception()

    async def _wait_done(self, name, timeout=2):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for task_name, task in self.proxy.tasks:
                if task_name == name and task.done():
                    return task
            await _real_sleep(0.01)
        self.fail(f"{name} did not finish; scheduled={self.proxy.names}")

    async def test_cold_start_with_no_leftover_tasks_starts_loop_once(self):
        await self._start([])

        self.assertEqual(self.proxy.names.count("_parked_pending_loop"), 1)
        self.assertLess(
            self.proxy.names.index("_parked_pending_loop"),
            self.proxy.names.index("recover_tasks"),
        )
        self.assertNotIn("_noop_consume", self.proxy.names)
        self.assertTrue(self.bot._pending_loop_started)

    async def test_leftover_tasks_do_not_start_a_second_loop_and_still_kick_consume(self):
        await self._start([{
            "task_id": 3,
            "download_state": "pending",
            "status": "running",
            "extra_data": {},
        }])

        self.assertEqual(self.proxy.names.count("_parked_pending_loop"), 1)
        self.assertEqual(self.proxy.names.count("_noop_consume"), 1)
        self.assertLess(
            self.proxy.names.index("_parked_pending_loop"),
            self.proxy.names.index("recover_tasks"),
        )
        self.assertEqual(self.bot.task_id, 3)

    async def test_ensure_helper_cannot_start_the_loop_twice(self):
        with patch.object(bot_mod, "_pending_consumer_loop", _parked_pending_loop):
            self.bot._ensure_pending_consumer_loop()
            self.bot._ensure_pending_consumer_loop()

        self.assertEqual(self.proxy.names, ["_parked_pending_loop"])
        self.assertTrue(self.bot._pending_loop_started)

    async def test_loop_consumes_a_pending_task_that_appears_after_an_idle_tick(self):
        """The loop start() arms is what drains a later save_task(pending)."""
        calls = {"n": 0}
        seen = []
        gate = asyncio.Event()

        async def stepped_sleep(delay=0, result=None):
            calls["n"] += 1
            gate.clear()
            await gate.wait()
            return result

        def get_pending():
            if calls["n"] <= 1:
                return []
            return [{"task_id": 9, "download_state": "pending"}]

        async def record_consume():
            seen.append(9)

        with patch.object(bot_mod.asyncio, "sleep", stepped_sleep), \
                patch("module.task_store.get_pending_tasks", get_pending), \
                patch.object(bot_mod, "_consume_one_pending", record_consume):
            task = asyncio.create_task(bot_mod._pending_consumer_loop())
            self.proxy.tasks.append(("_pending_consumer_loop", task))
            await _real_sleep(0)
            self.assertEqual(calls["n"], 1)
            self.assertEqual(seen, [])

            gate.set()
            await _real_sleep(0)
            self.assertEqual(calls["n"], 2)
            self.assertEqual(seen, [])

            gate.set()
            await _real_sleep(0)
            self.assertEqual(seen, [9])

            task.cancel()
            await task


if __name__ == "__main__":
    unittest.main()
