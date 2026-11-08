import os
import unittest
from unittest.mock import patch

from app import accounts, policies


class PermissionMatrixTests(unittest.TestCase):
    def test_regular_users_cannot_administer(self):
        for action in ("deactivate", "ban", "delete", "role", "reset_password"):
            self.assertIsNotNone(accounts.permission_error("user", "user", action, False), action)

    def test_admin_can_manage_regular_users_but_not_assign_roles(self):
        for action in ("deactivate", "ban", "delete", "reset_password"):
            self.assertIsNone(accounts.permission_error("admin", "user", action, False), action)
        self.assertIn("super administrador", accounts.permission_error("admin", "user", "role", False))

    def test_admin_cannot_act_on_other_admins_or_super_admin(self):
        for action in ("deactivate", "ban", "delete", "reset_password"):
            self.assertIsNotNone(accounts.permission_error("admin", "admin", action, False), action)
            self.assertIsNotNone(accounts.permission_error("admin", "super_admin", action, False), action)

    def test_super_admin_can_manage_everyone_except_himself_and_other_super_admins(self):
        for target in ("user", "admin"):
            for action in ("deactivate", "ban", "delete", "reset_password", "role"):
                self.assertIsNone(accounts.permission_error("super_admin", target, action, False), (target, action))
        for action in ("deactivate", "ban", "delete", "role", "reset_password"):
            self.assertIsNotNone(accounts.permission_error("super_admin", "super_admin", action, False))
            self.assertIsNotNone(accounts.permission_error("super_admin", "admin", action, True), action)

    def test_nobody_can_remove_or_ban_the_super_admin(self):
        self.assertIn("super administrador", accounts.permission_error("super_admin", "super_admin", "ban", False))

    def test_account_state(self):
        class U:
            banned_at = None
            is_active = True
        user = U()
        self.assertEqual(accounts.account_state(user), "active")
        user.is_active = False
        self.assertEqual(accounts.account_state(user), "inactive")
        user.banned_at = object()
        self.assertEqual(accounts.account_state(user), "banned")  # el baneo prevalece sobre la inactivación


class NewUserRoleTests(unittest.TestCase):
    def role(self, email, super_exists, configured):
        with patch.dict(os.environ, {"SUPERADMIN_EMAIL": configured}), \
                patch("app.accounts.super_admin_exists", return_value=super_exists):
            return accounts.new_user_role(object(), email)

    def test_new_users_are_regular_by_default(self):
        self.assertEqual(self.role("ana@omc.com", False, "jefe@omc.com"), "user")

    def test_only_the_configured_email_can_become_super_admin_and_only_once(self):
        self.assertEqual(self.role("jefe@omc.com", False, "Jefe@omc.com"), "super_admin")
        self.assertEqual(self.role("jefe@omc.com", True, "Jefe@omc.com"), "user")

    def test_without_configuration_nobody_becomes_super_admin(self):
        self.assertEqual(self.role("x@omc.com", False, ""), "user")


class PolicyValidationTests(unittest.TestCase):
    def test_valid_changes_are_accepted(self):
        cleaned = policies.clean_policy({
            "min_password_length": 14, "require_complexity": True, "session_minutes": 120, "max_failed_logins": 5,
            "lockout_minutes": 15, "registration_enabled": False, "allowed_email_domains": ["@OMC.com", "omc.co", "omc.com"],
            "ai_redact_pii": True, "allowed_ai_providers": ["groq", "anthropic"],
        })
        self.assertEqual(cleaned["allowed_email_domains"], ["omc.com", "omc.co"])
        self.assertEqual(cleaned["session_minutes"], 120)

    def test_out_of_range_and_unknown_values_are_rejected_with_all_problems(self):
        with self.assertRaises(ValueError) as caught:
            policies.clean_policy({"min_password_length": 4, "session_minutes": 99999, "inventada": 1,
                                   "allowed_ai_providers": ["no-existe"], "allowed_email_domains": ["no valido!"]})
        message = str(caught.exception)
        for fragment in ("entre 12 y 64", "entre 15 y 1440", "desconocida", "proveedores", "dominios válidos"):
            self.assertIn(fragment, message)

    def test_booleans_must_be_real_booleans(self):
        with self.assertRaises(ValueError):
            policies.clean_policy({"registration_enabled": "si"})
        with self.assertRaises(ValueError):
            policies.clean_policy({"min_password_length": True})

    def test_password_rules(self):
        base = policies.default_policy()
        self.assertEqual(policies.password_problems("una-clave-larga-123", base), [])
        self.assertTrue(policies.password_problems("corta", base))
        strict = {**base, "min_password_length": 14, "require_complexity": True}
        self.assertTrue(policies.password_problems("todaminusculas", strict))
        self.assertEqual(policies.password_problems("Abcdefghijk1!z", strict), [])

    def test_domain_and_provider_rules(self):
        policy = {**policies.default_policy(), "allowed_email_domains": ["empresa.com"], "allowed_ai_providers": ["groq"]}
        self.assertTrue(policies.email_domain_ok("ana@empresa.com", policy))
        self.assertFalse(policies.email_domain_ok("ana@gmail.com", policy))
        self.assertTrue(policies.provider_allowed("groq", policy))
        self.assertFalse(policies.provider_allowed("gemini", policy))
        self.assertTrue(policies.provider_allowed("gemini", policies.default_policy()))


class TemporaryPasswordTests(unittest.TestCase):
    def test_passwords_are_random_strong_and_meet_the_default_policy(self):
        seen = set()
        for _ in range(50):
            password = policies.generate_temporary_password()
            seen.add(password)
            self.assertGreaterEqual(len(password), 16)
            self.assertEqual(policies.password_problems(password, {**policies.default_policy(), "require_complexity": True, "min_password_length": 16}), [])
        self.assertEqual(len(seen), 50)


if __name__ == "__main__":
    unittest.main(verbosity=2)
