"""
search_engine.py — TF-IDF based article search engine for internal backlinking.

Loads article titles from the database, builds a TF-IDF matrix, and supports
fast cosine similarity search for finding related articles.
"""

import logging
import re
from typing import Optional

import psycopg2
from psycopg2.extras import RealDictCursor
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)


class ArticleSearchEngine:
    """TF-IDF based search engine for finding related articles."""

    def __init__(self):
        self.articles: list[dict] = []
        self.vectorizer: Optional[TfidfVectorizer] = None
        self.tfidf_matrix = None
        self._is_ready = False

    @property
    def is_ready(self) -> bool:
        return self._is_ready and len(self.articles) > 0

    @property
    def article_count(self) -> int:
        return len(self.articles)

    def build_index(self, database_url: str) -> int:
        """Load articles from DB and build TF-IDF index."""
        conn = psycopg2.connect(database_url)
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT url, title, category, lastmod FROM article_index ORDER BY lastmod DESC NULLS LAST"
                )
                rows = cur.fetchall()
        finally:
            conn.close()

        if not rows:
            logger.warning("No articles in article_index table.")
            self._is_ready = False
            return 0

        self.articles = [dict(r) for r in rows]

        # Build TF-IDF from titles
        titles = [self._normalize(a["title"]) for a in self.articles]
        self.vectorizer = TfidfVectorizer(
            max_features=5000,
            ngram_range=(1, 2),  # uni + bigrams for better matching
            stop_words="english",
            min_df=1,
            sublinear_tf=True,
        )
        self.tfidf_matrix = self.vectorizer.fit_transform(titles)
        self._is_ready = True

        logger.info(f"Search index built: {len(self.articles)} articles, "
                     f"{len(self.vectorizer.vocabulary_)} features")
        return len(self.articles)

    def search(self, query: str, top_k: int = 6) -> list[dict]:
        """Search for articles similar to the query.

        Returns list of dicts with: url, title, category, lastmod, score
        """
        if not self.is_ready:
            return []

        # Normalize and vectorize query
        query_normalized = self._normalize(query)
        query_vec = self.vectorizer.transform([query_normalized])

        # Compute cosine similarity
        scores = cosine_similarity(query_vec, self.tfidf_matrix).flatten()

        # Get top-k results (exclude zero scores)
        ranked_indices = scores.argsort()[::-1]
        results = []
        for idx in ranked_indices:
            if len(results) >= top_k:
                break
            score = float(scores[idx])
            if score < 0.01:  # skip near-zero matches
                break
            article = self.articles[idx].copy()
            article["score"] = round(score * 100, 1)  # percentage
            # Convert lastmod to string for JSON
            if article.get("lastmod"):
                article["lastmod"] = str(article["lastmod"])
            results.append(article)

        return results

    @staticmethod
    def _normalize(text: str) -> str:
        """Normalize text for TF-IDF: lowercase, remove special chars."""
        text = text.lower()
        text = re.sub(r"[^a-z0-9\s]", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text


# Global singleton
search_engine = ArticleSearchEngine()
