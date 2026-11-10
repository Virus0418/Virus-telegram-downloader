"""Forwarded media is downloaded from the bot-chat copy immediately.

The user client must not be asked for the source channel, and the
"Direct download..." reply must not wait on that fetch.
"""

import asyncio
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import module.bot as bot_mod


def _media_message(*, forwarded=True):
    message = SimpleNamespace(
        id=8801,
        media=SimpleNamespace(value="document"),
        document=SimpleNamespace(file_id="bot-copy-file", file_name="a.bin"),
        from_user=SimpleNamespace(id=4242),
        forward_from_chat=None,
        forward_from_message_id=None,
    )
    if forwarded:
        message.forward_from_chat = SimpleNamespace(
            id=-1009876543210,
            title="Source Channel",
            username="source_channel",
        )
        message.forward_from_message_id = 77
    return message


class _RecordingNode:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.task_id_display = "1110-1"
        self.source_chat_title = ""
        self.source_chat_id = 0
        self.source_message_id = 0
        self.is_running = False


class ForwardMediaTests(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.bot = bot_mod._bot
        self._saved = {
            "client": self.bot.client,
            "bot": self.bot.bot,
            "task_id": self.bot.task_id,
            "cached": dict(self.bot._cached_messages),
            "nodes": dict(self.bot.task_node),
        }
        self.bot.task_id = 1000
        self.bot._cached_messages.clear()
        self.order = []
        self.saved_tasks = []

    async def asyncTearDown(self):
        self.bot.client = self._saved["client"]
        self.bot.bot = self._saved["bot"]
        self.bot.task_id = self._saved["task_id"]
        self.bot._cached_messages.clear()
        self.bot._cached_messages.update(self._saved["cached"])
        self.bot.task_node.clear()
        self.bot.task_node.update(self._saved["nodes"])

    def _install_clients(self):
        async def get_messages(*args, **kwargs):
            self.order.append(("get_messages", args, kwargs))
            return SimpleNamespace(
                id=77,
                media=SimpleNamespace(value="document"),
                document=SimpleNamespace(file_id="source-original"),
                chat=SimpleNamespace(id=-1009876543210, title="Source Channel"),
            )

        async def parse_link(*args, **kwargs):
            self.order.append(("parse_link", args, kwargs))
            return -1009876543210, 77, 0

        async def bot_send_message(chat_id, text, reply_to_message_id=None, **kwargs):
            self.order.append(("reply", text, chat_id, reply_to_message_id))
            return SimpleNamespace(id=501)

        async def handler_send_message(*args, **kwargs):
            self.order.append(("handler_send", args, kwargs))
            return SimpleNamespace(id=1)

        self.bot.client = SimpleNamespace(get_messages=get_messages)
        self.bot.bot = SimpleNamespace(send_message=bot_send_message)
        self.handler = SimpleNamespace(
            get_messages=get_messages,
            send_message=handler_send_message,
        )

        def save_task(**kwargs):
            self.saved_tasks.append(kwargs)

        return (
            patch.object(bot_mod, "parse_link", parse_link),
            patch.object(bot_mod, "save_task", save_task),
            patch.object(bot_mod, "TaskNode", _RecordingNode),
        )

    async def test_forwarded_file_replies_then_queues_the_bot_copy(self):
        message = _media_message(forwarded=True)
        patches = self._install_clients()
        with patches[0], patches[1], patches[2]:
            await bot_mod.download_forward_media(self.handler, message)
            # A background original-fetch would be scheduled before return.
            await asyncio.sleep(0)
            await asyncio.sleep(0)

        self.assertEqual(
            self.order,
            [("reply", "Direct download...", 4242, 8801)],
        )
        self.assertEqual(len(self.saved_tasks), 1)
        saved = self.saved_tasks[0]
        self.assertEqual(saved["chat_id"], 4242)
        self.assertEqual(saved["from_user_id"], 4242)
        self.assertEqual(saved["task_type"], "direct")
        self.assertEqual(saved["extra_data"]["message_id"], 8801)
        self.assertNotIn("source_chat_id", saved["extra_data"])
        self.assertNotIn("source_message_id", saved["extra_data"])

        cached = self.bot._cached_messages[saved["task_id"]]
        self.assertIs(cached, message)
        node = self.bot.task_node[saved["task_id"]]
        self.assertEqual(node.chat_id, 4242)
        self.assertEqual(node.source_chat_id, 0)
        self.assertEqual(node.source_message_id, 0)
        self.assertTrue(node.is_running)

    async def test_upload_without_forward_header_still_uses_that_message(self):
        message = _media_message(forwarded=False)
        patches = self._install_clients()
        with patches[0], patches[1], patches[2]:
            await bot_mod.download_forward_media(self.handler, message)

        self.assertEqual(self.order[0][0], "reply")
        self.assertNotIn("get_messages", [item[0] for item in self.order])
        self.assertIs(self.bot._cached_messages[self.saved_tasks[0]["task_id"]], message)

    async def test_message_without_media_does_not_fetch_or_queue(self):
        message = _media_message(forwarded=True)
        message.media = None
        patches = self._install_clients()
        with patches[0], patches[1], patches[2]:
            await bot_mod.download_forward_media(self.handler, message)

        self.assertEqual(len(self.order), 1)
        self.assertEqual(self.order[0][0], "handler_send")
        self.assertEqual(self.saved_tasks, [])
        self.assertEqual(self.bot._cached_messages, {})


if __name__ == "__main__":
    unittest.main()
