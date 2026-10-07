import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import conversation_prompt_eval as evaluator


class TestConversationPromptPlan(unittest.TestCase):
    def test_offline_plan_has_28_counterbalanced_requests(self):
        with patch("socket.socket.connect", side_effect=AssertionError("Network forbidden")):
            plan = evaluator.prepare_plan()
        self.assertEqual(plan["status"], "offline_draft_no_live_calls")
        self.assertEqual(plan["planned_requests"], 28)
        first_arms = {}
        for index in range(0, 28, 2):
            a, b = plan["requests"][index:index + 2]
            self.assertEqual((a["case_id"], a["trial"]), (b["case_id"], b["trial"]))
            first_arms.setdefault(a["case_id"], []).append(a["variant"])
            left, right = json.loads(json.dumps(a["request"])), json.loads(json.dumps(b["request"]))
            left["messages"][0]["content"] = right["messages"][0]["content"] = "controlled difference"
            self.assertEqual(left, right)
        self.assertTrue(all(len(set(arms)) == 2 for arms in first_arms.values()))

    def test_voice_and_date_preserved_without_forced_topic_initiation(self):
        plan = evaluator.prepare_plan()
        prompt = plan["variants"]["B_conversation_first"]
        for text in ("あいちゃん", "自然な関西弁", "会話全体", "直近の発言", "訂正", "2026年10月07日", "20時00分"):
            self.assertIn(text, prompt)
        self.assertNotIn("時々関西の食べ物や文化について話したがる", prompt)
        self.assertNotIn("時間帯や季節に応じた話題を提案する", prompt)
        self.assertEqual(plan["sdk_transport"]["max_retries"], 0)
        self.assertFalse(plan["sdk_transport"]["follow_redirects"])

    def test_required_multiturn_checkpoints_and_model_settings(self):
        plan = evaluator.prepare_plan()
        cases = {row["case_id"]: row for row in plan["requests"]}
        self.assertEqual(set(cases), {"greeting", "casual_followup", "restaurant_unspecified",
            "restaurant_specified", "current_weather_reference", "location_correction",
            "recall_budget_after_correction"})
        self.assertEqual(cases["greeting"]["request"]["messages"][-1]["content"], "やっほい")
        self.assertEqual(cases["restaurant_unspecified"]["request"]["messages"][-1]["content"], "おすすめの飲食店ある?")
        for row in plan["requests"]:
            request = row["request"]
            self.assertEqual(request["model"], "openai/gpt-oss-20b")
            self.assertEqual(request["temperature"], 0.7)
            self.assertEqual(request["max_tokens"], 1000)
            self.assertEqual(request["reasoning_effort"], "medium")
            self.assertEqual(request["tool_choice"], "auto")
            self.assertEqual(sum(message["role"] == "system" for message in request["messages"]), 1)


if __name__ == "__main__":
    unittest.main()
