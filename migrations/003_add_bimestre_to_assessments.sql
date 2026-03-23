-- Migration: Adicionar coluna bimestre à tabela assessments
-- ============================================================================

-- Adicionar coluna bimestre com valor padrão 1
ALTER TABLE assessments
ADD COLUMN bimestre INTEGER DEFAULT 1 CHECK (bimestre IN (1, 2, 3, 4));

-- Criar índice para melhorar performance
CREATE INDEX idx_assessments_bimestre ON assessments(bimestre);
CREATE INDEX idx_assessments_class_id_bimestre ON assessments(class_id, bimestre);

-- Comentário para documentação
COMMENT ON COLUMN assessments.bimestre IS 'Bimestre da avaliação: 1 (Jan-Mar), 2 (Abr-Jun), 3 (Jul-Set), 4 (Out-Dez)';
