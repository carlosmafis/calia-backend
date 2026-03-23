-- Migration: Atualizar role "student" para "aluno" em todos os perfis existentes
-- Motivo: Compatibilidade com frontend que espera role "aluno"

UPDATE profiles
SET role = 'aluno'
WHERE role = 'student';

-- Verificar quantos registros foram atualizados
SELECT COUNT(*) as updated_count FROM profiles WHERE role = 'aluno';
