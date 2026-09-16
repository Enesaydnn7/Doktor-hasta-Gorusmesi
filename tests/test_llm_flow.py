import threading
import unittest
from unittest.mock import patch

import llm


class AnalyzeFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_reports_and_comed_draft_run_in_parallel(self):
        events = []
        progress_events = []
        usage = {"input": 1, "output": 1, "total": 2}
        barrier = threading.Barrier(4, timeout=3)

        def fake_gemini(system, _user):
            events.append(system)
            barrier.wait()
            return {"ok": True}, usage.copy()

        async def capture_progress(event):
            progress_events.append(event.copy())

        with (
            patch.object(llm, "_gemini", side_effect=fake_gemini),
        ):
            result = await llm.analyze_all("örnek görüşme", progress=capture_progress)

        self.assertCountEqual(events, [
            llm.prompts.SYSTEM_HASTA,
            llm.prompts.SYSTEM_DOKTOR,
            llm.prompts.SYSTEM_YONETIM,
            llm.prompts.SYSTEM_COMED,
        ])
        running = [event for event in progress_events if event["status"] == "running"]
        completed = [event for event in progress_events if event["status"] == "completed"]
        self.assertCountEqual([event["step"] for event in running], ["hasta", "doktor", "yonetim"])
        self.assertEqual(sorted(event["percent"] for event in completed), [33, 67, 100])
        self.assertEqual(result["comed"], {"ok": True})
        self.assertEqual(result["usage"]["calls"], 4)
        self.assertTrue(result["usage"]["parallel"])
        self.assertEqual(result["usage"]["total"], 8)


if __name__ == "__main__":
    unittest.main()
