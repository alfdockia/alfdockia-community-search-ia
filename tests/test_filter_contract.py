# Copyright (c) 2026 AIgen Technologies S.L
# This file is part of alfdockia-community-search-ia.
# Distributed under the GNU Affero General Public License, version 3.
# See LICENSE and COPYRIGHT for details.

from __future__ import annotations

import unittest

from alfdockia.community.search.ia.filter_contract import FilterValidationError, encode_qname, normalize_metadata_filters


class FilterContractTest(unittest.TestCase):
    def test_normalizes_typed_metadata_filters(self) -> None:
        result = normalize_metadata_filters({
            "version": 1,
            "types": ["cm:content", "acme:contract", "cm:content"],
            "aspects": ["cm:titled"],
            "properties": [
                {"name": "acme:vivienda", "operator": "eq", "value": True, "dataType": "d:boolean"},
                {"name": "acme:importe", "operator": "between", "value": [1000, 5000], "dataType": "d:double"},
            ],
        })

        self.assertEqual(["cm:content", "acme:contract"], result["types"])
        self.assertEqual([1000.0, 5000.0], result["properties"][1]["value"])

    def test_rejects_invalid_qname_and_operator(self) -> None:
        with self.assertRaisesRegex(FilterValidationError, r"properties\[0\]"):
            normalize_metadata_filters({
                "version": 1,
                "properties": [
                    {"name": "bad field", "operator": "execute", "value": "x", "dataType": "d:text"}
                ],
            })

    def test_encodes_qname_like_indexer(self) -> None:
        self.assertEqual("q_636d3a636f6e74656e742e6d696d6574797065", encode_qname("cm:content.mimetype"))
        self.assertEqual("q_7379733a6e6f64652d75756964", encode_qname("sys:node-uuid"))

    def test_rejects_unknown_contract_fields(self) -> None:
        with self.assertRaises(FilterValidationError):
            normalize_metadata_filters({"version": 1, "script": "ignored"})


if __name__ == "__main__":
    unittest.main()
