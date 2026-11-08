"""Which drugs count as oncology / haematology.

Filter is by ATC code prefix. The oncology team should review this list once;
anything not matched here is still visible on the page under "Alle".
"""

BAG_URL = (
    "https://epl.bag.admin.ch/static/sl/publication/fhir/"
    "foph-sl-publication-latest-de.ndjson"
)

# (ATC prefix, group label). First matching prefix wins, so put specific
# exclusions (label None) before the broader prefix they belong to.
ATC_GROUPS = [
    # --- Onkologie ---
    ("L01", "Onkologie ‚Äì Antineoplastika"),
    ("L02", "Onkologie ‚Äì Endokrine Tumortherapie"),
    ("V10", "Onkologie ‚Äì Radiopharmaka"),
    ("H01CB", "Onkologie ‚Äì Somatostatin-Analoga (NET)"),
    ("M05BX04", "Onkologie ‚Äì Supportiv (Denosumab)"),
    ("V03AF", "Onkologie ‚Äì Supportiv (Entgiftung Zytostatika)"),
    ("A04AD", "Onkologie ‚Äì Supportiv (Antiemetika)"),
    # --- Immunmodulatoren, nur onko/h√§ma-relevante Untergruppen ---
    ("L03AA", "H√§matologie ‚Äì Wachstumsfaktoren (G-CSF)"),
    ("L03AB07", None),  # Interferon beta (MS) ‚Äì ausgeschlossen
    ("L03AB08", None),  # Interferon beta (MS) ‚Äì ausgeschlossen
    ("L03AB13", None),  # Peginterferon beta (MS) ‚Äì ausgeschlossen
    ("L03AB", "H√§matologie/Onkologie ‚Äì Interferone"),
    ("L03AX", "Onkologie ‚Äì Immunstimulanzien"),
    ("L04AX", "H√§matologie ‚Äì Immunmodulatoren (IMiDs)"),
    ("L04AJ", "H√§matologie ‚Äì Komplementinhibitoren"),
    # --- H√§matologie ---
    # B01 (Antithrombotika) bewusst nicht: fast nur Kardiologie (z.B. Ticagrelor).
    ("B02", "H√§matologie ‚Äì H√§mostatika / Gerinnungsfaktoren"),
    ("B03", "H√§matologie ‚Äì Antian√§mika"),
    ("B06", "H√§matologie ‚Äì Andere H√§matologika"),
]


def group_for_atc(atc: str):
    atc = (atc or "").upper()
    for prefix, label in ATC_GROUPS:
        if atc.startswith(prefix):
            return label
    return None
