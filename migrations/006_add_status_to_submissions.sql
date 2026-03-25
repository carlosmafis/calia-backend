-- Migration: Adicionar coluna status em student_submissions
-- Motivo: Permitir marcar alunos como "ausente" ou "presente"

-- 1. Adicionar coluna status
ALTER TABLE student_submissions
ADD COLUMN status VARCHAR(20) DEFAULT 'presente' 
CHECK (status IN ('presente', 'ausente'));

-- 2. Criar índice para melhorar performance
CREATE INDEX idx_student_submissions_status ON student_submissions(status);

-- 3. Verificar resultado
SELECT status, COUNT(*) as total FROM student_submissions GROUP BY status;
