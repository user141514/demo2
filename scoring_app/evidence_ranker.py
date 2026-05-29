"""TF-IDF based evidence ranking for scoring dimensions.

Provides semantic similarity scoring between dimension definitions and
document sentences, fused with keyword density for robustness.
"""

import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class EvidenceRanker:
    """Ranks document sentences by TF-IDF similarity to dimension definitions."""

    def __init__(self, definitions):
        self.definitions = definitions
        self._build_tfidf(definitions)

    def _build_tfidf(self, definitions):
        """Build TF-IDF vectors for each dimension from its name, focus, and keywords."""
        dim_corpus = []
        self.dim_ids = []
        for dim in definitions["dimensions"]:
            doc_text = "{} {} {}".format(
                dim["name"], dim["focus"], " ".join(dim.get("keywords", []))
            )
            dim_corpus.append(doc_text)
            self.dim_ids.append(dim["id"])

        self.vectorizer = TfidfVectorizer(
            analyzer="char_wb", ngram_range=(2, 4), max_features=5000
        )
        self.dim_vectors = self.vectorizer.fit_transform(dim_corpus)

    def rank_sentences(self, sentences, dimension_id):
        """Return top-3 sentences ranked by cosine similarity with the dimension vector."""
        if not sentences:
            return []

        sent_vectors = self.vectorizer.transform(sentences)
        dim_idx = self.dim_ids.index(dimension_id)
        dim_vector = self.dim_vectors[dim_idx]

        similarities = cosine_similarity(sent_vectors, dim_vector).flatten()
        ranked = sorted(
            range(len(sentences)), key=lambda i: similarities[i], reverse=True
        )
        top3 = ranked[:3]
        return [
            {"sentence": sentences[i], "similarity": float(similarities[i])}
            for i in top3
        ]

    def best_evidence(self, text, dimension):
        """Select best evidence using 0.7 TF-IDF + 0.3 keyword density fusion."""
        sentences = self._split_sentences(text)
        candidates = self.rank_sentences(sentences, dimension["id"])
        if not candidates:
            return "文档文本提取质量不足，未找到可直接引用的有效证据。"

        keywords = dimension.get("keywords", [])
        for c in candidates:
            kw_density = self._calc_keyword_density(c["sentence"], keywords)
            c["combined_score"] = 0.7 * c["similarity"] + 0.3 * kw_density

        candidates.sort(key=lambda c: c["combined_score"], reverse=True)
        return self._limit(candidates[0]["sentence"], 80)

    def _calc_keyword_density(self, text, keywords):
        """Calculate keyword hit ratio for a piece of text."""
        if not keywords:
            return 0.0
        hits = sum(1 for kw in keywords if kw in text)
        return min(hits / float(len(keywords)), 1.0)

    @staticmethod
    def _split_sentences(text):
        """Split text into sentences by Chinese/English sentence terminators."""
        return [
            segment.strip()
            for segment in re.split(r"[。！？\n\r]+", text)
            if segment.strip()
        ]

    @staticmethod
    def _limit(text, size):
        """Truncate text to approximately *size* characters, appending an ellipsis."""
        if len(text) <= size:
            return text
        return text[: size - 1].rstrip() + "…"
