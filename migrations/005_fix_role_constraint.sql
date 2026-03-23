-- Migration: Corrigir constraint de role para aceitar 'aluno'
-- Motivo: Constraint antiga só aceitava 'student', precisa aceitar 'aluno'

-- 1. Remover constraint antiga
ALTER TABLE profiles
DROP CONSTRAINT IF EXISTS profiles_role_check;

-- 2. Adicionar constraint correta
ALTER TABLE profiles
ADD CONSTRAINT profiles_role_check 
CHECK (role IN ('super_admin', 'admin', 'professor', 'aluno'));

-- 3. Atualizar dados antigos
UPDATE profiles
SET role = 'aluno'
WHERE role = 'student';

-- 4. Verificar resultado
SELECT role, COUNT(*) as total FROM profiles GROUP BY role;
