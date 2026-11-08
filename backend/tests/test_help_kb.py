import unittest

from core import help_kb

SHOULD_MATCH = [
    ("¿Cómo subo mi encuesta?", "importar-archivo"),
    ("como cargo un archivo excel", "importar-archivo"),
    ("¿Dónde guardo mi API key?", "api-key"),
    ("quiero cambiar mi clave", "api-key"),
    ("¿Cómo categorizo por temas?", "categorizar-temas"),
    ("que significa Otros y Ninguna", "etiquetas-especiales"),
    ("diferencia entre TOM espontaneo y ayudado", "awareness-tipos"),
    ("¿Awareness usa lo que categoricé?", "awareness-fuente"),
    ("como escribo los codigos P1 P2", "awareness-codigos"),
    ("no me sale la columna P7", "awareness-codigos"),
    ("por que la base es diferente", "awareness-base"),
    ("como descargo el grafico", "descargas"),
    ("como corrijo etiquetas", "revisar-corregir"),
    ("¿Cómo mido la calidad de la categorización?", "calidad"),
    ("me sale demasiadas solicitudes", "limites-uso"),
    ("¿protegen mis datos personales?", "privacidad"),
    ("como elimino un estudio", "eliminar-estudio"),
    ("insy usa ia?", "insy-ia"),
    ("diferencia entre awareness integrado e independiente", "awareness-modos"),
    ("para que sirven los diccionarios", "diccionarios"),
    ("¿cómo generar insights?", "insights-ia"),
    ("que proveedor de ia elijo", "proveedores-ia"),
    ("como me registro", "cuenta-acceso"),
    ("olvidé mi contraseña", "olvide-contrasena"),
    ("mi cuenta está suspendida", "cuenta-suspendida"),
    ("¿Qué puede hacer cada rol?", "roles-admin"),
    ("¿Cómo restablezco la contraseña de alguien?", "admin-restablecer"),
    ("¿Qué políticas de seguridad puedo configurar?", "politicas-seguridad"),
]
SHOULD_NOT_MATCH = [
    "¿Qué modelo se usó en mi última encuesta?", "cual es la capital de Francia", "receta de arepas", "hola",
    "cuanto cuesta el servicio", "dame los resultados de mi encuesta", "¿cuántos usuarios hay registrados?",
    "quiero comprar zapatos",
]


class HelpKnowledgeBaseTests(unittest.TestCase):
    def test_frequent_questions_get_the_right_article(self):
        for question, expected in SHOULD_MATCH:
            with self.subTest(question=question):
                result = help_kb.ask(question)
                self.assertTrue(result["confident"], f"sin respuesta: {question}")
                self.assertEqual(result["article"], expected)

    def test_out_of_scope_questions_are_not_answered_with_a_wrong_article(self):
        for question in SHOULD_NOT_MATCH:
            with self.subTest(question=question):
                self.assertFalse(help_kb.ask(question)["confident"])

    def test_every_article_is_well_formed_and_reachable(self):
        ids = [article["id"] for article in help_kb.ARTICLES]
        self.assertEqual(len(ids), len(set(ids)), "ids repetidos")
        valid_pages = {"home", "categorize", "dashboard", "awareness", "settings", "admin"}
        for article in help_kb.ARTICLES:
            self.assertTrue(article["answer"].strip() and article["keywords"], article["id"])
            for action in article["actions"]:
                self.assertIn(action["page"], valid_pages, article["id"])

    def test_answer_does_not_promise_things_the_platform_no_longer_does(self):
        text = " ".join(article["answer"] for article in help_kb.ARTICLES).lower()
        self.assertNotIn("tabla como csv", text)
        self.assertNotIn("insight tom", text)

    def test_current_page_breaks_ties(self):
        with_page = help_kb.search("cómo descargo", page="awareness")
        self.assertTrue(with_page)

    def test_answer_for_returns_the_requested_article(self):
        for article in help_kb.ARTICLES:
            self.assertEqual(help_kb.answer_for(article["id"])["answer"], article["answer"])
        self.assertIsNone(help_kb.answer_for("no-existe"))

    def test_page_suggestions_exist_for_every_page(self):
        for page in ("home", "categorize", "dashboard", "awareness", "settings", "admin"):
            self.assertEqual(len(help_kb.PAGE_SUGGESTIONS[page]), 3)
            for question in help_kb.PAGE_SUGGESTIONS[page]:
                self.assertTrue(help_kb.ask(question, page)["confident"], f"las sugerencias deben tener respuesta: {question}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
