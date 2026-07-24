-- Migration 015: change embedding column from vector(1536) to vector(768)
-- to align with the Ollama `nomic-embed-text` local embedder.
--
-- The previous dimension was 1536, matching OpenAI's text-embedding-3-small.
-- The OpenRouter key on file is no longer valid, so the deployment now uses a
-- local Ollama service with nomic-embed-text (768 dimensions). The embedding
-- column must match so semantic search can store and compare vectors.
--
-- This migration is safe on a fresh database that has not yet stored real
-- embeddings. On an installation with previously-stored 1536-dim vectors the
-- column would need to be dropped and re-created (loss of prior embeddings);
-- that has been intentionally avoided here.

ALTER TABLE memory ALTER COLUMN embedding TYPE vector(768);

-- The HNSW index on embedding needs to be rebuilt to match the new dimension.
DROP INDEX IF EXISTS idx_memory_embedding;
CREATE INDEX IF NOT EXISTS idx_memory_embedding
    ON memory USING hnsw (embedding vector_cosine_ops);
