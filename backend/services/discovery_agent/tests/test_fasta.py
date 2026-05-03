"""Tests for _parse_fasta_to_sequence in mcp_agent."""
import unittest

from mcp_agent import _parse_fasta_to_sequence


class TestParseFasta(unittest.TestCase):
    def test_header_and_multiline(self):
        fasta = ">sp|P12345|TEST\nMKTVRQERL\nKSIVRILER\n"
        self.assertEqual(_parse_fasta_to_sequence(fasta), "MKTVRQERLKSIVRILER")

    def test_header_only(self):
        self.assertEqual(_parse_fasta_to_sequence(">sp|P12345|TEST\n"), "")

    def test_whitespace_only(self):
        self.assertEqual(_parse_fasta_to_sequence("   \n \t\n"), "")

    def test_empty(self):
        self.assertEqual(_parse_fasta_to_sequence(""), "")
        self.assertEqual(_parse_fasta_to_sequence(None), "")  # type: ignore[arg-type]

    def test_no_header_single_line(self):
        self.assertEqual(_parse_fasta_to_sequence("MKTVRQER"), "MKTVRQER")

    def test_embedded_whitespace(self):
        fasta = ">x\nMKT VRQ\n ERL \n"
        self.assertEqual(_parse_fasta_to_sequence(fasta), "MKTVRQERL")


if __name__ == "__main__":
    unittest.main()
