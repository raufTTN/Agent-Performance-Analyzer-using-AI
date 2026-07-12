import numpy as np
import re
from utils.db_manager import get_db_connection

class LocalTicketVectorStore:
    def __init__(self):
        # Local vocabulary hashes to keep vector sizing uniform at 384 dimensions
        self.vector_dim = 384

    def _generate_vector(self, text: str) -> np.ndarray:
        """Transforms text into a normalized frequency vector using native hashing."""
        vec = np.zeros((self.vector_dim,), dtype=np.float32)
        if not text:
            return vec
            
        # Clean text and tokenize into words
        words = re.sub(r'[^a-zA-Z0-9\s]', '', str(text).lower()).split()
        
        for word in words:
            # Deterministic hashing to map words to vector slots
            idx = hash(word) % self.vector_dim
            vec[idx] += 1.0
            
        norm = np.linalg.norm(vec)
        return vec / norm if norm > 0 else vec

    def surface_similar_resolutions(self, current_subject: str, current_description: str, top_k: int = 3) -> list:
        """Compares current issue text against database records using cosine similarity."""
        query_text = f"{current_subject} {current_description}"
        query_vector = self._generate_vector(query_text)
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Select historically resolved items to harvest past knowledge
            cursor.execute("""
                SELECT ticket_id, subject, description, resolution_applied, resolution_note, agent 
                FROM tickets 
                WHERE resolution_note IS NOT NULL AND resolution_note != '' AND resolution_note != 'nan'
            """)
            rows = cursor.fetchall()
            
        scored_matches = []
        for row in rows:
            historical_text = f"{row['subject']} {row['description']}"
            historical_vector = self._generate_vector(historical_text)
            
            # Compute cosine similarity value
            similarity_score = float(np.dot(query_vector, historical_vector))
            
            if similarity_score > 0.0:  # Only gather positive match indices
                scored_matches.append((similarity_score, row))
                
        # Sort by highest match confidence score
        scored_matches.sort(key=lambda x: x[0], reverse=True)
        
        results = []
        for score, match in scored_matches[:top_k]:
            results.append({
                "ticket_id": match["ticket_id"],
                "subject": match["subject"],
                "resolution_note": match["resolution_note"] if match["resolution_note"] else match["resolution_applied"],
                "agent": match["agent"],
                "confidence": round(score * 100, 1)
            })
        return results

