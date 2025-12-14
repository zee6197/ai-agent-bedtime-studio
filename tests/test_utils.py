import os
import unittest

import main


class TestUtils(unittest.TestCase):
    def test_summarize_request_contains_inputs(self):
        req = main.StoryRequest(
            description="Space adventure",
            characters="Fox, Rabbit",
            tone="Playful",
            lesson="Teamwork",
            length_label="short",
        )
        summary = main.summarize_request(req)
        self.assertIn("Space adventure", summary)
        self.assertIn("Fox, Rabbit", summary)
        self.assertIn("short", summary)

    def test_parse_judge_response_handles_markdown_wrapper(self):
        raw = """```json
{
  "verdict": "approve",
  "summary": "All good",
  "issues": [],
  "suggestions": []
}
```"""
        data = main._parse_judge_response(raw)
        self.assertEqual(data["verdict"], "approve")
        self.assertEqual(data["summary"], "All good")

    def test_parse_judge_response_handles_bad_json(self):
        raw = "not json at all"
        data = main._parse_judge_response(raw)
        self.assertEqual(data["verdict"], "revise")
        self.assertTrue(data["issues"])

    def test_normalize_judge_report_defaults(self):
        report = main._normalize_judge_report({"verdict": "maybe"})
        self.assertEqual(report["verdict"], "revise")
        self.assertIsInstance(report["issues"], list)
        self.assertIsInstance(report["suggestions"], list)

    def test_config_from_env_parses_values(self):
        os.environ["STORY_TEMP"] = "0.5"
        os.environ["JUDGE_TEMP"] = "0.1"
        os.environ["MAX_STORY_ATTEMPTS"] = "3"
        cfg = main.Config.from_env()
        self.assertEqual(cfg.storyteller_temp, 0.5)
        self.assertEqual(cfg.judge_temp, 0.1)
        self.assertEqual(cfg.max_attempts, 3)

    def test_noise_detection_handles_numeric_strings(self):
        self.assertTrue(main._looks_like_noise("12345"))
        self.assertTrue(main._looks_like_noise("!!"))
        self.assertFalse(main._looks_like_noise("Brave otter"))
        self.assertTrue(main._looks_like_noise("asdada"))


if __name__ == "__main__":
    unittest.main()
