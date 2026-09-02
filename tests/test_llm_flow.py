import unittest
from unittest.mock import AsyncMock, patch

import llm


class AnalyzeFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_reports_run_sequentially_with_one_second_gaps(self):
        events = []
        progress_events = []
        usage = {"input": 1, "output": 1, "total": 2}

        def fake_gemini(system, _user):
            events.append(system)
            return {"ok": True}, usage.copy()

        async def immediate_to_thread(function, *args):
            return function(*args)

        async def capture_progress(event):
            progress_events.append(event.copy())

        with (
            patch.object(llm, "_gemini", side_effect=fake_gemini),
            patch.object(llm.asyncio, "to_thread", side_effect=immediate_to_thread),
            patch.object(llm.asyncio, "sleep", new=AsyncMock()) as sleep,
        ):
            result = await llm.analyze_all("örnek görüşme", progress=capture_progress)

        self.assertEqual(
            events,
            [llm.prompts.SYSTEM_HASTA, llm.prompts.SYSTEM_DOKTOR, llm.prompts.SYSTEM_YONETIM],
        )
        self.assertEqual([call.args for call in sleep.await_args_list], [(1,), (1,)])
        self.assertEqual(
            [(e["step"], e["status"], e["percent"]) for e in progress_events],
            [
                ("hasta", "running", 0),
                ("hasta", "completed", 33),
                ("doktor", "running", 33),
                ("doktor", "completed", 67),
                ("yonetim", "running", 67),
                ("yonetim", "completed", 100),
            ],
        )
        self.assertEqual(result["usage"]["calls"], 3)
        self.assertEqual(result["usage"]["total"], 6)


if __name__ == "__main__":
    unittest.main()
