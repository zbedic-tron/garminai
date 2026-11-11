# Literatura v0.3

Alatka `search_training_literature(topic)` sada rangira rezultate po relevantnosti: oznake teme imaju veću težinu od naslova i napomena. Pretraga se odnosi ISKLJUČIVO na ručno odobrene reference u `data/literature/approved.json`. Novi kandidati su u `candidates.json` i ne postaju automatski pouzdani izvori.

**Postupak:** otkrij kandidat preko `python -m garminai_public.literature_admin --query "running training load"`, proveri DOI/PMID i primarni rad, tip studije, uzorak, ograničenja i odnosi li se na rekreativne trkače, pa napravi izmenu `approved.json` uz pregled. Baza ne kopira zaštićene cele naučne radove; samo bibliografske podatke i sopstvene kratke beleške.

Ograničenje: ovo je jednostavno pretraživanje ključnih reči, ne semantička pretraga ni automatska ocena kvaliteta dokaza. Bibliografiju je potrebno periodično proveravati.
