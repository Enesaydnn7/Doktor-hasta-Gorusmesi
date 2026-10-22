"""Doktor paneli COMED'in iş listesi ekranına benzemeli.

Doktor gün boyu COMED'de çalışıyor; panel ona yabancı gelmemeli. COMED'de
sıra şu: önce arama kutusu ve tarih aralığı, sonra iş listesi tablosu.
Sayım/maliyet şeridi doktorun işine yaramıyor, sayfanın altına alındı.
"""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class DoctorPanelLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "templates" / "doctor.html").read_text(encoding="utf-8")
        cls.js = (ROOT / "static" / "doctor.js").read_text(encoding="utf-8")
        cls.css = (ROOT / "static" / "doctor.css").read_text(encoding="utf-8")

    def test_search_comes_before_the_worklist(self):
        """COMED'de arama kutusu listenin üstünde."""
        self.assertIn('class="comed-bar"', self.html)
        self.assertLess(
            self.html.index('id="q"'),
            self.html.index('id="worklist"'),
            "arama kutusu iş listesinden önce gelmeli",
        )

    def test_stats_moved_below_the_lists(self):
        """Sayım şeridi artık sayfanın başında değil."""
        self.assertIn("stat-strip-foot", self.html)
        self.assertLess(
            self.html.index('id="rec-list"'),
            self.html.index("stat-strip"),
            "sayım şeridi kayıt listesinden sonra gelmeli",
        )

    def test_has_a_date_range_like_comed(self):
        self.assertIn('id="date-from"', self.html)
        self.assertIn('id="date-to"', self.html)
        self.assertIn(".date-range", self.css)
        self.assertIn("function inDateRange(", self.js)

    def test_date_filter_uses_both_bounds(self):
        """Tek taraf doldurulursa yalnız o sınır uygulanmalı."""
        self.assertIn("if (from && day < from) return false;", self.js)
        self.assertIn("if (to && day > to) return false;", self.js)

    def test_search_filters_worklist_and_records(self):
        """Tek arama kutusu her iki listeyi de süzer."""
        self.assertIn("function applySearch(", self.js)
        self.assertIn('querySelectorAll(".wl-row")', self.js)
        self.assertIn('querySelectorAll(".rec-item")', self.js)
        self.assertIn("data-search", self.js)

    def test_search_survives_background_refresh(self):
        """15 saniyelik yenileme süzgeci silmemeli: render sonrası yeniden uygula."""
        self.assertIn("applySearch();", self.js)
        self.assertIn(
            "function render() { renderStats(); renderWorklist(); renderRecords(); applySearch(); }",
            self.js,
        )

    def test_clear_button_resets_patient_and_dates(self):
        self.assertIn("function clearFilters(", self.js)
        self.assertIn('id="date-clear"', self.html)

    def test_empty_state_for_filtered_worklist(self):
        self.assertIn('id="bos-worklist"', self.html)


if __name__ == "__main__":
    unittest.main()
