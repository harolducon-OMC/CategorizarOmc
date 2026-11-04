import json
import unittest

from core.help_assistant import HELP_SYSTEM, answer_question, answer_without_model


class FakeLLM:
    smart = "fake-model"

    def __init__(self):
        self.calls = []

    def text(self, system, user, **kwargs):
        self.calls.append((system, user, kwargs))
        return "Las claves se gestionan en Ajustes."


class HelpAssistantTests(unittest.TestCase):
    def test_answer_uses_platform_guide_and_bounded_chat_history(self):
        llm = FakeLLM()
        messages = [
            {"role": "user", "content": f"pregunta {index}"}
            for index in range(15)
        ]

        response = answer_question(llm, messages)

        self.assertEqual(response, "Las claves se gestionan en Ajustes.")
        self.assertIn("API key", llm.calls[0][0])
        self.assertIn("Cada estudio pertenece a una cuenta", llm.calls[0][0])
        payload = json.loads(llm.calls[0][1])
        self.assertEqual(len(payload["conversacion"]), 12)
        self.assertEqual(payload["conversacion"][-1]["content"], "pregunta 14")
        self.assertEqual(llm.calls[0][2]["max_tokens"], 1200)

    def test_answer_requires_a_user_question_as_the_last_message(self):
        with self.assertRaises(ValueError):
            answer_question(FakeLLM(), [{"role": "assistant", "content": "respuesta"}])

    def test_key_setup_question_can_be_answered_without_a_provider_key(self):
        answer = answer_without_model([
            {"role": "user", "content": "¿Cómo guardo mi API key?"},
        ])
        self.assertIn("Ajustes", answer)
        self.assertIn("cifrada", answer)

    def test_unknown_question_requires_the_configured_model(self):
        self.assertIsNone(answer_without_model([
            {"role": "user", "content": "¿Qué modelo se usó en mi última encuesta?"},
        ]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
