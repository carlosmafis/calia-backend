-- ============================================================================
-- MIGRATION: Adicionar coluna class_id à tabela student_submissions
-- ============================================================================
-- Esta migration adiciona a coluna class_id que é necessária para:
-- 1. Filtrar submissões por turma nos relatórios
-- 2. Melhorar performance nas queries
-- 3. Manter integridade referencial
-- ============================================================================

-- Adicionar coluna class_id à tabela student_submissions
ALTER TABLE student_submissions
ADD COLUMN class_id UUID REFERENCES classes(id) ON DELETE CASCADE;

-- Criar índice para melhorar performance
CREATE INDEX idx_student_submissions_class_id ON student_submissions(class_id);

-- Preencher class_id com base na relação assessment -> class_id
UPDATE student_submissions ss
SET class_id = a.class_id
FROM assessments a
WHERE ss.assessment_id = a.id;

-- Tornar a coluna NOT NULL após preencher os dados existentes
ALTER TABLE student_submissions
ALTER COLUMN class_id SET NOT NULL;

-- ============================================================================
-- FIM DA MIGRATION
-- ============================================================================
