CREATE TABLE IF NOT EXISTS audit.ai_validation_results (
    validation_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pipeline_run_id UUID NOT NULL,
    barcode TEXT,
    status TEXT NOT NULL CHECK (status IN ('pass', 'reject')),
    confidence NUMERIC(5, 4) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    reasons JSONB NOT NULL DEFAULT '[]'::JSONB,
    validator TEXT NOT NULL,
    validated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ai_validation_barcode_time
ON audit.ai_validation_results (barcode, validated_at DESC);
