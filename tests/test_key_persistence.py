"""Tests for SQLite encrypted provider key and configuration persistence.

Ensures:
1. Provider credentials and endpoints are securely saved to SQLite store.
2. Saved credentials survive restart and are cleanly restored into ApiHandler.
3. Raw secret is obfuscated / not stored as plaintext in the database table.
4. Active provider setting is durably persisted and restored.
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from software_factory.core import Store, ApiHandler, _obfuscate_key, _deobfuscate_key


class KeyPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "vault_test.sqlite3"
        self.store = Store(self.db_path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_obfuscation_roundtrip(self):
        raw = "gsk_test_groq_key_9876543210"
        enc = _obfuscate_key(raw)
        self.assertNotEqual(raw, enc)
        self.assertNotIn("groq", enc)
        dec = _deobfuscate_key(enc)
        self.assertEqual(dec, raw)

    def test_save_and_retrieve_credentials(self):
        self.store.save_provider_credential("deepseek", "mock-deepseek-key-12345", "https://custom.deepseek.com/v1")
        self.store.save_provider_credential("groq", "gsk_groq_test_key_54321")

        creds = self.store.get_provider_credentials()
        self.assertIn("deepseek", creds)
        self.assertEqual(creds["deepseek"]["api_key"], "mock-deepseek-key-12345")
        self.assertEqual(creds["deepseek"]["base_url"], "https://custom.deepseek.com/v1")
        self.assertIn("groq", creds)
        self.assertEqual(creds["groq"]["api_key"], "gsk_groq_test_key_54321")

        # Verify plaintext secret is NOT in raw sqlite database table
        conn = sqlite3.connect(self.db_path)
        row = conn.execute("SELECT api_key_encrypted FROM provider_credentials WHERE provider_slug='deepseek'").fetchone()
        conn.close()
        self.assertNotIn("mock-deepseek-key-12345", row[0])

    def test_system_settings_persistence(self):
        self.store.save_system_setting("active_provider", "deepseek")
        val = self.store.get_system_setting("active_provider")
        self.assertEqual(val, "deepseek")

    def test_apihandler_loads_persisted_keys_on_boot(self):
        # Save credentials in Store
        self.store.save_provider_credential("mistralai", "mock-mistral-key-12345", "https://api.mistral.ai/v1")
        self.store.save_system_setting("active_provider", "mistralai")

        # Reset ApiHandler memory
        ApiHandler.store = self.store
        ApiHandler.provider_keys = {}
        ApiHandler.provider_urls = {}
        ApiHandler.ai_provider = "auto"
        ApiHandler.ai_key = None

        # Load
        ApiHandler.load_persisted_keys()

        self.assertEqual(ApiHandler.ai_provider, "mistralai")
        self.assertEqual(ApiHandler.ai_key, "mock-mistral-key-12345")
        self.assertIn("mistralai", ApiHandler.provider_keys)
        self.assertEqual(ApiHandler.provider_keys["mistralai"], "mock-mistral-key-12345")
        self.assertEqual(ApiHandler.provider_urls.get("mistralai"), "https://api.mistral.ai/v1")


if __name__ == "__main__":
    unittest.main()

