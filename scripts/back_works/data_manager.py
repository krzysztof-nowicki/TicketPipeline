import json
from pathlib import Path
from typing import Optional
from scripts.utils.data_classes import Customer, Invoice, KBArticle, Ticket

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"

import math
import re
from collections import Counter
from difflib import SequenceMatcher
from typing import Optional
from scripts.utils.data_classes import KBArticle

STOPWORDS = {"in", "is", "a", "an", "the", "to", "for", "of", "and", "or", "on", "at", "by", "it", "if"}

def _tokenize(text: str) -> list[str]:
    """Extract lowercased alphanumeric words, ignoring common stopwords."""
    words = re.findall(r"\w+", text.lower())
    return [w for w in words if w not in STOPWORDS]


class DataManager:
    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or DATA_DIR
        self._customers: dict[str, Customer] = {}
        self._invoices: dict[str, Invoice] = {}
        self._kb: dict[str, KBArticle] = {}
        self._example_tickets: dict[str, Ticket] = {}
        self.load_data()

    def load_data(self) -> None:
        # Hard coded data loading from JSON files in the data directory, could be improved for automatic data type detection and validation
        customers_file = self.data_dir / "customers.json"
        if customers_file.exists():
            with open(customers_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._customers = {c["customer_id"]: Customer(**c) for c in data}

        invoices_file = self.data_dir / "invoices.json"
        if invoices_file.exists():
            with open(invoices_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._invoices = {i["invoice_id"]: Invoice(**i) for i in data}

        kb_file = self.data_dir / "kb.json"
        if kb_file.exists():
            with open(kb_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._kb = {k["article_id"]: KBArticle(**k) for k in data}

        tickets_file = self.data_dir / "example_tickets.json"
        if tickets_file.exists():
            with open(tickets_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._example_tickets = {t["ticket_id"]: Ticket(**t) for t in data}

    def get_customer(self, customer_id: str) -> Optional[Customer]:
        return self._customers.get(customer_id)

    def get_invoices(self, customer_id: str) -> list[Invoice]:
        return [inv for inv in self._invoices.values() if inv.customer_id == customer_id]

    def search_kb(
        self,
        query: str,
        top_k: int = 3,
        k1: float = 1.5,
        b: float = 0.75,
        fuzzy_threshold: float = 0.8,
        min_score: float = 0.7,
    ) -> list[KBArticle]:
        """
        BM25 search with typo-tolerant fuzzy matching and minimum score threshold.
        - Tokenizes query into words.
        - Corrects misspelled words if similarity >= fuzzy_threshold.
        - Ranks matching KB articles using standard BM25 formula.
        - Filters out low-relevance matches below min_score (e.g. single stopword matches).
        """
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        articles = list(self._kb.values())
        N = len(articles)
        if N == 0:
            return []

        doc_tokens = {
            a.article_id: _tokenize(f"{a.title} {a.text}") for a in articles
        }
        avg_doc_len = sum(len(tokens) for tokens in doc_tokens.values()) / N
        vocab = {word for tokens in doc_tokens.values() for word in tokens}

        expanded_tokens: list[str] = []
        for q in query_tokens:
            if q in vocab:
                expanded_tokens.append(q)
            else:
                # Closest word in KB vocabulary
                matches = [
                    w for w in vocab
                    if SequenceMatcher(None, q, w).ratio() >= fuzzy_threshold
                ]
                expanded_tokens.extend(matches if matches else [q])

        scores: dict[str, tuple[float, KBArticle]] = {}
        for article in articles:
            tokens = doc_tokens[article.article_id]
            doc_len = len(tokens)
            tf = Counter(tokens)
            score = 0.0

            for q in expanded_tokens:
                # Document frequency (number of docs containing term q)
                df = sum(1 for toks in doc_tokens.values() if q in toks)
                if df == 0:
                    continue

                idf = math.log((N - df + 0.5) / (df + 0.5) + 1.0)

                # Term Frequency component with document length normalization
                f = tf[q]
                numerator = f * (k1 + 1)
                denominator = f + k1 * (1 - b + b * (doc_len / avg_doc_len))
                score += idf * (numerator / denominator)

            if score >= min_score:
                scores[article.article_id] = (score, article)

        ranked = sorted(scores.values(), key=lambda x: x[0], reverse=True)
        return [article for score, article in ranked[:top_k]]

    def get_all_example_tickets(self) -> list[Ticket]:
        return list(self._example_tickets.values())


_global_data_manager: Optional[DataManager] = None


def get_data_manager() -> DataManager:
    global _global_data_manager
    if _global_data_manager is None:
        _global_data_manager = DataManager()
    return _global_data_manager
