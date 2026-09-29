# Copyright (c) 2026 AIgen Technologies S.L
# This file is part of alfdockia-community-search-ia.
# Distributed under the GNU Affero General Public License, version 3.
# See LICENSE and COPYRIGHT for details.

from __future__ import annotations

import unittest

from alfdockia.community.search.ia.cursor import CursorCodec, CursorError


class CursorCodecTest(unittest.TestCase):
    def setUp(self) -> None:
        self.codec = CursorCodec("a-test-secret-with-enough-entropy", ttl_seconds=300, clock=lambda: 1_000)

    def test_round_trips_signed_state_bound_to_request_and_principal(self) -> None:
        token = self.codec.encode(
            bindings={"mode": "bulk", "query": "query-hash", "filters": "filter-hash", "principal": "maria"},
            state={"offset": "11111111-1111-1111-1111-111111111111"},
        )

        state = self.codec.decode(
            token,
            bindings={"mode": "bulk", "query": "query-hash", "filters": "filter-hash", "principal": "maria"},
        )

        self.assertEqual({"offset": "11111111-1111-1111-1111-111111111111"}, state)

    def test_rejects_tampering_expiry_and_changed_bindings(self) -> None:
        token = self.codec.encode(
            bindings={"mode": "interactive", "query": "q", "filters": "f", "principal": "maria"},
            state={"seen": ["one"]},
        )
        with self.assertRaises(CursorError):
            self.codec.decode(token + "x", {"mode": "interactive", "query": "q", "filters": "f", "principal": "maria"})
        with self.assertRaises(CursorError):
            self.codec.decode(token, {"mode": "interactive", "query": "q", "filters": "f", "principal": "otro"})
        expired = CursorCodec("a-test-secret-with-enough-entropy", ttl_seconds=300, clock=lambda: 1_301)
        with self.assertRaises(CursorError):
            expired.decode(token, {"mode": "interactive", "query": "q", "filters": "f", "principal": "maria"})


if __name__ == "__main__":
    unittest.main()
