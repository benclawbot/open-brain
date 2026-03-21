-- Open Brain Database Schema
-- PostgreSQL + pgvector

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- Core memory table
CREATE TABLE IF NOT EXISTS memory (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source VARCHAR(50) NOT NULL,
    source_id VARCHAR(255),
    content TEXT NOT NULL,
    raw_content TEXT,
    embedding vector(768),
    entities JSONB DEFAULT '{}',
    tags TEXT[] DEFAULT '{}',
    tag_sources JSONB DEFAULT '{}',
    importance FLOAT DEFAULT 0.5,
    created_at TIMESTAMP DEFAULT NOW(),
    original_date TIMESTAMP,
    language VARCHAR(10),
    metadata JSONB DEFAULT '{}'
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_memory_embedding ON memory USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_memory_entities ON memory USING gin (entities);
CREATE INDEX IF NOT EXISTS idx_memory_tags ON memory USING gin (tags);
CREATE INDEX IF NOT EXISTS idx_memory_source ON memory (source);
CREATE INDEX IF NOT EXISTS idx_memory_created ON memory (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_memory_original_date ON memory (original_date DESC);

-- Full-text search index
CREATE INDEX IF NOT EXISTS idx_memory_content_fts ON memory USING GIN (to_tsvector('english', content));

-- Function to generate embeddings (placeholder - computed in Python)
-- This allows us to store pre-computed embeddings

-- Function to get memories from today
CREATE OR REPLACE FUNCTION get_today_memories(limit_count INTEGER DEFAULT 10)
RETURNS TABLE (
    id UUID,
    source VARCHAR,
    content TEXT,
    tags TEXT[],
    created_at TIMESTAMP,
    importance FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT m.id, m.source, m.content, m.tags, m.created_at, m.importance
    FROM memory m
    WHERE m.created_at >= CURRENT_DATE
    ORDER BY m.importance DESC, m.created_at DESC
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;

-- Function to get memory statistics
CREATE OR REPLACE FUNCTION get_memory_stats()
RETURNS TABLE (
    total_count BIGINT,
    source_name VARCHAR,
    source_count BIGINT,
    tag_name TEXT,
    tag_count BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(*)::BIGINT as total_count,
        NULL::VARCHAR as source_name,
        NULL::BIGINT as source_count,
        NULL::TEXT as tag_name,
        NULL::BIGINT as tag_count
    FROM memory;
END;
$$ LANGUAGE plpgsql;
